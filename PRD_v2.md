# nota v2.0 — Product Requirements Document (PRD)

**Version:** 1.0
**Status:** Draft
**Author:** Vesper (for maps)

---

## 1. Problem Statement

nota MVP provides basic task + habit tracking backed by taskwarrior and harsh. However:

- **Date parsing** requires taskwarrior to parse (which it doesn't do for all NL dates)
- **Task editing** is missing — no way to modify existing tasks
- **No bulk operations** — one task at a time
- **Limited filtering** — only project/scope/priority
- **No dependency visualization** — can't see blocking trees
- **Relations are annotations only** — not queryable
- **No recurring task support** — native to taskwarrior but not exposed
- **No wait/scheduled dates** — taskwarrior features not exposed
- **Hardcoded 10 scopes** — no user-defined scopes
- **Plain text CLI** — no rich UI
- **Basic habits** — no stats, analytics, or reminders

---

## 2. Target Users

1. **Primary:** sextile/hermes agents (MCP tool consumption)
2. **Secondary:** maps (direct CLI usage)
3. **Tertiary:** Future hermetica-ios users (TUI)

---

## 3. Goals & Success Metrics

### 3.1 Goals

| Goal | Metric |
|------|--------|
| Full taskwarrior parity | All native TW features accessible via nota CLI |
| Local NL date parsing | `due:friday` → ISO date stored, no LLM needed |
| Rich CLI output | `nota bene` TUI with colors, navigation |
| Habit analytics | Streaks, trends, weekly/monthly views |

### 3.2 Success Criteria

- [ ] All CLI commands in Section 6 of Scope Document implemented
- [ ] `nota bene` launches and is usable
- [ ] `dateparser` library handles at least 20 common date patterns
- [ ] MCP tools pass acceptance criteria in Section 7
- [ ] No regression: existing `nota add`, `nota list`, `nota done` still work

---

## 4. Scope

### 4.1 In Scope

**P0 (must have):**
- Local NL date parsing (dateparser)
- Task modification (edit command)
- Bulk operations
- Advanced filtering (find command)
- User-defined scopes

**P1 (should have):**
- Dependency visualization (tree, graph)
- Relations overhaul
- Recurring tasks
- Wait/scheduled dates
- Rich TUI (`nota bene`)

**P2 (nice to have):**
- Habit analytics
- Habit reminders
- Graphviz export

### 4.2 Out of Scope

- Web UI (Phase 3, per original scope)
- Garden sync (Phase 4)
- Mobile app
- Multi-user support

---

## 5. User Stories

### US1: Natural Language Due Dates
> As a user, I want to type `nota add "call dentist due:next friday"` and have it store the correct ISO date, so I don't have to look up the calendar.

**Acceptance:**
- Input: `due:friday` → stored as `2026-04-10`
- Input: `due:next monday` → stored as `2026-04-13`
- Input: `due:in 2 weeks` → stored as `2026-04-20`

### US2: Edit Existing Tasks
> As a user, I realized I typed the wrong project. Instead of deleting and re-adding, I want to fix it with `nota edit 5 --project home`.

**Acceptance:**
- `nota edit 5 --project home` updates project
- `nota edit 5 --title "new title"` updates title
- `nota edit 5 --add-tag urgent` adds tag

### US3: Bulk Complete
> As a user, I've finished several tasks. Instead of `nota done 1 && nota done 2 && nota done 3`, I want `nota done 1 2 3`.

**Acceptance:**
- `nota done 1 2 3` marks all three complete
- `nota done --project admin` completes all in project
- Output shows success/failure for each

### US4: Search & Filter
> As a user, I want to find all overdue urgent tasks: `nota find "priority:H due < today"`.

**Acceptance:**
- Raw TW expressions pass through
- `--overdue` flag works
- `--has-annotation` flag works
- Results display in same format as `nota list`

### US5: Dependency Tree
> As a user, I can't remember what's blocking task 5: `nota tree 5`.

**Acceptance:**
- Shows blocking chain: 5 → 2 → 1
- Uses ASCII art: `[5] → [2] → [1]`
- Shows status (done/pending) for each

### US6: Custom Scopes
> As a user, I want a `work` scope beyond the defaults.

**Acceptance:**
- Define in `~/.nota/scopes`
- `nota add "task" scope:work` works
- `nota list --scope work` filters correctly
- `nota scopes` lists all

### US7: Rich TUI
> As a user, I want to launch `nota bene` and see a split-pane UI with tasks, details, and habits.

**Acceptance:**
- Launches without error
- j/k navigation moves selection
- enter shows task detail
- q quits

### US8: Habit Stats
> As a user, I want to see my habit streaks: `nota habits --stats`.

**Acceptance:**
- Shows streak count per habit
- Shows last completed date
- Highlights current streak leaders

---

## 6. Technical Design

### 6.1 Architecture

See SCOPE_v2.md Section 2 for architecture diagram.

### 6.2 Key Modules

| Module | Responsibility |
|--------|---------------|
| `dateparse.py` | Convert NL dates to ISO, handle shortcuts |
| `query.py` | Build taskwarrior filter strings, custom filters |
| `config.py` | Load/write config, merge defaults |
| `scopes.py` | Load user scopes, merge with defaults |
| `tui/app.py` | Main textual app |
| `tui/views.py` | View classes |
| `tui/widgets.py` | Reusable widgets |

### 6.3 Data Flow

```
User Input (CLI/TUI/MCP)
       ↓
parse.py / dateparse.py (if date)
       ↓
tw.py (taskwarrior wrapper)
       ↓
taskwarrior binary
       ↓
Output (CLI text / TUI render / JSON)
```

### 6.4 Config Files

| File | Location | Purpose |
|------|----------|---------|
| Config | `~/.nota/nota.toml` | DB path, defaults |
| Scopes | `~/.nota/scopes` | User-defined scopes |
| Data | `~/.task` | taskwarrior data |
| Habits | `~/.config/harsh/` | harsh data |

---

## 7. Testing Strategy

### 7.1 Unit Tests
- `dateparse.py`: 20+ date patterns
- `parse.py`: existing, ensure no regression
- `scopes.py`: load, merge, validate

### 7.2 Integration Tests
- CLI commands work end-to-end
- MCP tools return expected JSON
- TUI launches without crash

### 7.3 Manual Testing
- All acceptance criteria in SCOPE_v2.md Section 7

---

## 8. Timeline

| Phase | Est. Time | Contents |
|-------|-----------|----------|
| Phase A | 2-3 hrs | dateparse, config, edit, find |
| Phase B | 1-2 hrs | bulk, relations, tree |
| Phase C | 1 hr | recurring, wait/scheduled |
| Phase D | 1-2 hrs | habits+, reminders |
| Phase E | 2-3 hrs | TUI bene |

**Total:** ~8-11 hours (spread across multiple sessions)

---

## 9. Open Questions

1. **Recurrence syntax:** Both — simplified CLI aliases (daily/weekly/monthly) + full taskwarrior syntax support
2. **TUI tech:** `textual` (confirmed)
3. **Scope config location:** In `nota.toml` (confirmed)
4. **Habit reminder mechanism:** Skip this phase (confirmed)
5. **Graph output:** ASCII only (confirmed)

---

## 10. Approval

- [ ] Product requirements reviewed
- [ ] Technical design approved
- [ ] Timeline accepted
- [ ] Prioritization confirmed

---

*End of PRD*
