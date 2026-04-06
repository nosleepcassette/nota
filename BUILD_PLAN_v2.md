# nota v2.0 — Build Plan

**Based on:** Scope Document v2.0 + PRD v2.0
**Priority:** Tasks first, habits second

---

## Phase A: Core Infrastructure

**Goal:** Local NL date parsing, config/scopes, task modification, basic filtering

### A1: Local Date Parsing (`dateparse.py`)
- [ ] Install `dateparser` library
- [ ] Create `src/dateparse.py`
  - `parse_date(input: str) → str | None`
  - Handle TW shortcuts: today, tomorrow, eod, eow, eom, eoq
  - Use dateparser for NL dates
  - Return None on parse failure
- [ ] Integrate into `parse.py`
  - Parse `due:...` tokens through dateparse
  - Fall back to store-as-is on None
- [ ] Test: 20+ date patterns

### A2: Config & Scopes
- [ ] Create `src/config.py`
  - Load `~/.nota/nota.toml`
  - Defaults: db path, default project, etc.
- [ ] Create `src/scopes.py`
  - Load default scopes (10)
  - Merge user scopes from `nota.toml` `[scopes]` section
  - `list_scopes() → [(name, emoji?, desc?)]`
  - `add_scope(name)`, `rm_scope(name)`
- [ ] Create `~/.nota/` dir if not exists
- [ ] Create default `~/.nota/nota.toml` if not exists
- [ ] Update `parse.py` to use dynamic scope list

### A3: Task Modification (`nota edit`)
- [ ] Add `nota edit ID [flags]` command
- [ ] Flags: `--title`, `--project`, `--priority`, `--due`, `--scope`, `--add-tag`, `--rm-tag`, `--body`
- [ ] Call `task_modify()` from tw.py
- [ ] Add `nota_modify` MCP tool

### A4: Basic Filtering (`nota find`)
- [ ] Create `src/query.py`
  - `build_filter(args) → str` (taskwarrior expression)
  - Custom filters: `--overdue`, `--due-this-week`, `--unblocked`, `--has-annotation`
- [ ] Add `nota find [expression]` command
- [ ] Add `nota_find` MCP tool

**A Complete Criteria:**
- `nota add "task due:friday"` stores ISO
- `nota scopes` lists all scopes
- `nota edit 1 --project admin` works
- `nota find --overdue` works

---

## Phase B: Bulk & Relations

### B1: Bulk Operations
- [ ] Extend `nota done` to accept multiple IDs: `nota done 1 2 3`
- [ ] Add `--project`, `--scope`, `--filter` flags to done
- [ ] Add `nota move` command: `nota move ID(s) --project X`
- [ ] Add `nota tag` command: `nota tag ID(s) --add X --rm Y`
- [ ] Add `nota_bulk_done` MCP tool

### B2: Relations Overhaul
- [ ] Change relation storage: `+related:TARGET_ID` tags
- [ ] Add `nota relate ID --to ID2` command
- [ ] Add `nota relate ID --blocks ID2` command
- [ ] Add `nota relate ID --subtask ID2` command
- [ ] Add `nota related ID` command (query +related:ID)
- [ ] Add `nota_related` MCP tool

### B3: Dependency Visualization
- [ ] Add `nota tree ID` command
  - Traverse depends chain
  - Render as ASCII tree
- [ ] Add `nota graph ID` command (DOT export)
- [ ] Add `nota_tree` MCP tool

**B Complete Criteria:**
- `nota done 1 2 3` completes three tasks
- `nota relate 1 --to 2` creates queryable relation
- `nota tree 5` shows blocking chain

---

## Phase C: Recurring & Scheduling

### C1: Recurring Tasks
- [ ] Add `--recur` flag to `nota add`
  - Values: daily, weekly, biweekly, monthly, quarterly, annual
- [ ] Add `--until DATE` flag for end date
- [ ] Add `nota recur ID` (show recurrence)
- [ ] Add `nota recur ID --modify DAILY` (change)
- [ ] Add `nota recur ID --stop` (stop)
- [ ] Add `nota recurring` command (list parents)
- [ ] Add `nota_recurring` MCP tool

### C2: Wait/Scheduled Dates
- [ ] Add `--wait` flag to `nota add` (hidden until)
- [ ] Add `--scheduled` flag to `nota add` (actionable after)
- [ ] Add `nota waiting` command (status:waiting)
- [ ] Add `nota scheduled` command (scheduled > now)
- [ ] Add `nota_waiting`, `nota_scheduled` MCP tools

### C3: Additional List Views
- [ ] `nota all` — all statuses
- [ ] `nota completed` — done tasks
- [ ] `nota deleted` — deleted tasks
- [ ] `nota waiting` (from C2)
- [ ] `nota scheduled` (from C2)

**C Complete Criteria:**
- `nota add "task" --recur daily` creates recurring
- `nota add "task" --wait friday` works
- `nota waiting` lists hidden tasks

---

## Phase D: Habits+

### D1: Habit Stats
- [ ] Extend `nota habits --stats`
  - Current streak per habit
  - Longest streak
  - Last completed date
  - Completion rate (%)
- [ ] Add `nota habit NAME --stats` (single habit)
- [ ] Add `nota habit NAME --streak` (just streak)
- [ ] Add `nota habit NAME --history` (last 30 days)

### D2: Habit Analytics
- [ ] Add `nota habits --weekly` (week summary)
- [ ] Add `nota habits --monthly` (month summary)
- [ ] Add `nota habits --chart NAME` (text bar chart)
- [ ] Add `nota_habit_stats`, `nota_habit_history` MCP tools

### D3: Habit Reminders
- [ ] Add `nota reminder add NAME --time HH:MM`
- [ ] Add `nota reminder list`
- [ ] Add `nota reminder rm NAME`
- [ ] Simple cron generation (write to crontab)

**D Complete Criteria:**
- `nota habits --stats` shows streaks
- `nota habits --weekly` shows summary
- `nota reminder add "water plants" --time 09:00` works

---

## Phase E: TUI (`nota bene`)

### E1: Setup
- [ ] Install `textual` library
- [ ] Create `src/tui/` directory
- [ ] Create basic `app.py` with App class

### E2: Task List View
- [ ] Render task list in main pane
- [ ] Color coding: priority (red/yellow/green)
- [ ] Show ID, description, project, due, scope, tags

### E3: Task Detail View
- [ ] Show full task on selection
- [ ] Show annotations, dependencies, relations

### E4: Habit Panel
- [ ] Show today's habits
- [ ] Show streaks
- [ ] Allow quick toggle

### E5: Navigation & Input
- [ ] j/k or arrow keys for navigation
- [ ] enter to view detail
- [ ] a to add task
- [ ] / to search
- [ ] q to quit
- [ ] Quick-add input at bottom

### E6: Polish
- [ ] Help overlay (?)
- [ ] Filter bar (p for project, s for scope)
- [ ] Status messages

**E Complete Criteria:**
- `nota bene` launches TUI
- Can navigate tasks with j/k
- Can view detail with enter
- Can quit with q
- Habits panel shows streaks

---

## Implementation Order (by file)

```
src/dateparse.py       (NEW)
src/config.py          (NEW)
src/scopes.py          (NEW)
src/query.py           (NEW)
bin/nota               (ADD edit, find, move, tag, tree, graph, relate, related, recur, waiting, scheduled, reminder)
src/cli.py             (ADD commands)
src/parse.py           (MODIFY use dateparse, scopes)
src/tw.py              (MODIFY add task_waiting, task_scheduled, task_recurring)
src/mcp_server.py      (ADD tools)
src/tui/               (NEW directory)
src/tui/__init__.py    (NEW)
src/tui/app.py         (NEW)
src/tui/views.py       (NEW)
src/tui/widgets.py     (NEW)
src/tui/keymap.py      (NEW)
```

---

## Testing Checklist

### Per-Phase Testing
- [ ] Unit: dateparse patterns
- [ ] Unit: scope loading
- [ ] Integration: CLI commands
- [ ] Integration: MCP tools

### Regression Testing
- [ ] `nota add "task"` still works
- [ ] `nota list` still works
- [ ] `nota done ID` still works
- [ ] `nota braindump` still works
- [ ] `nota log "habit"` still works

---

## Dependencies to Add

```txt
# requirements.txt
dateparser>=43.0
textual>=0.80
```

---

## Notes

- All MCP tool additions should return JSON-serializable results
- CLI output should be human-readable by default, `--json` for machine
- TUI (`nota bene`) is separate entrypoint, not controlled via MCP
- User scopes stored in `~/.nota/scopes`, config in `~/.nota/nota.toml`

---

*End of Build Plan*
