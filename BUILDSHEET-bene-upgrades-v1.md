# BUILDSHEET — nota bene: TUI Upgrades (Tier 2)
**Version:** v1  
**Target:** `/Users/maps/dev/nota/src/tui/app.py`  
**For:** Codex  
**Written by:** Claude Code (Vesper / sextile)  
**Date:** 2026-04-30

---

## Context

`nota bene` is the primary task interface for maps. The CLI (`nota`) is now agent-only.
The TUI is the user-facing interface for everything. It's in good shape — alternate
screen buffer, cached banner render, shared Console instance, single atomic frame write.
The tier 1 buildsheet added the split dashboard, pomo timer, header bar, and editor fixes.

This buildsheet adds tier 2 upgrades: features that turn bene from a task list into a
thinking tool.

---

## Current State

- `/Users/maps/dev/nota/src/tui/app.py` — working, 1741 lines
- Dashboard mode: left pane task list, right pane detail (dashboard_mode=True default)
- Pomo timer: `p` key, 25-min countdown, macOS notification, annotates task
- Header bar: task counts, overdue count, inbox count, pomo status
- Smart editor: 60-day date range, ESC clears / `w` saves+closes
- Sort, filter, fuzzy search, batch select all working
- Screen tearing: fixed (alt screen, cached banner, single write)

---

## Tasks

### Task 1: Annotation/notes in the detail pane

The right-side detail pane should surface `nota show <id>` annotation history for the
selected task. Currently annotations are written via `nota annotate` but invisible in
the TUI.

**Files:** `app.py`  
**What:** In `render_task_detail()`, append annotation history after the existing fields.
Also update `_task_detail_lines()` if that's the delegating function — grep for where
detail pane content is built and find the one that renders the right pane in dashboard mode.

**How:**
1. Find `render_task_detail` (around line 700-800 — grep for it)
2. After the existing field list, call `task_get_annotations(task_id)` — see `src/tw.py`
   for the exact function name. If it doesn't exist, call `task_get(task_id)` and check
   if the returned dict includes an `annotations` key (list of `{"entry": ..., "description": ...}`)
3. If annotations exist, append a separator line and then each annotation as:
   ```
   ── notes ──
   [date] description text
   [date] description text
   ```
   Format the date as `MMM DD HH:MM` (e.g. `Apr 28 14:32`). The entry field is an ISO
   timestamp string — parse with `datetime.fromisoformat()` or `datetime.strptime`.
4. If no annotations, append nothing (don't add an empty "notes" section)
5. The detail pane has a width constraint (`effective_detail_width`). Wrap annotation
   text to fit: `textwrap.wrap(desc, width=effective_detail_width - 4)`

**Done when:** Selecting a task with annotations shows them in the right pane. Tasks
without annotations show no empty section. Width wraps correctly at narrow terminals.

---

### Task 2: Focus mode — `F` key

One-keypress emergency triage view: show only overdue + due today. Clears on `F` again.
No filter menu, no sort selection.

**Files:** `app.py`  
**What:** Add `focus_mode = False` state variable. `F` key toggles it. When active,
`current_display_tasks()` filters to only tasks where due is today or overdue.

**How:**
1. Add `focus_mode: bool = False` near the other state variables (around line 1039-1060)
2. In `current_display_tasks()`, if `focus_mode` is True, filter `display` to tasks
   where `_due_display(t)` returns a style containing "red" (overdue) or "due" (today).
   
   Better approach: use the raw due field. A task is in focus if:
   ```python
   due_str = t.get("due", "")
   if not due_str:
       return False  # no due = not in focus
   try:
       due_dt = datetime.datetime.strptime(due_str[:8], "%Y%m%d").date()
       return due_dt <= datetime.date.today()
   except Exception:
       return False
   ```
3. Add `F` key handler in the main key loop (after the existing filter key `f`):
   ```python
   elif key == "F":
       focus_mode = not focus_mode
       cursor = 0
   ```
4. In the status line (bottom of frame), show `│ FOCUS` in amber when `focus_mode` is True
5. In the header bar area (near view_mode display), show `[FOCUS]` indicator when active

**Done when:** `F` in normal mode shows only overdue + due today. `F` again restores full
list. Status line shows indicator. Works correctly with existing sort and project filter.

---

### Task 3: Quick-capture natural language (`A` key)

Alternate to the full smart editor. `A` (shift-a) opens a single-line prompt, parses
natural language, adds the task without a modal.

**Files:** `app.py`  
**What:** `A` key → `read_line()` prompt → parse → `task_add()` → refresh.

**How:**
1. Add a simple parser function `_parse_quick_add(text: str) -> dict`:
   ```python
   def _parse_quick_add(text: str) -> dict:
       """Parse 'fix auth bug tomorrow high project:auth' into task fields."""
       import re
       fields = {}
       # Extract priority: high/h, medium/m, low/l or H/M/L at end
       m = re.search(r'\b(high|H|medium|M|low|L)\b', text)
       if m:
           fields['priority'] = m.group(1)[0].upper()
           text = text[:m.start()] + text[m.end():]
       # Extract project: project:name or proj:name
       m = re.search(r'\b(?:project|proj):(\S+)', text, re.I)
       if m:
           fields['project'] = m.group(1)
           text = text[:m.start()] + text[m.end():]
       # Extract due: today, tomorrow, monday...sunday, or YYYY-MM-DD or MMM DD
       m = re.search(r'\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{4}-\d{2}-\d{2})\b', text, re.I)
       if m:
           fields['due_raw'] = m.group(1).lower()
           text = text[:m.start()] + text[m.end():]
       fields['description'] = re.sub(r'\s+', ' ', text).strip()
       return fields
   ```
   
2. Due date resolution helper (reuse `_build_time_options` logic or inline):
   ```python
   def _resolve_quick_due(raw: str) -> str:
       """Convert natural language due to taskwarrior format YYYYMMDDTHHMMSSZ."""
       today = datetime.date.today()
       days = {"today": 0, "tomorrow": 1, "monday": ..., ...}
       if raw in days:
           target = today + datetime.timedelta(days=days[raw])
       # weekday resolution: find next occurrence
       ...
       return target.strftime("%Y%m%dT235900Z")
   ```

3. In the main key loop, add `A` handler:
   ```python
   elif key == "A":
       show_cursor()
       text, cancelled = read_line("  \033[33mquick add: \033[0m")
       hide_cursor()
       if not cancelled and text and text.strip():
           parsed = _parse_quick_add(text.strip())
           desc = parsed.pop('description', text.strip())
           due_raw = parsed.pop('due_raw', None)
           if due_raw:
               parsed['due'] = _resolve_quick_due(due_raw)
           _tui_add(desc, **parsed)  # update _tui_add signature to accept kwargs
           tasks = task_list(status=view_mode, limit=50)
   ```

4. Update `_tui_add(text, priority=None, project=None, due=None)` to accept and pass
   keyword arguments to `task_add()`. Check the current signature in app.py and expand it.

5. Add `(A)dd-quick` to the hotkey banner text (update the banner string in `_make_banner_lines`
   and in the plain-text fallback)

**Done when:** `A` opens a one-line prompt, `fix auth bug tomorrow high` adds a task with
due=tomorrow 23:59, priority=H. `project:auth` sets project. Description is remainder.
Invalid/unrecognized input adds as plain description with no extras.

---

### Task 4: Today-completed log view (`T` key)

Read-only list of tasks completed today. Useful post-pomo and end-of-day review.

**Files:** `app.py`, `src/tw.py`  
**What:** `T` key toggles a `show_today` state. When active, shows tasks with
`status:completed` and `end:today` in a simple list.

**How:**
1. In `src/tw.py`, add (or find if it exists):
   ```python
   def task_list_completed_today() -> list:
       import subprocess, json, datetime
       today = datetime.date.today().strftime("%Y-%m-%d")
       result = subprocess.run(
           ["task", f"end:{today}", "status:completed", "export"],
           capture_output=True, text=True
       )
       try:
           return json.loads(result.stdout)
       except Exception:
           return []
   ```
   
2. Add `show_today: bool = False` and `today_tasks: list = []` to state vars

3. Add `T` key handler:
   ```python
   elif key == "T":
       if not show_today:
           today_tasks = task_list_completed_today()
           show_today = True
       else:
           show_today = False
   ```

4. In the frame build section, add a branch for `show_today` (before the `else` that
   renders the task table):
   ```python
   elif show_today:
       frame.append(f"  \033[1;33mtoday's completions\033[0m  (\033[33mT\033[0m to close)")
       frame.append("")
       if not today_tasks:
           frame.append("  nothing completed today yet")
       else:
           for t in today_tasks:
               pomo_ann = next((a['description'] for a in t.get('annotations', []) 
                               if 'pomo' in a.get('description','').lower()), None)
               pomo_tag = f"  \033[33m[pomo]\033[0m" if pomo_ann else ""
               frame.append(f"  ✓  {t.get('description','')[:60]}{pomo_tag}")
   ```

**Done when:** `T` shows a list of today's completed tasks. Pomo-annotated tasks are
tagged. `T` again returns to normal view. Empty state shows "nothing completed today yet".

---

### Task 5: Dependency display in detail pane

When a task has `depends:` set in taskwarrior, the right-side detail pane shows
"blocks: X, Y" and "blocked by: Z" using the task IDs/descriptions.

**Files:** `app.py`  
**What:** Extend `render_task_detail()` to show dependency info from the task dict.

**How:**
1. The task dict from `task_get()` includes a `depends` key (list of UUIDs) when set.
   Also, to find what blocks the current task, query `task_list()` and check if any task's
   `depends` list contains the current task's UUID.

2. In `render_task_detail(task)`, after the existing fields:
   ```python
   depends_uuids = task.get('depends', [])
   if depends_uuids:
       # Resolve UUIDs to descriptions (best-effort; use local tasks list if available)
       dep_lines = []
       for uid in depends_uuids:
           dep_task = task_get_by_uuid(uid)  # add this to tw.py if needed
           dep_desc = dep_task.get('description', uid[:8]) if dep_task else uid[:8]
           dep_lines.append(f"    → {dep_desc}")
       lines.append("")
       lines.append("  blocked by:")
       lines.extend(dep_lines)
   ```

3. For "blocks" (reverse depends), this requires scanning all tasks — skip for now
   unless it's cheap. If `tasks` is available in scope (pass it in), scan:
   ```python
   blocks = [t for t in all_tasks if task.get('uuid') in t.get('depends', [])]
   ```

4. Add `task_get_by_uuid(uuid: str)` to `src/tw.py`:
   ```python
   def task_get_by_uuid(uuid: str) -> dict:
       result = subprocess.run(["task", uuid, "export"], capture_output=True, text=True)
       try:
           tasks = json.loads(result.stdout)
           return tasks[0] if tasks else {}
       except Exception:
           return {}
   ```

**Done when:** A task with `depends:` set shows "blocked by: [description]" in the detail
pane. If no dependencies, nothing is shown.

---

### Task 6: Project list sidebar (`P` key)

`P` toggles the left pane (in dashboard mode) to a project list with task counts.
Navigate with j/k, Enter filters to that project, `P` again returns to task list.

**Files:** `app.py`  
**What:** Add `show_projects: bool = False` state. When active, left pane shows projects
with counts instead of the task list.

**How:**
1. Add `show_projects = False` and `project_cursor = 0` to state vars

2. Build project list from current tasks:
   ```python
   def _get_project_list(tasks):
       from collections import Counter
       counts = Counter(t.get('project') or '(none)' for t in tasks)
       return sorted(counts.items(), key=lambda x: -x[1])
   ```

3. `P` key handler:
   ```python
   elif key == "P":
       show_projects = not show_projects
       project_cursor = 0
   ```

4. When `show_projects` is True and `dashboard_mode` is True, replace the left pane
   content with the project list:
   ```python
   # In the dashboard rendering block (around line 1248-1270)
   if show_projects:
       proj_list = _get_project_list(tasks)
       left_lines = [f"  \033[1;33mprojects\033[0m  (P close  Enter filter)"]
       left_lines.append("")
       for i, (proj, count) in enumerate(proj_list):
           marker = "\033[7m" if i == project_cursor else " "
           reset = "\033[0m" if i == project_cursor else ""
           left_lines.append(f"  {marker} {proj:<28} {count:>3}{reset}")
   ```

5. In key handling when `show_projects` is True:
   - j/k: move `project_cursor`
   - Enter: set `filter_project` to selected project name (or clear if `(none)`), 
     set `show_projects = False`, reset cursor
   - ESC: close without filtering

**Done when:** `P` in normal mode shows a project list with counts. j/k navigate.
Enter filters to that project and returns to task list view. `P` closes without filtering.

---

## Smoke Tests

```zsh
# Start bene
nota bene

# Task 1: annotations
nota annotate 1 "check this worked"
# Open bene, select task 1 → right pane should show "── notes ──" section

# Task 2: focus mode
# Press F → only overdue/today tasks visible
# Press F → full list returns
# Status bar shows FOCUS indicator when active

# Task 3: quick add
# Press A → type "fix auth bug tomorrow high project:backend"
# Task appears with priority H, due tomorrow 23:59, project backend

# Task 4: today log
# Complete a task: press c on any task
# Press T → completed task appears in the log
# Press T → returns to normal

# Task 5: dependencies (requires a task with depends set)
# nota add "blocker task" → get ID, e.g. 42
# nota modify 1 depends:42
# Open bene, select task 1 → detail pane shows "blocked by: blocker task"

# Task 6: project sidebar
# Press P → project list with counts appears in left pane
# Press j/k → navigate
# Press Enter → filters to selected project, P closes sidebar
```

## Commit

```
feat(bene): tier 2 upgrades — annotations, focus mode, quick-add, today log, deps, project sidebar
```
