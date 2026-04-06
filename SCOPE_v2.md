# nota — Comprehensive Scope Document
**Version:** 2.0 (Major Upgrade)
**Owner:** maps · cassette.help
**Status:** Draft for PRD

---

## 1. Project Vision

**nota** is a unified personal productivity CLI that wraps **taskwarrior** (task management) and **harsh** (habit tracking) into a single cohesive system. It serves as the backend for the sextile/hermes agent ecosystem, providing natural language input, dependency-aware task management, and habit/lifestyle tracking.

The v2.0 upgrade brings nota from MVP to full-featured productivity system with:
- Full taskwarrior feature parity
- Local natural language date parsing (no LLM required)
- Rich terminal UI via `nota bene`
- User-defined scopes
- Deep habit analytics
- Bulk operations and advanced filtering

---

## 2. Architecture Overview

```
nota/
├── bin/
│   ├── nota              # CLI entrypoint (default)
│   └── bene              # TUI entrypoint (new)
├── src/
│   ├── __init__.py
│   ├── tw.py             # taskwarrior wrapper (existing, expand)
│   ├── harsh.py          # harsh interface (existing, expand)
│   ├── parse.py          # inline syntax parser (existing)
│   ├── cli.py            # CLI command handlers (existing)
│   ├── mcp_server.py     # MCP stdio server (existing)
│   ├── braindump.py      # LLM parser (existing)
│   ├── dateparse.py      # NEW: local NL date parsing
│   ├── query.py          # NEW: advanced filtering/search
│   ├── tui/              # NEW: TUI components
│   │   ├── __init__.py
│   │   ├── app.py        # bene TUI main
│   │   ├── views.py      # view renderers
│   │   ├── widgets.py    # custom widgets
│   │   └── keymap.py     # keybindings
│   ├── config.py         # NEW: config management
│   └── scopes.py         # NEW: user-defined scopes
├── config/
│   └── nota.toml         # NEW: user config
├── docs/
│   └── SPEC.md           # This file (detailed spec)
├── CHANGELOG.md
├── README.md
└── requirements.txt
```

---

## 3. Data Model

### 3.1 Taskwarrior Integration (unchanged)
nota uses taskwarrior as the backend. All task data lives in taskwarrior's data store. Custom UDAs extend the base schema.

### 3.2 Custom UDAs
| UDA | Type | Values | Purpose |
|-----|------|--------|---------|
| scope | string | user-defined + defaults | Context domain |

### 3.3 Scope System (v2.0)
Default scopes (maintained for compatibility):
- `meatspace` — physical actions, real-world tasks
- `digital` — computer/online tasks
- `server` — sextile/system admin tasks
- `opencassette` — opencassette server tasks
- `appointment` — time-bound external obligations
- `recurring` — recurring tasks
- `waiting` — blocked on external response
- `creative` — creative work
- `admin` — administrative tasks
- `errand` — quick errands

**New:** User-defined scopes stored in `~/.nota/nota.toml`.

### 3.4 Habit Data (unchanged)
Harsh stores data in:
- `~/.config/harsh/habits` — habit definitions
- `~/.config/harsh/log` — daily logs

---

## 4. Feature Specifications

### 4.1 Natural Language Date Parsing

**Problem:** Currently `due:friday` is stored as literal "friday". Taskwarrior parses some dates, but not all natural language.

**Solution:** Local `dateparser` library to convert NL dates to ISO before passing to taskwarrior.

**Implementation:**
```python
# src/dateparse.py
import dateparser

def parse_date(input: str) -> str | None:
    """
    Parse natural language date to ISO 8601.
    'friday' → '2026-04-10'
    'next monday' → '2026-04-13'
    'in 3 days' → '2026-04-09'
    'eom' → '2026-04-30'
    'eow' → '2026-04-10'
    """
    # Handle taskwarrior shortcuts first
    shortcuts = {
        "today": "today",
        "tomorrow": "tomorrow", 
        "eod": "today",
        "eow": "eow",
        "eom": "eom",
        "eoq": "eoq",
    }
    if input.lower() in shortcuts:
        return shortcuts[input.lower()]
    
    # Use dateparser for everything else
    parsed = dateparser.parse(input, settings={"STRICT_PARSING": False})
    if parsed:
        return parsed.strftime("%Y-%m-%d")
    return None
```

**Integration:**
- Parse `due:...` tokens in `parse.py` before storing
- Parse on output for display (show, list, next)
- Support in inline syntax: `due:next friday`, `due:in 2 weeks`

**Commands affected:** `add`, `braindump`, `show`, `list`, `next`

---

### 4.2 Task Modification

**Problem:** No way to edit existing tasks.

**Solution:** Add `nota edit` command and `nota_modify` MCP tool.

**CLI:**
```
nota edit ID                    # interactive editor (vim/nano)
nota edit ID --title "new title"
nota edit ID --project admin    # change project
nota edit ID --priority p1      # change priority
nota edit ID --due 2026-04-10   # change due date
nota edit ID --scope meatspace  # change scope
nota edit ID --add-tag urgent    # add tag
nota edit ID --rm-tag old       # remove tag
nota edit ID --body "notes"     # add/edit annotation
```

**MCP tool:**
```python
nota_modify(id: int, title?, project?, priority_p?, due?, scope?, tags_add?, tags_remove?, body?)
```

---

### 4.3 Bulk Operations

**Problem:** Can only operate on one task at a time.

**Solution:** Add bulk command variants.

**CLI:**
```
nota done 1 2 3 4              # done multiple IDs
nota done --project admin      # done all in project
nota done --scope waiting      # done all in scope
nota move 1 2 3 --project home # move to project
nota tag 1 2 3 --add urgent    # bulk tag
nota done --due before:today   # done all overdue
```

**Implementation:** Parse multiple IDs or filter expressions, then iterate.

---

### 4.4 Advanced Filtering & Search

**Problem:** Limited to project/scope/priority filters.

**Solution:** Add `query` module with full taskwarrior filter syntax + custom extensions.

**CLI:**
```
nota find "urgency > 10"                    # taskwarrior expressions
nota find "due before:tomorrow +urgent"   # combined
nota find --scope meatspace --overdue      # pre-built filters
nota find --regex ".*stamps.*"              # regex search
nota find --has-annotation                 # has notes
nota find --blocked                         # is blocked
nota find --blocking                        # is blocking others
```

**Query Language:**
- All taskwarrior expressions pass through
- Custom filters:
  - `--overdue` → `due < today`
  - `--due-this-week` → `due <= eow`
  - `--unblocked` → `not depends:`
  - `--has-annotation` → `has:annotation`

---

### 4.5 Dependency Visualization

**Problem:** No way to see dependency trees.

**Solution:** Add `nota tree` command and visual rendering.

**CLI:**
```
nota tree ID                 # show blocking tree for task ID
nota tree --project admin   # show full dependency graph for project
nota graph ID               # ASCII art graph
```

**Output:**
```
[5] reply to pick n pull
└── [2] find stamps (prerequisite)
    └── [1] buy stamps (prerequisite)

[6] clean room
```

**Implementation:** Traverse taskwarrior's `depends` field, render as tree.

---

### 4.6 Relations Overhaul

**Problem:** Related tasks stored only as annotations, not queryable.

**Solution:** Store relations in dedicated UDA or use taskwarrior tags.

**Approach:** Use `+related:TARGET_ID` tags for machine-queryable relations.

**CLI:**
```
nota relate 1 --to 2         # create related relation
nota relate 1 --blocks 2    # create blocks relation
nota relate 1 --subtask 2   # create subtask relation
nota related 1              # show all related tasks
nota related 1 --blocks     # show blockers
nota related 1 --blocked-by # show blocked by
```

**Query:** `nota find "+related:1"` or `nota find "tags.contains('related:1')"`

---

### 4.7 Recurring Tasks

**Problem:** Not implemented.

**Solution:** Leverage taskwarrior's native recurrence, add convenience syntax.

**CLI:**
```
nota add "water plants" --recur daily
nota add "call mom" --recur weekly
nota add "pay rent" --recur monthly
nota add "review" --recur biweekly
nota add "standup" --recur daily --until 2026-12-31

# Full TW syntax also supported:
nota add "task" --recur "days:2"
nota add "task" --recur "weekdays"
```

**Recur formats (CLI convenience):** daily, weekly, monthly, biweekly, quarterly, annual

**Internal:** Maps to full taskwarrior recurrence: `daily` → `rdaily`, `weekly` → `rweekly`, etc. Users can also pass full TW syntax directly.

**Commands:**
```
nota recur ID                # show recurrence for task
nota recur ID --modify daily # change recurrence
nota recur ID --stop        # stop recurrence
nota recurring              # list all recurring parent tasks
```

---

### 4.8 Wait/Scheduled Dates

**Problem:** Not exposed in CLI.

**Solution:** Add `--wait` and `--scheduled` flags.

**CLI:**
```
nota add "follow up" --wait 2026-04-15    # hidden until date
nota add "check in" --scheduled tomorrow  # becomes actionable after date
nota waiting                             # list waiting tasks
nota scheduled                           # list scheduled tasks
```

---

### 4.9 User-Defined Scopes

**Problem:** 10 hardcoded scopes.

**Solution:** Load user scopes from config file.

**Config:** `~/.nota/nota.toml`
```toml
[scopes]
# User-defined scopes
# Format: scope_name = "emoji description"
work = "💼 Work-related tasks"
health = "🏃 Health and fitness"
finance = "💰 Financial tasks"
```
```

**CLI:**
```
nota scopes                  # list all scopes
nota scopes --add work      # add scope
nota scopes --rm work      # remove scope
nota list --scope work     # filter by custom scope
```

**Implementation:**
- Store in `src/scopes.py`
- Load user scopes from `nota.toml` `[scopes]` section
- Merge default + user scopes on load
- Validate in parse.py

---

### 4.10 Rich Terminal UI (`nota bene`)

**Problem:** Plain text output.

**Solution:** Build TUI using `textual` library.

**Entrypoint:** `nota bene` (nota bene = "note well" = pay attention)

**Features:**
- Split panes: task list | detail | habits
- Color-coded priority (red/yellow/green)
- Keyboard navigation (j/k, enter, Esc)
- Real-time filtering
- Habit streak visualization
- Quick-add input at bottom

**Keybindings:**
```
j/k or arrows    navigation
enter            view detail
a                add task
d                done task
e                edit task
/                search
p                filter by project
s                filter by scope
?                help
q                quit
```

**Architecture:**
```
nota bene
├── app.py          # Main app, layout
├── views/
│   ├── task_list   # main task pane
│   ├── task_detail # selected task detail
│   ├── habit_panel # habit status
│   └── help        # help overlay
├── widgets/
│   ├── task_row    # individual task
│   ├── streak      # habit streak
│   └── filter_bar  # quick filters
└── keymap.py       # keybindings
```

---

### 4.11 Habit Improvements

#### 4.11.1 Better Habit Stats
```
nota habits --stats              # show streaks, frequencies
nota habit water --stats         # single habit stats
nota habit water --streak        # current streak only
nota habit water --history       # last 30 days
```

**Output:**
```
── habits · 2026-04-06 ─────────────────────────
  ✓  watered plants    streak: 12   last: today
  ✗  meditated         streak: 3    last: 2026-04-04
  ~  smoked cigarette streak: --    today: 4  total: 127

  Current streak leaders:
    1. watered plants (12)
    2. took vitamins (7)
    3. meditated (3)
```

#### 4.11.2 Habit Analytics
```
nota habits --weekly             # weekly summary
nota habits --monthly           # monthly summary
nota habits --chart water       # text bar chart
```

**Output:**
```
── water plants · April 2026 ──────────────────
Mon ✗  Tue ✗  Wed ✓  Thu ✓  Fri ✓  Sat ✓  Sun ✓
████████░░░░░░░░░░░░  6/7 completion (86%)
```

#### 4.11.3 Daily Habit Reminders
```
nota reminder add "water plants" --time 09:00
nota reminder list
nota reminder rm "water plants"
```

**Implementation:** Simple cron wrapper or systemd timer.

---

## 5. MCP Tool Additions

New/changed MCP tools for v2.0:

| Tool | Description | New |
|------|-------------|-----|
| nota_modify | Modify existing task fields | NEW |
| nota_bulk_done | Mark multiple tasks complete | NEW |
| nota_find | Advanced search/filter | NEW |
| nota_tree | Dependency tree | NEW |
| nota_related | Query related tasks | NEW |
| nota_recurring | List recurring tasks | NEW |
| nota_waiting | List waiting tasks | NEW |
| nota_scheduled | List scheduled tasks | NEW |
| nota_scopes | Manage scopes | NEW |
| nota_habit_stats | Habit statistics | NEW |
| nota_habit_history | Habit history | NEW |
| nota_bene | Launch TUI (not MCP) | NEW |

---

## 6. CLI Command Matrix

| Command | Status | Description |
|---------|--------|-------------|
| `nota setup` | existing | Install UDAs |
| `nota add` | existing | Add task(s) |
| `nota list` | existing | List tasks |
| `nota next` | existing | Urgent tasks |
| `nota blocked` | existing | Blocked tasks |
| `nota show` | existing | Task detail |
| `nota done` | existing | Complete task |
| `nota depend` | existing | Set dependency |
| `nota annotate` | existing | Add note |
| `nota projects` | existing | Project list |
| `nota braindump` | existing | LLM parse |
| `nota track` | existing | Habit done |
| `nota log` | existing | Countable habit |
| `nota did` | existing | Alias track |
| `nota habits` | existing | Habit status |
| `nota mcp` | existing | MCP server |
| `nota edit` | NEW | Modify task |
| `nota move` | NEW | Change project |
| `nota tag` | NEW | Bulk tag |
| `nota find` | NEW | Search/filter |
| `nota tree` | NEW | Dependency tree |
| `nota graph` | NEW | ASCII graph |
| `nota relate` | NEW | Manage relations |
| `nota related` | NEW | Query relations |
| `nota recur` | NEW | Manage recurring |
| `nota recurring` | NEW | List recurring |
| `nota waiting` | NEW | Waiting tasks |
| `nota scheduled` | NEW | Scheduled tasks |
| `nota scopes` | NEW | Manage scopes |
| `nota reminder` | NEW | Habit reminders |
| `nota bene` | NEW | Launch TUI |

---

## 7. Acceptance Criteria

### 7.1 Date Parsing
- [ ] `nota add "task due:friday"` stores ISO date
- [ ] `nota show` displays parsed date in human form
- [ ] `nota add "task due:next monday"` works
- [ ] `nota add "task due:in 2 weeks"` works

### 7.2 Task Modification
- [ ] `nota edit 1 --title "new title"` updates task
- [ ] `nota edit 1 --project admin` moves task
- [ ] `nota edit 1 --add-tag urgent` adds tag

### 7.3 Bulk Operations
- [ ] `nota done 1 2 3` completes all three
- [ ] `nota done --project admin` completes all in project

### 7.4 Filtering
- [ ] `nota find "urgency > 10"` returns filtered
- [ ] `nota find --overdue` works
- [ ] `nota find --has-annotation` works

### 7.5 Dependencies
- [ ] `nota tree 5` shows blocking tree
- [ ] `nota graph 5` shows ASCII art

### 7.6 Relations
- [ ] `nota relate 1 --to 2` creates queryable relation
- [ ] `nota related 1` shows all related

### 7.7 Recurring
- [ ] `nota add "task" --recur daily` creates recurring
- [ ] `nota recurring` lists recurring tasks

### 7.8 Scopes
- [ ] Custom scopes load from config
- [ ] `nota scopes --add work` works
- [ ] `nota list --scope work` filters

### 7.9 TUI (`nota bene`)
- [ ] `nota bene` launches TUI
- [ ] j/k navigation works
- [ ] Tasks display with colors
- [ ] Habits panel shows streaks

### 7.10 Habits
- [ ] `nota habits --stats` shows streaks
- [ ] `nota habits --weekly` shows summary
- [ ] `nota reminder add` works

---

## 8. Dependencies

```python
# requirements.txt additions
dateparser>=43.0           # NL date parsing
textual>=0.80              # TUI framework
```

---

## 9. Phase Roadmap

### Phase A: Core Infrastructure (this session)
- [ ] dateparse.py with dateparser integration
- [ ] config.py and scopes.py
- [ ] `nota edit` command
- [ ] `nota find` command

### Phase B: Bulk & Relations
- [ ] Bulk operations
- [ ] Relations overhaul
- [ ] Dependency visualization

### Phase C: Recurring & Scheduling
- [ ] Recurring tasks
- [ ] Wait/scheduled dates
- [ ] `nota waiting`, `nota scheduled`

### Phase D: Habits+
- [ ] Habit stats
- [ ] Habit analytics
- [ ] Daily reminders

### Phase E: TUI
- [ ] `nota bene` app skeleton
- [ ] Task list view
- [ ] Task detail view
- [ ] Habit panel
- [ ] Keybindings

---

## 10. Decisions (answered)

1. **Recurrence:** Both — simplified CLI aliases + full taskwarrior syntax
2. **TUI framework:** `textual`
3. **Scope config:** In `~/.nota/nota.toml` `[scopes]` section
4. **Habit reminders:** Skip this phase
5. **Graph output:** ASCII only

---

*End of Scope Document*
