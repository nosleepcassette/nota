# Taskwarrior Findings — for nota pivot
**Source:** task 3.4.2 man page, read 2026-04-05
**Purpose:** Inform the pivot from custom SQLite backend to taskwarrior backend.
**TL;DR:** Taskwarrior already does ~80% of what nota's backend needs. We build the intelligent parsing layer on top. Do not reinvent the data model.

---

## What taskwarrior gives us for free

### Core data model — no need to build
- `description` — task title
- `project:name` — project assignment (hierarchical: `project:Home.Kitchen`)
- `priority:H|M|L` — three levels (we can map p1→H, p2→H, p3→M, p4→L)
- `due:DATE` — full natural language date parsing built in (today, tomorrow, eow, eom, eoy, friday, 3wks, etc.)
- `+tag -tag` — arbitrary tags, multiple per task
- `depends:ID,ID2` — first-class dependency support; automatically marks tasks as BLOCKED/BLOCKING
- `wait:DATE` — hide task until date (perfect for "waiting on" tasks)
- `scheduled:DATE` — date after which task becomes actionable
- `recur:FREQ` — recurring tasks (daily, weekly, monthly, etc.)
- `status:pending|completed|deleted|waiting|recurring`
- `annotations` — timestamped notes appended to tasks
- `entry`, `modified` — automatic timestamps

### Virtual tags — free filtering primitives
These exist as filter terms without explicit storage:
- `+BLOCKED` / `+BLOCKING` — dependency graph state
- `+READY` — actionable (unblocked, scheduled date past)
- `+UNBLOCKED`
- `+OVERDUE`, `+DUE`, `+TODAY`, `+TOMORROW`, `+WEEK`, `+MONTH`
- `+WAITING`, `+PENDING`, `+COMPLETED`
- `+ACTIVE` — currently started

### UDAs (User-Defined Attributes) — extend without patching
We can add custom fields without modifying taskwarrior:
```
task config uda.scope.type string
task config uda.scope.label Scope
task config uda.scope.values meatspace,digital,server,opencassette,appointment,waiting,creative,admin,errand
```
This gives us `scope:meatspace` as a native field queryable with all taskwarrior filters.

### Import/export JSON — agent interface
```bash
task export          # stdout: JSON array of all tasks
task import          # stdin: JSON array, creates/updates by UUID
task add description project:X due:tomorrow +tag depends:3,5
```
JSON export includes all fields including UDAs. This is the agentic interface — parse the dump, construct JSON, `task import`.

### Context — scoped sessions
```bash
task context define work project:Work
task context work      # all subsequent adds go to project:Work automatically
task context none
```
Useful for hermes sessions: "I'm in home mode" → `task context home` → all adds auto-tagged.

### `task next` — built-in urgency ranking
Taskwarrior computes urgency scores automatically factoring in: due date, priority, age, tags, blocking status. `task next` gives the top actionable items. This is a Todoist-equivalent "today" view for free.

### `task ready` — actionable only
Shows only unblocked, scheduled-past tasks. Perfect for "what can I actually do right now?"

### Hooks — automation integration
Scripts in `~/.task/hooks/` fire on events:
- `on-add` — runs when a task is created
- `on-modify` — runs on task changes
- `on-exit` — runs after any task command
Input: JSON task on stdin. Output: modified JSON on stdout + exit code.
This is how we'd push to Garden, send notifications, trigger hermes alerts.

### Helper commands for scripting
```bash
task +PENDING _unique project   # list all active projects
task +BLOCKED list              # what's blocked
task +BLOCKING list             # what's blocking others
task ID information             # all metadata for one task
task export                     # full JSON dump
task _get ID.due                # extract single field via DOM
```

---

## What we still need to build (nota's actual value-add)

### 1. Intelligent braindump parser (`braindump.py`)
Takes freeform text → LLM → structured JSON → `task import` or `task add` calls.

The LLM output maps directly to taskwarrior fields:
```json
[
  {
    "description": "reply to pick n pull",
    "project": "admin",
    "priority": "M",
    "tags": ["errand"],
    "uda_scope": "meatspace",
    "depends_descriptions": ["find stamps"],
    "related_descriptions": ["clean room"]
  }
]
```

Dependency resolution: LLM returns `depends_descriptions` (human-readable). We resolve to task IDs after insert.

### 2. Scope UDA setup (`setup.py`)
One-time config script that installs the scope UDA and any nota-specific contexts into `~/.taskrc`.

### 3. nota CLI wrapper (`bin/nota`)
Thin wrapper that:
- Passes `nota add "..."` through the inline parser then calls `task add`
- Provides `nota braindump "..."` for LLM parsing
- Provides `nota mcp` to start the MCP server
- Everything else delegates to `task` directly

### 4. MCP server (`mcp_server.py`)
Exposes taskwarrior ops as MCP tools. Tools call `task` subprocess and parse JSON output.

### 5. Hermes skill (`skills/nota/SKILL.md`)
Teaches hermes how to: add tasks via nota, braindump, query blocked tasks, use context.

---

## Key mapping: nota concepts → taskwarrior native

| nota concept | taskwarrior equivalent |
|---|---|
| `->` (depends on) | `depends:ID` |
| `::` (related to) | No native; use `+related-OTHERID` tag or annotation |
| `p1/p2/p3/p4` | `priority:H` / `priority:H` / `priority:M` / `priority:L` |
| `@project` | `project:name` |
| `#tag` | `+tag` |
| `scope:meatspace` | UDA `scope:meatspace` |
| `due:friday` | `due:friday` (native, already parsed) |
| `scope:waiting` | `wait:DATE` + `+waiting` tag |
| `scope:recurring` | `recur:weekly` etc. |
| subtask (parent/child) | `depends:PARENTID` on child OR `project:Parent.Sub` hierarchy |

**Note on `related_to`:** Taskwarrior has no native bidirectional relation. Best approach: mutual annotation or tag `+related-UUID`. Not critical for MVP — skip or use annotations.

---

## Architecture pivot

**Old plan:** Custom SQLite + Python CRUD + CLI + MCP

**New plan:**
```
taskwarrior (data store, CLI, urgency, deps, recurring, dates) ← already installed
    ↑ subprocess calls / JSON import-export
nota (Python)
├── setup.py        — install UDAs + nota contexts into ~/.taskrc
├── parse.py        — inline syntax → task add args (keep from existing src/parse.py)
├── braindump.py    — LLM → JSON → task import (Phase 1, high value)
├── mcp_server.py   — MCP stdio server wrapping task subprocess
└── bin/nota        — thin CLI wrapper
```

Drop `src/db.py` entirely — taskwarrior IS the database.

---

## Build order (revised)

1. **`src/setup.py`** — `nota setup` installs scope UDA into ~/.taskrc (~20 min)
2. **`bin/nota`** — rewrite as thin wrapper calling `task` subprocess; `nota add` maps parse.py output to `task add` args (~30 min)
3. **Smoke test** — `nota add "reply to pick n pull -> find stamps :: clean room"` → verify in `task list`
4. **`src/mcp_server.py`** — MCP server wrapping `task export`, `task add`, `task done`, `task next` (~45 min)
5. **`src/braindump.py`** — LLM parser (claude-haiku → task import) (~45 min)

---

## What to keep from current nota code

- `src/parse.py` — inline syntax parser is still useful as a pre-processing step before calling `task add`. Keep it.
- `bin/nota` — rewrite the command dispatch; the structure is right, just replace db calls with subprocess calls
- All docs (SCOPE.md, MVP.md, README.md, CHANGELOG.md) — update to reflect pivot

## What to drop

- `src/db.py` — replaced by taskwarrior entirely
- `requirements.txt` — remove sqlite dependency (it's stdlib); keep `mcp`

---

## Quick reference: task commands nota will call

```bash
# Add a task
task add "description" project:admin priority:M +tag scope:meatspace due:friday

# Add with dependency (must resolve IDs first)
STAMP_ID=$(task add "find stamps" +PENDING | grep -oP '(?<=task )\d+')
task add "reply to pick n pull" depends:$STAMP_ID

# List actionable tasks
task ready

# Export all for agent consumption
task export

# Mark done
task ID done

# Query blocked
task +BLOCKED list

# Query by scope UDA
task scope:meatspace list

# Import from JSON (braindump output)
echo '[{"description":"...","project":"home","priority":"H"}]' | task import
```

---

*Vesper — read taskwarrior 3.4.2 man page in full, 2026-04-05*
*Next session: implement pivot. Start with src/setup.py then bin/nota rewrite.*
