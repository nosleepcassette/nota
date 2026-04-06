# nota — MVP spec
**Target:** buildable in one session (~2-4 hours)
**Scope:** Phase 0 only — no LLM, no web UI, no garden sync
**Deliverable:** Working CLI + MCP server that stores, queries, and links tasks

---

## What MVP does

1. `nota add` — add a task with inline syntax parsing (title, project, priority, scope, due, tags, subtasks, relations)
2. `nota list` — list tasks, filterable by project/scope/priority/status
3. `nota show ID` — show a task with its subtasks and relations
4. `nota done ID` — mark complete
5. `nota link ID --depends-on ID2` — add relation between tasks
6. `nota projects` — list all known projects with counts
7. MCP server (`nota mcp`) — exposes the above as MCP tools for Claude/Codex/Gemini/Hermes

## What MVP does NOT do

- LLM braindump parsing (Phase 1)
- Web UI (Phase 3)
- Garden sync (Phase 4)
- Recurring tasks
- Due date natural language parsing (store as-is in MVP; parse in Phase 1)

---

## File structure

```
~/dev/nota/
├── MVP.md              (this file)
├── SCOPE.md
├── bin/
│   └── nota            (executable Python script)
├── src/
│   ├── __init__.py
│   ├── db.py           (SQLite schema + CRUD)
│   ├── parse.py        (inline syntax: ->, ::, p1-p4, @project, #tag, scope:x)
│   ├── cli.py          (argparse CLI commands)
│   └── mcp_server.py   (MCP stdio server)
├── requirements.txt
└── config.example.toml
```

---

## Build instructions

### 1. Schema (`src/db.py`)

```python
# maps · cassette.help · MIT
import sqlite3, os, time
from pathlib import Path

DB_PATH = Path(os.environ.get("NOTA_DB", Path.home() / ".nota" / "nota.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT DEFAULT '',
    project TEXT DEFAULT 'inbox',
    scope TEXT DEFAULT '',
    priority INTEGER DEFAULT 3,
    due_date TEXT DEFAULT NULL,
    status TEXT DEFAULT 'todo',
    parent_id INTEGER REFERENCES tasks(id),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS task_relations (
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    related_id INTEGER NOT NULL REFERENCES tasks(id),
    relation_type TEXT NOT NULL,
    PRIMARY KEY (task_id, related_id, relation_type)
);

CREATE TABLE IF NOT EXISTS task_tags (
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    tag TEXT NOT NULL,
    PRIMARY KEY (task_id, tag)
);
"""

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn

def task_create(title, body='', project='inbox', scope='', priority=3,
                due_date=None, parent_id=None, tags=None):
    now = int(time.time())
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title,body,project,scope,priority,due_date,parent_id,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (title, body, project, scope, priority, due_date, parent_id, now, now)
        )
        task_id = cur.lastrowid
        for tag in (tags or []):
            conn.execute("INSERT OR IGNORE INTO task_tags VALUES (?,?)", (task_id, tag))
        return task_id

def task_relate(task_id, related_id, relation_type):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO task_relations VALUES (?,?,?)",
            (task_id, related_id, relation_type)
        )

def task_done(task_id):
    now = int(time.time())
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status='done', updated_at=? WHERE id=?", (now, task_id)
        )

def task_get(task_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return None
        t = dict(row)
        t['tags'] = [r['tag'] for r in conn.execute(
            "SELECT tag FROM task_tags WHERE task_id=?", (task_id,))]
        t['subtasks'] = [dict(r) for r in conn.execute(
            "SELECT * FROM tasks WHERE parent_id=? AND status != 'done'", (task_id,))]
        t['relations'] = [dict(r) for r in conn.execute(
            "SELECT tr.related_id, tr.relation_type, t.title FROM task_relations tr "
            "JOIN tasks t ON t.id=tr.related_id WHERE tr.task_id=?", (task_id,))]
        return t

def task_list(project=None, scope=None, priority=None, status='todo', limit=50):
    where = ["status=?"]
    params = [status]
    if project:
        where.append("project=?"); params.append(project)
    if scope:
        where.append("scope=?"); params.append(scope)
    if priority:
        where.append("priority=?"); params.append(priority)
    sql = f"SELECT * FROM tasks WHERE {' AND '.join(where)} ORDER BY priority ASC, due_date ASC NULLS LAST, created_at ASC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params)]

def projects_list():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT project, COUNT(*) as count FROM tasks WHERE status='todo' GROUP BY project ORDER BY count DESC"
        )]
```

---

### 2. Inline parser (`src/parse.py`)

```python
# maps · cassette.help · MIT
import re

PRIORITY_MAP = {'p1': 1, 'p2': 2, 'p3': 3, 'p4': 4}
SCOPES = {'meatspace','digital','server','opencassette','appointment','recurring','waiting','creative','admin','errand'}

def parse_inline(text):
    """
    Parse nota inline syntax from a task string.
    Returns dict: {title, subtasks[], related_titles[], project, priority, scope, tags[], due_date}

    Syntax:
      main task -> subtask1 -> subtask2   (subtasks, order-dependent)
      task A :: task B                    (related_to, bidirectional)
      p1/p2/p3/p4                         (priority)
      @project-name                        (project)
      #tag                                 (tags)
      scope:meatspace                      (scope)
      due:YYYY-MM-DD or due:friday        (due date, stored as-is for now)
    """
    # Split on :: first (related)
    related_titles = []
    if '::' in text:
        parts = text.split('::')
        text = parts[0].strip()
        related_titles = [p.strip() for p in parts[1:] if p.strip()]

    # Split on -> (subtasks)
    subtask_titles = []
    if '->' in text:
        parts = [p.strip() for p in text.split('->')]
        text = parts[0]
        subtask_titles = [p for p in parts[1:] if p]

    result = {
        'title': text,
        'subtasks': subtask_titles,
        'related_titles': related_titles,
        'project': 'inbox',
        'priority': 3,
        'scope': '',
        'tags': [],
        'due_date': None,
    }

    # Extract tokens from title
    tokens_to_remove = []
    for token in text.split():
        low = token.lower()
        if low in PRIORITY_MAP:
            result['priority'] = PRIORITY_MAP[low]
            tokens_to_remove.append(token)
        elif token.startswith('@') and len(token) > 1:
            result['project'] = token[1:]
            tokens_to_remove.append(token)
        elif token.startswith('#') and len(token) > 1:
            result['tags'].append(token[1:])
            tokens_to_remove.append(token)
        elif low.startswith('scope:'):
            sc = low[6:]
            if sc in SCOPES:
                result['scope'] = sc
            tokens_to_remove.append(token)
        elif low.startswith('due:'):
            result['due_date'] = token[4:]
            tokens_to_remove.append(token)

    for tok in tokens_to_remove:
        text = text.replace(tok, '').strip()
    result['title'] = re.sub(r'\s+', ' ', text).strip()
    return result
```

---

### 3. CLI (`src/cli.py` and `bin/nota`)

The CLI needs these commands:

```
nota add "text with inline syntax"
nota add "reply to pick n pull -> find stamps :: clean room" --body "optional notes"
nota list [--project X] [--scope X] [--priority N] [--all]
nota show ID
nota done ID
nota link ID --depends-on ID2
nota link ID --related-to ID2
nota projects
nota mcp              # start MCP stdio server
```

**`bin/nota` entrypoint** — argparse dispatcher calling `src/cli.py` functions. Output is human-readable for terminal, JSON-serializable for agent consumption (`--json` flag).

---

### 4. MCP server (`src/mcp_server.py`)

Tools to expose:

```
nota_add(title, body?, project?, scope?, priority?, due_date?)
  → {id, title, project, ...}

nota_braindump(text)
  → MVP: same as nota_add with inline parse; Phase 1: LLM parse

nota_list(project?, scope?, priority?, status?)
  → [{id, title, project, scope, priority, due_date, status}, ...]

nota_show(id)
  → {id, title, body, project, scope, priority, due_date, status, tags[], subtasks[], relations[]}

nota_done(id)
  → {ok: true}

nota_link(task_id, related_id, relation_type)
  → {ok: true}

nota_projects()
  → [{project, count}, ...]
```

Use `mcp` Python library (same pattern as other sextile MCP servers). Transport: stdio.

---

### 5. Config (`~/.nota/config.toml`)

```toml
[nota]
db_path = "~/.nota/nota.db"

[llm]
# used in Phase 1 braindump
model = "claude-haiku-4-5-20251001"
# api_key read from ANTHROPIC_API_KEY env var
```

---

## Acceptance criteria for MVP

- [ ] `nota add "need to reply to pick n pull -> find stamps :: clean room"` creates:
  - Task: "need to reply to pick n pull" (project: inbox, status: todo)
  - Subtask: "find stamps" (parent_id → above task)
  - Task: "clean room" (created if not exists)
  - Relation: pick-n-pull reply ↔ clean room (related_to)
- [ ] `nota list` shows tasks sorted by priority then due date
- [ ] `nota show 1` shows task with subtasks and relations
- [ ] `nota done 1` marks task done and removes from default list
- [ ] `nota projects` shows project breakdown
- [ ] `nota mcp` starts MCP server, Claude Code can call `nota_list` and get results
- [ ] Database lives at `~/.nota/nota.db`, survives restarts

---

## Build order

1. `src/db.py` — schema and CRUD (30 min)
2. `src/parse.py` — inline syntax (20 min)
3. `bin/nota` + `src/cli.py` — CLI commands (45 min)
4. Test the acceptance criteria manually (15 min)
5. `src/mcp_server.py` — MCP wrapper (30 min)
6. Wire MCP into Claude Code config (15 min)

Total: ~2.5 hours

---

*maps · cassette.help · MIT*
