# nota — CHANGELOG
**Format:** Each step has a status marker. Update this file as you complete or begin work.
**For handoff agents:** Read this file first. Find the last `[IN PROGRESS]` or `[DONE]` entry. Resume from the next `[TODO]` step. Do not skip steps.

---

## Status markers
- `[DONE]` — completed, tested, working
- `[IN PROGRESS]` — started but not finished; notes below the entry explain current state
- `[TODO]` — not started yet
- `[BLOCKED]` — cannot proceed; reason noted

---

## PIVOT NOTE — 2026-04-05
**Decision:** Rebuild nota atop taskwarrior (already installed, `task` binary at 3.4.2) rather than maintaining a custom SQLite backend. Taskwarrior handles data model, deps, dates, urgency, recurrence natively. nota's value-add is the braindump/LLM parser + MCP server + hermes skill. Read `TASKWARRIOR_FINDINGS.md` before building. Drop `src/db.py`. Keep `src/parse.py`. Rewrite `bin/nota` as a thin wrapper calling `task` subprocess.

---

## Step 0 — Project scaffold
**Status:** `[DONE]`
Files created: `SCOPE.md`, `MVP.md`, `CHANGELOG.md`, `README.md`, `requirements.txt`, `src/__init__.py`, `src/db.py`, `src/parse.py`, `bin/nota`, `TASKWARRIOR_FINDINGS.md`

---

## Step 1 — Taskwarrior wrapper (`src/tw.py`)
**Status:** `[DONE]`

Thin subprocess wrapper around `task` binary. All taskwarrior calls go through here.
Functions: task_add, task_get, task_list, task_next, task_blocked, task_done, task_depend, task_annotate, task_projects, task_modify, task_import, fmt_row, fmt_detail, setup_udas.

---

## Step 2 — Setup + UDA installer (`src/setup.py`)
**Status:** `[DONE]`

`nota setup` installs scope UDA and nota contexts (meatspace, digital, server, waiting, blocked, ready) into ~/.taskrc. Idempotent.

Test: `nota setup` — should report all settings confirmed.

---

## Step 3 — CLI rewrite (`bin/nota`)
**Status:** `[DONE]`

Rewritten as taskwarrior-backed CLI. Commands: setup, add, list, next, blocked, show, done, depend, annotate, projects, mcp.
Inline syntax (parse.py) → taskwarrior field args. Dependencies via `task modify depends:ID`.
Related-to via mutual annotation (no native tw support).

Test:
```bash
nota add "need to reply to pick n pull -> find stamps :: clean room"
nota list          # find stamps, clean room, reply (blocked)
nota show 1        # shows depends_on: find stamps + annotation: related clean room
nota next          # reply NOT shown (blocked); find stamps shown
nota done 2        # complete find stamps
nota next          # reply NOW shown (unblocked)
```

---

## Step 4 — MCP server (`src/mcp_server.py`)
**Status:** `[DONE]`

10 tools: nota_add, nota_braindump (stub), nota_list, nota_next, nota_blocked, nota_show, nota_done, nota_depend, nota_annotate, nota_projects.

Registered in ~/.claude.json mcpServers as "nota". Restart Claude Code to activate.

nota_braindump is currently a passthrough to nota_add — full LLM parsing is Step 6.

---

## Step 5 — Hermes skill (`skills/nota/SKILL.md`)
**Status:** `[TODO]`

Write a SKILL.md file that a Hermes agent can load to understand how to use nota. See README.md for what the skill should cover. Copy the skill into `~/dev/hermetica/skills/nota/` or wherever hermes skills live on this system.

---

## Step 6 — Braindump LLM parser (`src/braindump.py`)
**Status:** `[TODO]`

Uses Anthropic API (claude-haiku-4-5) to parse freeform text into structured tasks. Called by `nota braindump "..."` and MCP tool `nota_braindump`.

Prompt contract: send text, receive JSON array of task objects. Each object has: title, body, project, scope, priority, due_date, subtasks (array of titles), related_titles (array of titles or IDs).

---

## Step 7 — Web UI
**Status:** `[TODO]` — Phase 3, not tonight

---

*Updated: 2026-04-05 — Vesper (claude-sonnet-4-6)*
