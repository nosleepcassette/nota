# nota
**maps · cassette.help · MIT**

A task management system for the sextile/hermes agent ecosystem. Natural language input, dependency-aware, agent-first.

---

## Quick start

```bash
cd ~/dev/nota
pip install -r requirements.txt
make dev          # creates ~/.bin/nota symlink (run once)

nota add "reply to pick n pull -> find stamps :: clean room"
nota list
nota show 1
nota bene         # TUI
notadash          # tmux dashboard with nota bene + taskwarrior panes
```

No rebuild needed after edits — `bin/nota` runs directly from source via symlink.

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

Works in `nota add` (CLI) **and** the TUI `a` prompt. Freeform sentences are auto-routed through NLP; structured syntax goes through the inline parser.

```
task title                              # basic task
task title p1                           # priority 1 (urgent)
task title @project-name                # assign to project
task title #tag1 #tag2                  # tags
task title scope:meatspace              # scope
task title due:tomorrow                 # due date (taskwarrior natural language)
task title due:eow                      # end of week
task title due:friday                   # named day
task title -> subtask                   # prereq: cannot complete task until subtask is done
task A :: task B                        # related-to link
task title p2 @admin -> find stamps :: clean room  # combined
```

**Priority levels:** `p1` = urgent (H), `p2` = high (H), `p3` = medium (M), `p4` = low (L)

**Scopes:** `meatspace` · `digital` · `server` · `appointment` · `waiting` · `anywhere`

### Dependency direction
`parent -> child` means **parent depends on child**. Cannot complete parent until child is done.

`"reply to pick n pull -> find stamps"` → cannot reply until stamps are found.

### NLP freeform (via Gemini 2.0 Flash)
If input has no syntax tokens and is 4+ words, it's routed to the LLM:

```
nota add "call the dentist sometime next week"
# → project:inbox, due:next week, inferred priority
```

Works in both CLI and TUI `a` prompt. Requires `GEMINI_API_KEY` in env.

---

## nota bene TUI

Key highlights:

```
e        smart edit panel — h/l or ←/→ between fields; j/k between options;
         tab to focus text input; enter to commit; m for $EDITOR fallback
m        manual edit in $EDITOR
ctrl+f   fuzzy search — matches description, project, tags, annotations
         j/k to navigate results; enter to jump; esc to cancel
←/→      switch pending/completed views; in detail view, previous/next task
x / B    select tasks / batch selected tasks
```

The table shows due countdowns, task details include notes and dependency titles,
and sort order is persisted in `~/.config/nota/tui_state.json`.

---

## Mobile push notifications

`nota cron-check` checks for pending tasks due soon and can POST them to a push
webhook. The included launchd agent runs every 30 minutes and checks for tasks
due within 2 hours:

```bash
nota cron-check --minutes 120 --push-url "$NOTA_PUSH_URL"
```

Set up an iOS Shortcut with a URL Session automation trigger:

```
Trigger: Receives URL from webhook POST
Action: Show notification with task descriptions
```

Or use a Pushover/ntfy URL as `NOTA_PUSH_URL` for zero-config push.

---

## notadash

`nota bene` + taskwarrior tmux dashboard:

```bash
notadash
```

Layout: burndown · `nota bene` interactive TUI · `task next`/`task overdue` · calendar.

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


<!-- BEGIN INJECT:gofundme -->
---

## support this work

maps is currently navigating severe financial precarity and is at real risk of losing her housing. if this project has been useful to you — or you just think what she's building is worth keeping alive — please consider throwing a few dollars her way.

<div align="center">

<a href="https://www.gofundme.com/f/support-needed-for-unexpected-expenses-brn6h">
  <img src="https://img.shields.io/badge/GoFundMe-support%20maps-00b964?style=for-the-badge&logo=gofundme&logoColor=white" alt="GoFundMe — support maps">
</a>

**[→ gofundme.com/f/support-needed-for-unexpected-expenses-brn6h](https://www.gofundme.com/f/support-needed-for-unexpected-expenses-brn6h)**

</div>

[ko-fi.com/nosleepcassette](https://ko-fi.com/nosleepcassette) · venmo: **@keaghoul** · cashapp: **$keaghoul** · [cassette.help](https://cassette.help)
<!-- END INJECT:gofundme -->
---

## support this work

maps is currently navigating severe financial precarity and is at real risk of losing her housing. if this project has been useful to you — or you just think what she's building is worth keeping alive — please consider throwing a few dollars her way. it goes directly toward keeping the lights on.

[ko-fi.com/nosleepcassette](https://ko-fi.com/nosleepcassette) · venmo: **@keaghoul** · cashapp: **$keaghoul** · [cassette.help](https://cassette.help)

<!-- cassette.help/donate -->
