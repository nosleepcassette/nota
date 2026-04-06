# nota — scope document
**Project:** nota
**Owner:** maps · cassette.help
**Started:** 2026-04-05
**Status:** Pre-MVP

---

## What this is

A task management system built for the sextile/hermes agent ecosystem. The spiritual successor to Todoist for maps — not a general productivity tool, but a personal system designed around agent-first interaction and natural language input.

The core premise: **you should be able to dump anything — a grocery list, a life spiral, a work backlog, a single half-formed thought — and get back a structured, sorted, dependency-aware task list without touching a keyboard twice.**

---

## Primary interface

**Hermes agents** (spoken/chat, via hermetica-ios) are the primary users, both reading and writing. Everything else is secondary. A task system that requires a GUI to use has already failed.

Secondary interfaces (in priority order):
1. MCP server — exposes nota tools to Claude Code, Codex, Gemini, any MCP-capable agent
2. CLI — `nota` binary, direct terminal use
3. Web UI — later, nginx-served, standalone
4. hermetica-ios — native app or webview, accessed from phone

---

## Philosophy

Todoist's strengths:
- Natural language date/priority parsing ("buy milk tomorrow p1")
- Projects as first-class organizing unit
- Quick capture above all else
- Subtask + dependency model

What nota adds:
- **Scope tagging** — not all tasks live in the same world. `meatspace` (physical action needed), `digital` (something on a computer), `server` (sextile-local), `opencassette` (the opencassette server), `appointment` (time-bound external obligation), `recurring`, `waiting` (blocked on someone else), `creative`, `admin`, `errand`
- **Dependency syntax** — first-class `depends_on`, `blocks`, `related_to` relations between tasks
- **Agent-native braindump parsing** — route a dump through LLM to produce structured tasks automatically
- **Garden integration** — optionally sync to/from the cassette knowledge graph for agent recall
- **Context-aware recall** — agents can query "what's blocking X" or "what's due this week in meatspace" in natural language

---

## Data model (v1)

### tasks
| field | type | notes |
|-------|------|-------|
| id | integer PK | auto-increment |
| title | text | the task, short |
| body | text | notes, details, context |
| project | text | inferred or explicit |
| scope | text | meatspace\|digital\|server\|opencassette\|appointment\|recurring\|waiting\|creative\|admin\|errand |
| priority | integer | 1 (urgent) – 4 (someday); default 3 |
| due_date | text | ISO 8601 date or null |
| status | text | todo\|in_progress\|done\|cancelled |
| parent_id | integer FK | subtask of another task |
| created_at | integer | unix timestamp |
| updated_at | integer | unix timestamp |

### task_relations
| field | type | notes |
|-------|------|-------|
| task_id | integer FK | source task |
| related_id | integer FK | target task |
| relation_type | text | depends_on\|blocks\|related_to\|part_of |

### task_tags
| field | type | notes |
|-------|------|-------|
| task_id | integer FK | |
| tag | text | freeform |

---

## Natural language syntax (inline shorthand)

For quick CLI/agent input without LLM parsing:

```
task title ->subtask title       # subtask (depends_on in context)
task title ->another thing       # multiple subtasks via repeated ->
task A :: task B                 # related_to (bidirectional)
task title p1                    # priority 1
task title @project-name         # assign to project
task title #tag                  # add tag
task title due:friday            # due date (natural language parsed locally)
task title scope:meatspace       # explicit scope
```

Example from user:
```
need to reply to pick n pull -> find stamps :: clean room
```
Parses to:
- Task: "need to reply to pick n pull" (project: admin, scope: meatspace)
  - Subtask: "find stamps" (depends_on: reply to pick n pull)
  - Related: "clean room" (task lookup or create)

---

## Braindump flow

1. User sends any freeform text to hermes (or `nota braindump "..."`)
2. nota sends text to LLM (claude-haiku-4-5 for cost, configurable) with structured prompt
3. LLM returns JSON array of task objects with inferred fields
4. nota validates + inserts, reports back summary ("created 7 tasks across 3 projects")
5. User can review, edit, or immediately query the result

---

## Architecture (target)

```
nota-core (Python)
├── db.py          — SQLite model + migrations
├── parse.py       — inline syntax parser (no LLM)
├── braindump.py   — LLM-assisted parsing
├── query.py       — query/filter/sort logic
└── mcp.py         — MCP server (stdio transport)

bin/
└── nota           — CLI entrypoint

config:
~/.nota/config.toml  — db path, LLM model, API keys
~/.nota/nota.db      — default database
```

---

## Phases

### Phase 0 — MVP (tonight, ~2-4 hours)
SQLite + CLI + inline syntax parser + MCP server. No LLM. No web UI. Just: works, stores, queries, exposes to agents. See MVP.md.

### Phase 1 — Braindump (next session)
LLM parsing via claude-haiku or hermes. Bulk import. Handles the "here's everything in my brain" use case.

### Phase 2 — MCP polish + agent UX
Hermes-native natural language queries. "What do I need to do before I can reply to Pick n Pull?" → nota traverses dependency graph and answers.

### Phase 3 — Web interface
nginx-served, lightweight. Single-page, mobile-friendly. No framework overhead. Plain HTML + htmx or similar. Auth via shared secret for now.

### Phase 4 — Sync / export
Garden graph sync (optionally surface tasks as knowledge). Caldav/iCal export for appointments. Obsidian markdown export.

---

*maps · cassette.help · MIT*
