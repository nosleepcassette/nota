# BUILDSHEET — nota tier 1: dashboard, pomo, smart editor fixes, notadash
# maps · cassette.help · MIT
# Target: Codex
# Date: 2026-04-30
# File: ~/dev/nota/BUILDSHEET-tier1-dashboard-v1.md

---

## Overview

Five independent workstreams. Work in order — each is self-contained.

1. **Bug fixes** (sort order, due time default, editor range + exit)
2. **In-bene split dashboard** (permanent detail pane + header bar)
3. **Pomodoro timer** (`p` key, countdown in header, macOS notification)
4. **`nota next` smarter output** (grouped by urgency)
5. **notadash fix** (nota bene pane not launching)

Files you will touch:
- `~/dev/nota/src/tui/app.py` — all TUI work
- `~/dev/nota/src/tw.py` — due time default fix
- `~/dev/nota/bin/nota` — `nota next` output
- `~/dev/nota/bin/notadash` — timing fix

---

## PART 1 — Bug fixes

### 1A. Sort by due: empty due at bottom, not top

**File:** `~/dev/nota/src/tui/app.py`

Find `sort_tasks()` → `get_sort_key()` → the `due` branch:

```python
elif sort_by == "due":
    return t.get("due") or ""
```

Replace with:

```python
elif sort_by == "due":
    # Empty due sorts LAST — use high sentinel string
    return t.get("due") or "~"
```

`"~"` (ASCII 126) sorts after all ISO date strings (`"2026-..."`) so tasks
without a due date sink to the bottom.

---

### 1B. Due dates default to 23:59 not midnight

When the smart editor or CLI sets a due date without a time component (e.g.
`"Mon May 4"`, `"tomorrow"`, `"end of week"`), taskwarrior stores it as
`T000000Z` (midnight), which makes tasks appear overdue at midnight instead of
end of day.

**Fix in `~/dev/nota/src/tui/app.py` — `_apply_edit_field()`:**

Find:
```python
elif field_key == "due":
    task_modify(task_id, due="" if value.lower() in ("clear", "-", "") else value)
```

Replace with:
```python
elif field_key == "due":
    if value.lower() in ("clear", "-", ""):
        task_modify(task_id, due="")
    else:
        # Append T23:59 to date-only values so they expire end-of-day
        # Don't append if value already has a time component
        due_val = value
        if not any(c in value for c in (":", "T", "am", "pm", "AM", "PM")):
            due_val = f"{value}T23:59"
        task_modify(task_id, due=due_val)
```

**Also fix in `~/dev/nota/src/tw.py` — `task_add()` and `task_modify()`:**

In `task_add()`, find:
```python
if due:
    args.append(f"due:{due}")
```
Replace with:
```python
if due:
    if not any(c in due for c in (":", "T", "am", "pm", "AM", "PM")):
        due = f"{due}T23:59"
    args.append(f"due:{due}")
```

In `task_modify()`, find:
```python
if "due" in kwargs:
    args.append(f"due:{kwargs['due']}")
```
Replace with:
```python
if "due" in kwargs:
    due_val = kwargs["due"]
    if due_val and not any(c in due_val for c in (":", "T", "am", "pm", "AM", "PM")):
        due_val = f"{due_val}T23:59"
    args.append(f"due:{due_val}")
```

**Fix existing overdue tasks** — run this once after the code change:
```bash
# Find all tasks with midnight due dates and shift to 23:59
task export | python3 -c "
import json, sys, subprocess
tasks = json.load(sys.stdin)
for t in tasks:
    due = t.get('due', '')
    if due and due.endswith('T000000Z'):
        date_part = due[:8]  # 20260504
        new_due = f'{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}T23:59'
        tid = t.get('id')
        if tid:
            subprocess.run(['task', str(tid), 'modify', f'due:{new_due}',
                           'rc.confirmation=off'], capture_output=True)
            print(f'fixed task {tid}: {new_due}')
"
```

---

### 1C. Smart editor: extend due date range to 60 days

**File:** `~/dev/nota/src/tui/app.py`

Find `_build_time_options()`:
```python
for i in range(1, 15):
    d = today + datetime.timedelta(days=i)
    opts.append(f"{d:%a} {d:%b} {d.day}")
```

Replace `range(1, 15)` with `range(1, 61)` — 60 days forward gives full
2-month coverage without needing freeform entry for most scheduling.

---

### 1D. Smart editor: cleaner exit UX

**Current behavior:** Enter commits the field and advances to next field. ESC
closes the panel entirely. `q` also closes. No way to "save and close" in one
gesture, and ESC is destructive (loses un-entered current field).

**New behavior:**
- `Enter` — commits current field value, advances to next field (unchanged)
- `w` — save current field (if anything staged) and **close the panel**
- `ESC` — if a text field is active and has input: clears input only (does NOT
  close panel). If no input active: close panel without saving current field
- `q` — close panel (unchanged, same as ESC when no input active)

**File:** `~/dev/nota/src/tui/app.py`

In the `if show_edit and edit_task:` key-handling block, find:

```python
elif key == "ESC":
    show_edit = False
    edit_task = None
```

Replace with:
```python
elif key == "ESC":
    if edit_input_active and edit_input:
        # Clear in-progress text input only — don't close panel
        edit_input = ""
    else:
        # Close panel without saving current unsaved input
        show_edit = False
        edit_task = None
```

After the `elif key == "m":` block, add a new `elif` for `w`:
```python
elif key == "w":
    # Commit current field if anything is staged, then close panel
    val = None
    if ftype == "text" and edit_input.strip():
        val = edit_input.strip()
    elif ftype in ("pick", "time"):
        if edit_input_active and edit_input.strip():
            val = edit_input.strip()
        elif active_options and 0 <= edit_col < len(active_options):
            val = active_options[edit_col]
    elif ftype == "cycle" and active_options:
        val = active_options[edit_col % len(active_options)]
    if val is not None:
        _apply_edit_field(edit_task, fkey, val)
        tasks = task_list(status=view_mode, limit=50)
    show_edit = False
    edit_task = None
```

**Update `render_edit_panel()` footer hint** to show the new key:

Find the footer line in `render_edit_panel()` that shows controls and add `w=save+close`:
```
h/l ←/→ field   j/k pick   tab text   enter commit   w save+close   ESC cancel   m editor
```

---

## PART 2 — In-bene split dashboard

### Goal

Transform bene from a flat list into a split-pane command center:

```
┌────────────────────────────────────────────────────────────────────────┐
│  NOTA BENE  │  3 due today  │  12 open  │  2 inbox  │  ● POMO 18:32  │  ← header
├──────────────────────────────────────┬─────────────────────────────────┤
│ [logo]                               │                                 │
│ [hotkey bar]                         │  TASK DETAIL                    │
│ ─────────────────────────────────── │  (permanent, auto-updates as   │
│  ID  PRI  PROJECT     DUE  DESC      │   cursor moves)                 │
│ ─────────────────────────────────── │                                 │
│  5   !!   @health     tod  call endo │  [5] call endocrinologist       │
│  3   !    @cassette   tmrw fix auth  │  project: @health               │
│ ...                                  │  due: today                     │
│                                      │  priority: !!                   │
│                                      │  scope: appointment             │
│                                      │  [no annotations]               │
│                                      │                                 │
└──────────────────────────────────────┴─────────────────────────────────┘
```

The right pane replaces the current full-screen detail view. No more `v`/Enter
to open detail — it's always visible, always tracking the cursor.

### Implementation

**File:** `~/dev/nota/src/tui/app.py`

#### 2A. New state variables (add to `run()` init block)

```python
dashboard_mode = True   # False = classic full-width list
detail_width = 36       # chars for right pane (min 28, max 48)
```

#### 2B. Header bar function

Add a new function `render_header_bar()` before `run()`:

```python
def render_header_bar(tasks: list, pomo_state: dict, term_width: int) -> str:
    """Render the top status bar: counts + pomo timer."""
    from src.tw import task_list as _tl
    today_str = datetime.date.today().isoformat()

    due_today = sum(
        1 for t in tasks
        if (t.get("due") or "")[:10] == today_str
    )
    overdue = sum(
        1 for t in tasks
        if t.get("due") and (t.get("due") or "")[:10] < today_str
    )
    inbox = sum(1 for t in tasks if not t.get("project"))
    total = len(tasks)

    parts = [
        f"\033[1;33m NOTA BENE \033[0m",
        f"\033[33m│\033[0m",
        f" {total} open",
    ]
    if due_today:
        parts.append(f"  \033[33m{due_today} due today\033[0m")
    if overdue:
        parts.append(f"  \033[31m{overdue} overdue\033[0m")
    if inbox:
        parts.append(f"  \033[33m{inbox} inbox\033[0m")

    # Pomo segment
    if pomo_state.get("active"):
        remaining = pomo_state.get("remaining_secs", 0)
        mins, secs = divmod(max(0, remaining), 60)
        filled = int((1 - remaining / (25 * 60)) * 10)
        bar = "▓" * filled + "░" * (10 - filled)
        task_name = pomo_state.get("task_name", "")[:20]
        parts.append(f"  \033[1;31m● POMO [{bar}] {mins:02d}:{secs:02d} {task_name}\033[0m")

    line = "".join(parts)
    return line
```

#### 2C. Detail pane renderer for dashboard mode

Add `render_detail_pane(task, width)` — a width-constrained version of the existing
`render_task_detail()`:

```python
def render_detail_pane(task: Optional[dict], width: int) -> list:
    """Render task detail as a list of lines for the right dashboard pane."""
    lines = []
    if not task:
        lines.append(" (no task selected)")
        return lines

    def w(text=""):
        # Truncate to pane width, strip rich markup for plain output
        import re
        plain = re.sub(r'\[/?[^\]]*\]', '', str(text))
        lines.append((" " + plain)[:width])

    w(f"[{task.get('id')}] {task.get('description','')}")
    w("─" * (width - 2))

    project = task.get("project") or "(inbox)"
    w(f"project: {project}")

    priority_label = {"H": "!!! urgent", "M": "!! high", "L": "~ low", "": "(none)"}.get(
        task.get("priority", ""), "(none)"
    )
    w(f"priority: {priority_label}")

    due_raw = task.get("due") or ""
    if due_raw:
        due_disp, _ = _due_display(task)
        w(f"due: {due_disp}")
    else:
        w("due: (none)")

    scope = task.get("scope") or "(none)"
    w(f"scope: {scope}")

    tags = task.get("tags") or []
    if tags:
        w(f"tags: {' '.join('#' + tg for tg in tags)}")

    annotations = task.get("annotations") or []
    if annotations:
        w("─" * (width - 2))
        for ann in annotations[-4:]:  # last 4 annotations
            note = (ann.get("description") or "")[:width - 4]
            w(f"  · {note}")

    deps = task.get("depends") or []
    if deps:
        w("─" * (width - 2))
        w(f"depends on: {', '.join(str(d) for d in deps)}")

    return lines
```

#### 2D. Main render loop — dashboard split

In the main render loop (`while True:`), find the block that builds `frame`.
After building the logo + hotkey bar, replace the task list render section with
a split-pane render when `dashboard_mode` is True.

Find:
```python
        else:
            if not display_tasks:
                frame.append("  (no tasks)  — press a to add")
            else:
                table_lines = render_tasks_table(display_tasks, cursor, term_width, selected)
                frame.extend(table_lines)
```

Replace with:
```python
        else:
            if not display_tasks:
                frame.append("  (no tasks)  — press a to add")
            elif dashboard_mode:
                # Split: task list left, detail right
                detail_task_live = display_tasks[cursor] if display_tasks and 0 <= cursor < len(display_tasks) else None
                left_width = term_width - detail_width - 1

                table_lines = render_tasks_table(display_tasks, cursor, left_width, selected)
                detail_lines = render_detail_pane(detail_task_live, detail_width)

                max_rows = max(len(table_lines), len(detail_lines))
                divider = "\033[33m│\033[0m"
                for i in range(max_rows):
                    left = table_lines[i] if i < len(table_lines) else ""
                    right = detail_lines[i] if i < len(detail_lines) else ""
                    # Pad left to left_width
                    import re
                    plain_left = re.sub(r'\033\[[^m]*m', '', left)
                    padding = max(0, left_width - len(plain_left))
                    frame.append(left + " " * padding + divider + right)
            else:
                table_lines = render_tasks_table(display_tasks, cursor, term_width, selected)
                frame.extend(table_lines)
```

#### 2E. Header bar in frame

At the very top of each frame build (right after `frame = []`), add:

```python
        header = render_header_bar(tasks, pomo_state, term_width)
        frame.append(header)
        frame.append("\033[33m" + "─" * (term_width - 1) + "\033[0m")
```

`pomo_state` is a dict initialized in `run()` — see Part 3.

#### 2F. Toggle dashboard mode

Add key handler for `\` (backslash) to toggle dashboard mode:

In the main key dispatch section, add:
```python
elif key == "\\":
    dashboard_mode = not dashboard_mode
```

#### 2G. In dashboard mode, `v`/Enter no longer opens full-screen detail

Since detail is always visible in the right pane, pressing `v` or Enter in
dashboard mode should do nothing (or could optionally pop the old full-screen
detail for tasks with long annotations). The simplest fix: in dashboard mode,
suppress the `v`/Enter → `show_detail = True` branch.

Find where `show_detail = True` is set on `v`/Enter, and wrap it:
```python
if not dashboard_mode:
    show_detail = True
    detail_task = display_tasks[cursor]
```

---

## PART 3 — Pomodoro timer

### Goal

`p` on any task starts a 25-minute focus timer. The header bar shows a live
countdown and progress bar. macOS notification fires at zero. `P` pauses/resumes.
Completions logged as annotations on the task.

### Implementation

**File:** `~/dev/nota/src/tui/app.py`

#### 3A. Pomo state dict (add to `run()` init)

```python
pomo_state = {
    "active": False,
    "paused": False,
    "task_id": None,
    "task_name": "",
    "start_time": None,    # datetime
    "pause_time": None,    # datetime (when paused)
    "elapsed_secs": 0,     # seconds accumulated before pause
    "duration_secs": 25 * 60,
    "remaining_secs": 25 * 60,
    "notified": False,
}
```

#### 3B. Pomo update function (add near top of module, after imports)

```python
def _pomo_tick(state: dict) -> None:
    """Update remaining_secs in place. Call once per render frame."""
    if not state.get("active") or state.get("paused"):
        return
    start = state["start_time"]
    if start is None:
        return
    elapsed = (datetime.datetime.now() - start).total_seconds() + state.get("elapsed_secs", 0)
    remaining = max(0, state["duration_secs"] - elapsed)
    state["remaining_secs"] = remaining

    if remaining == 0 and not state.get("notified"):
        state["notified"] = True
        state["active"] = False
        _pomo_notify(state.get("task_name", "pomo"))
```

```python
def _pomo_notify(task_name: str) -> None:
    """Fire a macOS notification. No-op on non-mac or if osascript missing."""
    import subprocess, shutil
    if not shutil.which("osascript"):
        return
    msg = f"Pomo complete: {task_name}"
    subprocess.Popen(
        ["osascript", "-e",
         f'display notification "{msg}" with title "nota bene" sound name "Glass"'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
```

#### 3C. Key handlers for `p` and `P`

In the main key dispatch section, add:

```python
elif key == "p" and not show_edit and not fuzzy_active:
    # Start pomo on focused task
    if display_tasks and 0 <= cursor < len(display_tasks):
        t = display_tasks[cursor]
        pomo_state.update({
            "active": True,
            "paused": False,
            "task_id": t.get("id"),
            "task_name": (t.get("description") or "")[:30],
            "start_time": datetime.datetime.now(),
            "pause_time": None,
            "elapsed_secs": 0,
            "remaining_secs": 25 * 60,
            "notified": False,
        })

elif key == "P" and not show_edit and not fuzzy_active:
    # Pause / resume pomo
    if pomo_state.get("active"):
        if pomo_state.get("paused"):
            # Resume: reset start_time, keep elapsed
            pomo_state["paused"] = False
            pomo_state["start_time"] = datetime.datetime.now()
        else:
            # Pause: accumulate elapsed
            if pomo_state["start_time"]:
                pomo_state["elapsed_secs"] += (
                    datetime.datetime.now() - pomo_state["start_time"]
                ).total_seconds()
            pomo_state["paused"] = True
            pomo_state["pause_time"] = datetime.datetime.now()
```

#### 3D. Tick pomo each frame

At the TOP of the main while loop (before building `frame`), add:

```python
        _pomo_tick(pomo_state)
```

#### 3E. Log pomo completion as task annotation

In `_pomo_tick()`, after `_pomo_notify()` call, add:

```python
        # Annotate task with pomo completion
        task_id = state.get("task_id")
        if task_id:
            try:
                from src.tw import _run as _tw_run
                ts = datetime.datetime.now().strftime("%H:%M")
                _tw_run(str(task_id), "annotate", f"pomo complete {ts}",
                        "rc.confirmation=off")
            except Exception:
                pass
```

#### 3F. Hotkey bar update

Add `p=pomo` and `P=pause` to the hotkey banner string:

```python
"(a)dd  (c)omplete  (D)elete  (v)iew  (e)dit  (m)anual  (p)omo  (s)ort  (f)ilter  (x)select  (q)uit"
```

---

## PART 4 — `nota next` smarter output

### Goal

Grouped output instead of flat list:

```
── DUE TODAY (3) ────────────────────────────
  [5] call endocrinologist  @health  scope:appointment
  [8] pay rent  @admin
  [2] submit form  @cassette  scope:digital

── OVERDUE (1) ──────────────────────────────
  [1] respond to email  @cassette  3d overdue

── HIGH PRIORITY (4) ────────────────────────
  [12] finish auth refactor  @cassette  p1
  ...

── THIS WEEK (2) ────────────────────────────
  ...

── INBOX (5 untagged) ───────────────────────
  ...
```

### Implementation

**File:** `~/dev/nota/bin/nota`

Find `cmd_next()` (or wherever `nota next` output is generated). Replace its
rendering with:

```python
def cmd_next(args):
    from src.tw import task_list
    import datetime
    tasks = task_list(status="pending", limit=100)
    today = datetime.date.today().isoformat()
    this_week = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()

    overdue, due_today, high_pri, this_week_tasks, inbox, rest = [], [], [], [], [], []

    for t in tasks:
        due = (t.get("due") or "")[:10]
        pri = t.get("priority", "")
        project = t.get("project") or ""

        if due and due < today:
            overdue.append(t)
        elif due == today:
            due_today.append(t)
        elif pri == "H":
            high_pri.append(t)
        elif due and due <= this_week:
            this_week_tasks.append(t)
        elif not project:
            inbox.append(t)
        else:
            rest.append(t)

    def fmt(t):
        tid = t.get("id", "?")
        desc = t.get("description", "")[:50]
        proj = f"  @{t['project']}" if t.get("project") else ""
        scope = f"  scope:{t['scope']}" if t.get("scope") else ""
        due = (t.get("due") or "")[:10]
        due_str = f"  due:{due}" if due else ""
        return f"  [{tid}] {desc}{proj}{scope}{due_str}"

    def section(title, items):
        if not items:
            return
        print(f"\n── {title} ({len(items)}) " + "─" * max(0, 44 - len(title) - 5))
        for t in items[:10]:
            print(fmt(t))

    section("OVERDUE", overdue)
    section("DUE TODAY", due_today)
    section("HIGH PRIORITY", high_pri)
    section("THIS WEEK", this_week_tasks)
    section("INBOX", inbox)
    if rest:
        section(f"OTHER ({len(rest)} tasks)", rest[:5])
    print()
```

---

## PART 5 — notadash fix: nota bene pane not launching

### Problem

When tmux creates a new pane via `notadash`, the shell in that pane may not have
sourced `~/.zshrc` yet when `tmux send-keys` fires. This means `nota` (at
`~/.bin/nota`) isn't in PATH yet, so the command silently fails and the pane
shows a bare shell prompt.

### Fix

**File:** `~/dev/nota/bin/notadash`

Find:
```zsh
tmux send-keys -t "$P_bene"    -l -- "nota bene"
tmux send-keys -t "$P_bene"    Enter
```

Replace with:
```zsh
tmux send-keys -t "$P_bene"    -l -- "source ~/.zshrc 2>/dev/null; nota bene"
tmux send-keys -t "$P_bene"    Enter
```

This forces the interactive shell config to load before running nota bene,
regardless of whether tmux launches panes as login or interactive shells.

Also add a small sleep before sending keys to all panes, to give each shell
time to initialize:

After the last `tmux select-pane` name line (before the send-keys block), add:
```zsh
sleep 0.3
```

---

## PART 6 — Update full help text

**File:** `~/dev/nota/src/tui/app.py`

In `render_full_help()`, update to reflect all new keys:

```
  [bold amber]Dashboard[/bold amber]
    \               toggle split-pane dashboard mode
    p               start 25-min pomo on focused task
    P               pause / resume active pomo

  [bold amber]Smart edit changes[/bold amber]
    w               save current field + close edit panel
    ESC (in text)   clear text input (don't close)
    ESC (no text)   close edit panel without saving
```

---

## PART 7 — Smoke tests

After implementation, run these checks:

```bash
# Syntax check
python3 -m py_compile ~/dev/nota/src/tui/app.py && echo "OK"
python3 -m py_compile ~/dev/nota/src/tw.py && echo "OK"
python3 -c "import ast; ast.parse(open('/Users/maps/dev/nota/bin/nota').read())" && echo "OK"

# Sort fix: add a task with no due date and one with a date, sort by due, verify dated task is first
nota add "no due date task @test"
nota add "due date task @test due:tomorrow"
# Launch nota bene, press 's d', verify dated task is above the no-date task

# Due time fix: add a task due today and verify it doesn't show as overdue at midnight
nota add "eod task @test due:today"
task export | python3 -c "import json,sys; [print(t.get('due')) for t in json.load(sys.stdin) if 'eod' in t.get('description','')]"
# Should show a T23:59 timestamp, not T000000Z

# Pomo: launch nota bene, press p on a task, verify header shows countdown
# (visual check only — no automated test)

# notadash: kill any existing session, relaunch, verify bene pane shows nota bene
notadash kill 2>/dev/null; notadash
# Check right pane has nota bene running, not a bare shell

# nota next
nota next
# Should show grouped sections: OVERDUE / DUE TODAY / HIGH PRIORITY / etc.
```

---

## Git commit

```bash
cd ~/dev/nota
git add src/tui/app.py src/tw.py bin/nota bin/notadash
git commit -m "bene: dashboard split, pomo timer, smart editor fixes, nota next groups, notadash fix"
```

---

## What is NOT in this buildsheet (queued for next pass)

- Scope-aware context routing (`nota ctx home/out`, bene context badge)
- Task templates (`nota template save/from`)
- `nota done` undo buffer (`~/.config/nota/undo.json`)
- Dependency graph view in bene (`D` key → ASCII dep tree)
- `nota_bene_state()` MCP resource (structured JSON of top-10 tasks)
- Cart daily-brief nota block smoke + fix
- Completion event webhooks
- `nota log` (append worklog note without creating a task)
- `nota overdue` bulk reschedule
- `nota agenda` / `nota context` (agent-oriented compact output)
- Inline annotation toggle (`A` key in task list)
- Project totals in status line
- `notadash`: 4th data pane (today's completed count)

---
*maps · cassette.help · MIT*
