# nota
**maps · cassette.help · MIT**

A task management system for the sextile/hermes agent ecosystem. Natural language input, dependency-aware, agent-first.

---

## Quick start

```bash
cd ~/dev/nota
pip install -r requirements.txt
chmod +x bin/nota
export PATH="$PATH:$HOME/dev/nota/bin"

nota add "reply to pick n pull -> find stamps :: clean room"
nota list
nota show 1
```

---

## For hermes agents: how to build a skill around this

Point your agent at this file. The skill should wrap these CLI commands as verbs:

| Verb | CLI | What it does |
|------|-----|--------------|
| add task | `nota add "title [options]"` | Create a task with optional inline syntax |
| list tasks | `nota list [--project X] [--scope X] [--priority N]` | Show open tasks |
| show task | `nota show ID` | Full task detail with subtasks and relations |
| complete task | `nota done ID` | Mark task done |
| link tasks | `nota link ID --depends-on ID2` or `--related-to ID2` | Add relation |
| list projects | `nota projects` | Show all projects with task counts |
| start MCP | `nota mcp` | Start MCP stdio server (for agent tool use) |

The skill should understand:
- Tasks have dependencies: "I can't do X until Y is done" → `nota add "X -> Y"`
- Tasks have relations: "X is related to Y" → `nota add "X :: Y"` or `nota link X --related-to Y`
- Projects are just strings: `@admin`, `@home`, `@server`, `@cassette`, etc.
- Scopes: `scope:meatspace` (physical), `scope:digital`, `scope:server`, `scope:appointment`, `scope:waiting`
- Priority: `p1` (do now) through `p4` (someday)

**Braindump handling (Phase 1, not yet built):** When a user says "here's everything on my mind," capture the whole text and call `nota braindump "..."`. This will be available once `src/braindump.py` is implemented (see CHANGELOG.md Step 6).

---

## Inline syntax

```
task title                              # basic task
task title p1                           # priority 1 (urgent)
task title @project-name                # assign to project
task title #tag1 #tag2                  # tags
task title scope:meatspace              # scope
task title due:2026-04-10               # due date
task title -> subtask                   # add subtask (you CANNOT do task until subtask is done)
task A :: task B                        # task A is related to task B
task title p2 @admin -> find stamps :: clean room  # combined
```

### Dependency direction (important)
`parent -> child` means **parent depends on child**. You cannot complete the parent until the child is done. Child is the prerequisite.

Example: `"reply to pick n pull -> find stamps"` means:
- Cannot reply until stamps are found
- "find stamps" must be completed first

---

## MCP tools (once `nota mcp` is running)

```
nota_add         Add a task
nota_list        List open tasks
nota_show        Get full task detail
nota_done        Mark a task complete
nota_link        Add a relation between two tasks
nota_projects    List projects with counts
nota_braindump   (Phase 1) Parse freeform text into tasks
```

Add to `~/.claude.json` mcpServers:
```json
"nota": {
  "command": "/Users/maps/dev/nota/bin/nota",
  "args": ["mcp"]
}
```

---

## Data lives at

`~/.nota/nota.db` — SQLite. Safe to back up, copy, inspect with any SQLite tool.

Override: `export NOTA_DB=/path/to/other.db`

---

## Project structure

```
nota/
├── README.md           ← you are here
├── SCOPE.md            ← full vision + data model + phase roadmap
├── MVP.md              ← step-by-step build instructions (codex-readable)
├── CHANGELOG.md        ← build progress; read this to resume after handoff
├── requirements.txt
├── bin/
│   └── nota            ← CLI entrypoint
└── src/
    ├── db.py           ← SQLite schema + CRUD
    ├── parse.py        ← inline syntax parser
    ├── mcp_server.py   ← MCP stdio server (Step 4)
    └── braindump.py    ← LLM parser (Step 6)
```

---

## Build status

See `CHANGELOG.md` for current completion state. If handed off mid-build, read CHANGELOG.md first.

---

*maps · cassette.help · MIT*
