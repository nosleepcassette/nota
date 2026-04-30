# BUILDSHEET: nota master — Smart Edit + Polish + Fuzzy + Mobile Push + notadash
# maps · cassette.help · MIT
# Target: Codex (autonomous execution)
# IMPORTANT: Read every target file IN FULL before editing. One coherent pass per file.
# Do NOT skip sections. Do NOT partially implement. Report exact errors.

---

## TARGET FILES

- `~/dev/nota/src/tui/app.py`     — TUI (smart edit, polish, fuzzy, arrow keys, logo)
- `~/dev/nota/bin/notadash`       — tmux dashboard (add bene pane, smarter panes)
- `~/dev/nota/src/webhook.py`     — iOS webhook (add due-check + push endpoint)
- `~/dev/nota/bin/nota`           — CLI (add `nota cron-check` command)
- `~/dev/nota/README.md`          — update to reflect all new features

---

## PART 1 — Smart field editor (replaces `e` key)

**File:** `~/dev/nota/src/tui/app.py`

The current `e` key does `os.system(f"task {id} edit")` — raw $EDITOR. Replace entirely.

### 1a. State variables — add to `run()` near top

```python
show_edit   = False
edit_task   = None
edit_field  = 0      # 0=description, 1=project, 2=scope, 3=priority, 4=due, 5=tags
edit_col    = 0      # position within a pick-list column (for j/k within options)
edit_pick   = []     # current options list for pick fields
edit_input  = ""     # text buffer for free-text fields
edit_input_active = False   # True when cursor is in the text input box
```

### 1b. Field definitions (constant, module-level)

```python
EDIT_FIELDS = [
    {"key": "description", "label": "Description", "type": "text"},
    {"key": "project",     "label": "Project",     "type": "pick"},
    {"key": "scope",       "label": "Scope",       "type": "pick"},
    {"key": "priority",    "label": "Priority",    "type": "cycle", "options": ["H", "M", "L"]},
    {"key": "due",         "label": "Due",         "type": "time"},   # 15-min chunk picker
    {"key": "tags",        "label": "Tags",        "type": "text"},
]
```

### 1c. `_load_edit_picks(field_key)` — populate pick lists

```python
def _load_edit_picks(field_key: str) -> list:
    if field_key == "project":
        try:
            from src.tw import task_projects
            return sorted({p.get("project","") for p in task_projects() if p.get("project")})
        except Exception:
            return []
    elif field_key == "scope":
        try:
            from src.scopes import list_scopes
            scopes = list_scopes()
            if isinstance(scopes, dict):
                return sorted(scopes.keys())
            return [s.get("scope","") for s in scopes if s.get("scope")]
        except Exception:
            return []
    return []
```

### 1d. `render_edit_panel(task, field, col, picks, input_buf, input_active, term_width)`

Renders the smart edit overlay. Returns a list of strings (frame lines).

Layout:
```
  ┌─ Edit Task #N ─────────────── [m=manual] ─┐
  │                                            │
  │  ◀  Description  ▶   call the dentist      │  ← active field header (h/l to switch)
  │                                            │
  │  Options:          │  [ text input box ]   │
  │  > inbox           │  _                    │
  │    health          │                       │
  │    admin           │                       │
  │                    │                       │
  │                    │                       │
  └────────────────────────────────────────────┘
  j/k navigate options   enter select   tab → input   esc cancel
```

For `type: "text"` fields: only show the input box, no pick list.
For `type: "pick"` fields: show pick list on left + text input on right (for new value).
For `type: "cycle"` fields: show all options in a vertical list, highlight current.
For `type: "time"` (due): generate a list of time options:
  - "clear" (blank/remove due)
  - "today", "tomorrow", "end of week"
  - then: next 14 days as "Mon Apr 28", "Tue Apr 29", etc.
  - then: times in 15-min chunks from now to +4hrs (e.g. "today 2:00pm", "today 2:15pm")
  All generated dynamically at render time using `datetime`.

Show current field value prominently at top. Show field name with `◀ ▶` indicators
(prev/next field via `h`/`←` and `l`/`→`).

If Rich is available, use `box.ROUNDED` panel. If not, use plain `─`/`│`/`┌`/`┐`/`└`/`┘`.

### 1e. Key handling — when `show_edit` is True

Handle BEFORE the main key dispatch block (use `continue` at end):

```python
if show_edit and edit_task:
    if key in ("h", "LEFT"):
        edit_field = (edit_field - 1) % len(EDIT_FIELDS)
        edit_pick = _load_edit_picks(EDIT_FIELDS[edit_field]["key"])
        edit_col = 0
        edit_input = ""
        edit_input_active = False

    elif key in ("l", "RIGHT"):
        edit_field = (edit_field + 1) % len(EDIT_FIELDS)
        edit_pick = _load_edit_picks(EDIT_FIELDS[edit_field]["key"])
        edit_col = 0
        edit_input = ""
        edit_input_active = False

    elif key in ("j", "DOWN") and not edit_input_active:
        if edit_pick:
            edit_col = (edit_col + 1) % len(edit_pick)

    elif key in ("k", "UP") and not edit_input_active:
        if edit_pick:
            edit_col = (edit_col - 1) % len(edit_pick)

    elif key == "\t":
        edit_input_active = not edit_input_active  # tab toggles focus

    elif key in ("\r", "\n"):
        # Commit current value
        field_def = EDIT_FIELDS[edit_field]
        ftype = field_def["type"]
        fkey = field_def["key"]
        val = None

        if ftype == "text":
            val = edit_input.strip() if edit_input.strip() else None
        elif ftype == "pick":
            if edit_input_active and edit_input.strip():
                val = edit_input.strip()
            elif edit_pick and 0 <= edit_col < len(edit_pick):
                val = edit_pick[edit_col]
        elif ftype == "cycle":
            opts = field_def.get("options", [])
            if opts:
                val = opts[edit_col % len(opts)]
        elif ftype == "time":
            if edit_input_active and edit_input.strip():
                val = edit_input.strip()
            elif edit_pick and 0 <= edit_col < len(edit_pick):
                val = edit_pick[edit_col]

        if val is not None:
            _apply_edit_field(edit_task, fkey, val)
            edit_task = task_get(edit_task.get("id"))
            tasks = task_list(status=view_mode, limit=50)

        # After commit: advance to next field automatically
        edit_field = (edit_field + 1) % len(EDIT_FIELDS)
        edit_pick = _load_edit_picks(EDIT_FIELDS[edit_field]["key"])
        edit_col = 0
        edit_input = ""
        edit_input_active = False

    elif edit_input_active:
        # Route keypresses to input buffer
        if key in ("\x7f", "\x08"):   # backspace
            edit_input = edit_input[:-1]
        elif len(key) == 1 and ord(key) >= 32:
            edit_input += key

    elif key == "m":
        # Manual fallback
        os.system(f"task {edit_task.get('id')} edit")
        tasks = task_list(status=view_mode, limit=50)
        show_edit = False
        edit_task = None

    elif key in ("q", "ESC"):
        show_edit = False
        edit_task = None

    pending_key = ""
    continue
```

### 1f. `_apply_edit_field(task, field_key, value)` function

```python
def _apply_edit_field(task: dict, field_key: str, value: str) -> None:
    from src.tw import task_modify
    task_id = task.get("id")
    if not task_id:
        return
    if field_key == "description":
        task_modify(task_id, description=value)
    elif field_key == "project":
        task_modify(task_id, project=value)
    elif field_key == "scope":
        task_modify(task_id, scope=value)
    elif field_key == "priority":
        pri_map = {"H": "p1", "M": "p3", "L": "p4"}
        task_modify(task_id, priority_p=pri_map.get(value.upper(), "p3"))
    elif field_key == "due":
        task_modify(task_id, due="" if value.lower() in ("clear", "-", "") else value)
    elif field_key == "tags":
        new_tags = [t.strip() for t in value.replace(",", " ").split() if t.strip()]
        old_tags = task.get("tags") or []
        task_modify(task_id,
                    tags_add=[t for t in new_tags if t not in old_tags],
                    tags_remove=[t for t in old_tags if t not in new_tags])
```

### 1g. Wire `e` key

Replace current `elif key == "e":` block:

```python
elif key == "e":
    if display_tasks and cursor < len(display_tasks):
        t = display_tasks[cursor]
        edit_task = task_get(t.get("id"))
        edit_field = 0
        edit_pick = _load_edit_picks(EDIT_FIELDS[0]["key"])
        edit_col = 0
        edit_input = ""
        edit_input_active = False
        show_edit = True
        show_detail = False
        show_help = False
        show_sort = False
    pending_key = ""

elif key == "m":
    if display_tasks and cursor < len(display_tasks):
        t = display_tasks[cursor]
        os.system(f"task {t.get('id')} edit")
        tasks = task_list(status=view_mode, limit=50)
    pending_key = ""
```

### 1h. Wire `show_edit` into render block

In the main render block, after the `show_detail` branch:

```python
elif show_edit and edit_task:
    time_options = _build_time_options() if EDIT_FIELDS[edit_field]["type"] == "time" else edit_pick
    panel_lines = render_edit_panel(
        edit_task, edit_field, edit_col,
        time_options if EDIT_FIELDS[edit_field]["type"] == "time" else edit_pick,
        edit_input, edit_input_active, term_width
    )
    frame.extend(panel_lines)
```

Add `_build_time_options()`:

```python
def _build_time_options() -> list:
    import datetime
    opts = ["clear", "today", "tomorrow", "end of week"]
    today = datetime.date.today()
    for i in range(1, 15):
        d = today + datetime.timedelta(days=i)
        opts.append(d.strftime("%Y-%m-%d (%a %b %-d)"))
    # 15-min chunks for today
    now = datetime.datetime.now()
    base = now.replace(second=0, microsecond=0)
    mins = (base.minute // 15 + 1) * 15
    base = base.replace(minute=0) + datetime.timedelta(minutes=mins)
    for i in range(16):   # 4 hours of 15-min slots
        t = base + datetime.timedelta(minutes=i*15)
        opts.append("today " + t.strftime("%-I:%M%p").lower())
    return opts
```

---

## PART 2 — Screen tearing + arrow keys + logo (from BUILDSHEET-polish-v1.md)

**File:** `~/dev/nota/src/tui/app.py`

This buildsheet supersedes BUILDSHEET-polish-v1.md. Implement all of it here.

### 2a. Double-buffer render (fix tearing)

Replace the per-frame clear+write block:
```python
sys.stdout.write("\033[2J\033[H")
output = "\n".join(frame)
sys.stdout.write(output)
if not frame or frame[-1] != "\n":
    sys.stdout.write("\n")
sys.stdout.flush()
```
With:
```python
output = "\n".join(frame)
sys.stdout.write("\033[H")   # move to top-left
sys.stdout.write(output)     # write frame
sys.stdout.write("\033[J")   # erase remainder
sys.stdout.flush()
```

Remove `first_render` state variable and its associated `if first_render:` block.
Keep `clear_screen()` using `\033[2J\033[H` (used for explicit clears only).

### 2b. SIGWINCH handler

After imports, add:
```python
import signal as _signal
_term_resized = False
def _handle_sigwinch(signum, frame):
    global _term_resized
    _term_resized = True
_signal.signal(_signal.SIGWINCH, _handle_sigwinch)
```

At the very top of the `while True:` body, before building `frame`:
```python
global _term_resized
if _term_resized:
    term_width = get_term_size().columns
    _term_resized = False
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
```

### 2c. Arrow keys — LEFT/RIGHT for view switching + detail nav

`LEFT`/`RIGHT` when NOT in detail view → switch pending/completed:
```python
elif key == "RIGHT" and not show_detail and not show_edit:
    view_mode = "completed"
    tasks = task_list(status="completed", limit=50)
    cursor = 0; selected = set(); pending_key = ""

elif key == "LEFT" and not show_detail and not show_edit:
    view_mode = "pending"
    tasks = task_list(status="pending", limit=50)
    cursor = 0; selected = set(); pending_key = ""
```

`LEFT`/`RIGHT` when in detail view → alias for `h`/`l` (prev/next task):
Change:
```python
elif key == "h" and show_detail:
```
to:
```python
elif key in ("h", "LEFT") and show_detail:
```
And:
```python
elif key == "l" and show_detail:
```
to:
```python
elif key in ("l", "RIGHT") and show_detail:
```

Add view direction hint to status bar:
```python
arrow = "\033[33m→\033[0m completed" if view_mode == "pending" else "\033[33m←\033[0m pending"
status_line += f"  │ {arrow}"
```

### 2d. Logo loader + render

After module-level imports, add:
```python
import os as _os
_LOGO_PATH = _os.path.realpath(
    _os.path.join(_os.path.dirname(__file__), "..", "..", "notabene"))
_LOGO_LINES: list = []
try:
    with open(_LOGO_PATH, encoding="utf-8") as _f:
        _LOGO_LINES = [ln.rstrip("\n") for ln in _f]
except Exception:
    pass
```

Add function:
```python
def render_logo(term_width: int) -> list:
    if not _LOGO_LINES:
        return []
    import re
    logo_w = max(len(re.sub(r'\033\[[^m]*m','',l)) for l in _LOGO_LINES)
    if term_width < logo_w + 2:
        return []
    pad = " " * ((term_width - logo_w) // 2)
    return [f"\033[33m{pad}{l}\033[0m" for l in _LOGO_LINES]
```

Add state: `show_logo = True`

In the render block, when no tasks exist OR `show_logo` is True:
```python
if show_logo or not display_tasks:
    logo = render_logo(term_width)
    if logo:
        frame.extend(logo)
        frame.append("")
if not display_tasks:
    frame.append("  (no tasks)  — press a to add")
```

Set `show_logo = False` after the first `key = read_key()` returns.

---

## PART 3 — Fuzzy search (ctrl+f)

**File:** `~/dev/nota/src/tui/app.py`

No external deps. Pure Python fuzzy score.

### 3a. `_fuzzy_score(query, task)` function

```python
def _fuzzy_score(query: str, task: dict) -> int:
    """Score a task against a fuzzy query. Higher = better match. 0 = no match."""
    q = query.lower()
    haystack = " ".join(filter(None, [
        task.get("description", ""),
        task.get("project", ""),
        task.get("scope", ""),
        " ".join(task.get("tags") or []),
        " ".join(
            a.get("description","") for a in (task.get("annotations") or [])
        ),
    ])).lower()

    # Exact substring: highest score
    if q in haystack:
        return 100 + (50 if q in (task.get("description","") or "").lower() else 0)

    # All chars present in order (subsequence match)
    idx = 0
    for ch in q:
        pos = haystack.find(ch, idx)
        if pos == -1:
            return 0
        idx = pos + 1
    # Score by how contiguous the match is
    return max(1, 80 - (idx - len(q)))
```

### 3b. Fuzzy search state

Add to `run()` state block:
```python
fuzzy_query   = ""
fuzzy_results = []   # list of (score, task) sorted desc
fuzzy_active  = False
fuzzy_cursor  = 0
```

### 3c. `ctrl+f` key handler

`read_key()` already returns single chars. `\x06` = Ctrl+F.

```python
elif key == "\x06":   # Ctrl+F
    fuzzy_active = True
    fuzzy_query = ""
    fuzzy_results = []
    fuzzy_cursor = 0
    pending_key = ""
```

### 3d. Fuzzy input + result rendering — when `fuzzy_active` is True

Handle before main dispatch:

```python
if fuzzy_active:
    if key in ("\x06", "ESC", "q"):
        fuzzy_active = False
        fuzzy_query = ""
    elif key in ("\r", "\n"):
        # Confirm: jump to task in main list
        if fuzzy_results:
            _, chosen = fuzzy_results[fuzzy_cursor]
            for i, t in enumerate(display_tasks):
                if t.get("id") == chosen.get("id"):
                    cursor = i
                    break
        fuzzy_active = False
        fuzzy_query = ""
    elif key in ("j", "DOWN"):
        if fuzzy_results:
            fuzzy_cursor = (fuzzy_cursor + 1) % len(fuzzy_results)
    elif key in ("k", "UP"):
        if fuzzy_results:
            fuzzy_cursor = (fuzzy_cursor - 1) % len(fuzzy_results)
    elif key in ("\x7f", "\x08"):
        fuzzy_query = fuzzy_query[:-1]
        fuzzy_results = _run_fuzzy(fuzzy_query, tasks)
        fuzzy_cursor = 0
    elif len(key) == 1 and ord(key) >= 32:
        fuzzy_query += key
        fuzzy_results = _run_fuzzy(fuzzy_query, tasks)
        fuzzy_cursor = 0
    pending_key = ""
    continue
```

Add `_run_fuzzy`:
```python
def _run_fuzzy(query: str, tasks: list) -> list:
    if not query:
        return []
    scored = [(s, t) for t in tasks if (s := _fuzzy_score(query, t)) > 0]
    return sorted(scored, key=lambda x: -x[0])[:15]
```

### 3e. Fuzzy render in frame

In the render block, when `fuzzy_active`:
```python
elif fuzzy_active:
    frame.append(f"  \033[33mfuzzy search:\033[0m {fuzzy_query}\033[1m_\033[0m")
    frame.append("")
    if not fuzzy_query:
        frame.append("  type to search description · project · tags · notes")
    elif not fuzzy_results:
        frame.append("  no matches")
    else:
        for i, (score, t) in enumerate(fuzzy_results):
            marker = "\033[7m" if i == fuzzy_cursor else ""
            reset  = "\033[0m" if i == fuzzy_cursor else ""
            proj   = f"[{t.get('project','')}]" if t.get('project') else ""
            due_s, _ = _due_display(t)
            frame.append(
                f"  {marker}  {t.get('id','?'):>3}  {t.get('description','')[:60]}"
                f"  {proj}  {due_s}{reset}"
            )
    frame.append("")
    frame.append("  \033[33mj/k navigate  enter jump  esc cancel\033[0m")
```

### 3f. Update help text

In `render_full_help()`:
```
ctrl+f          fuzzy search (description/project/tags/notes)
```

---

## PART 4 — Mobile push: `nota cron-check`

### 4a. New webhook endpoint: `POST /nota/push-check`

**File:** `~/dev/nota/src/webhook.py`

Add endpoint after existing routes:

```python
@app.post("/nota/push-check")
def push_check():
    """Called by cron. Returns tasks due within threshold_minutes."""
    import datetime
    threshold = int(request.args.get("minutes", 120))
    now = datetime.datetime.utcnow()
    cutoff = now + datetime.timedelta(minutes=threshold)

    from src.tw import task_list
    tasks = task_list(status="pending", limit=200)
    due_soon = []
    for t in tasks:
        due = t.get("due") or ""
        if not due:
            continue
        try:
            if due[:8].isdigit():
                dt = datetime.datetime.strptime(due[:15], "%Y%m%dT%H%M%S")
            else:
                dt = datetime.datetime.fromisoformat(due[:19])
            if now <= dt <= cutoff:
                due_soon.append({
                    "id": t.get("id"),
                    "description": t.get("description",""),
                    "due": due,
                    "project": t.get("project",""),
                })
        except Exception:
            continue

    return {"due_soon": due_soon, "count": len(due_soon), "checked_at": now.isoformat()}
```

### 4b. New CLI command: `nota cron-check`

**File:** `~/dev/nota/bin/nota`

Add `cron-check` subcommand to argparse:
```python
p_cron = sub.add_parser("cron-check", help="Check for upcoming due tasks and POST to push webhook")
p_cron.add_argument("--minutes", type=int, default=120,
                    help="Tasks due within this many minutes (default: 120)")
p_cron.add_argument("--push-url", default="",
                    help="URL to POST task list to (optional; env: NOTA_PUSH_URL)")
```

Add `cmd_cron_check(args)`:
```python
def cmd_cron_check(args):
    import datetime, json, urllib.request, urllib.error
    from src.tw import task_list

    threshold = args.minutes
    now = datetime.datetime.utcnow()
    cutoff = now + datetime.timedelta(minutes=threshold)

    tasks = task_list(status="pending", limit=200)
    due_soon = []
    for t in tasks:
        due = t.get("due") or ""
        if not due:
            continue
        try:
            if due[:8].isdigit():
                dt = datetime.datetime.strptime(due[:15], "%Y%m%dT%H%M%S")
            else:
                dt = datetime.datetime.fromisoformat(due[:19])
            if now <= dt <= cutoff:
                due_soon.append(t)
        except Exception:
            continue

    if not due_soon:
        print("nota cron-check: no tasks due soon")
        return

    print(f"nota cron-check: {len(due_soon)} task(s) due within {threshold}m")
    for t in due_soon:
        print(f"  [{t.get('id')}] {t.get('description','')}  due:{t.get('due','')[:8]}")

    push_url = args.push_url or os.environ.get("NOTA_PUSH_URL", "")
    if not push_url:
        return

    payload = json.dumps({
        "due_soon": [{"id": t.get("id"), "description": t.get("description",""),
                      "project": t.get("project",""), "due": t.get("due","")}
                     for t in due_soon]
    }).encode()

    token = os.environ.get("NOTA_WEBHOOK_TOKEN", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = urllib.request.Request(push_url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"  pushed to {push_url} → {resp.status}")
    except urllib.error.URLError as e:
        print(f"  push failed: {e}", file=sys.stderr)
```

Wire in dispatch:
```python
elif args.command == "cron-check":
    cmd_cron_check(args)
```

### 4c. launchd plist for cron-check

**File to create:** `~/Library/LaunchAgents/help.cassette.nota.cron.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>help.cassette.nota.cron</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>zsh</string>
    <string>-c</string>
    <string>source ~/.env; /Users/maps/.bin/nota cron-check --minutes 120 --push-url "$NOTA_PUSH_URL"</string>
  </array>
  <key>StartInterval</key>
  <integer>1800</integer>
  <key>StandardOutPath</key>
  <string>/tmp/nota-cron.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/nota-cron.err</string>
</dict>
</plist>
```

Load it:
```zsh
launchctl load ~/Library/LaunchAgents/help.cassette.nota.cron.plist
```

---

## PART 5 — notadash: add nota bene pane + upgrade existing panes

**File:** `~/dev/nota/bin/notadash`

Read the full file before editing.

### 5a. New layout

Current: 7 panes (burndown top-left, next bottom-left, summary top-right, overdue
bottom-right, mapsOS corner, shell corner, calendar bottom strip).

New: Replace mapsOS corner pane with a `nota bene` pane that takes the full right column.

New layout target:
```
┌────────────────────┬────────────────────────────────────┐
│ burndown.daily     │       nota bene (live TUI)         │
│                    │                                    │
├────────────────────│                                    │
│ task next          │                                    │
├────────────────────┤                                    │
│ task overdue       │                                    │
├────────────────────┴────────────────────────────────────┤
│ task calendar (full width bottom strip)                 │
└─────────────────────────────────────────────────────────┘
```

The right column (currently split into summary/mapsOS/overdue/shell) becomes a SINGLE
tall pane running `nota bene`. The left column keeps burndown + next + overdue stacked.

### 5b. Column sizing

```zsh
# Right column: 60% of width for bene (needs room for Rich table)
local bene_cols=$(( COLS * 60 / 100 ))
(( bene_cols < 80 )) && bene_cols=80
(( bene_cols > COLS - 30 )) && bene_cols=$(( COLS - 30 ))
local left_cols=$(( COLS - bene_cols - 1 ))

# Left column rows (excluding calendar strip)
local left_rows=$top_rows
local burn_rows=$(( left_rows * 50 / 100 ))
(( burn_rows < 10 )) && burn_rows=10
local next_rows=$(( left_rows * 30 / 100 ))
(( next_rows < 6 )) && next_rows=6
# overdue gets the remainder
```

### 5c. Pane creation sequence

```zsh
local P_burn P_cal P_bene P_next P_overdue
P_burn=$(tmux display-message -t "$SESSION:dash" -p "#{pane_id}")

# Calendar: bottom strip (full width)
P_cal=$(tmux split-window -v -l $cal_rows -t "$P_burn" -P -F "#{pane_id}")

# nota bene: right column (tall, full left_rows height)
P_bene=$(tmux split-window -h -l $bene_cols -t "$P_burn" -P -F "#{pane_id}")

# Stack left column: next below burndown
P_next=$(tmux split-window -v -l $next_rows -t "$P_burn" -P -F "#{pane_id}")

# Overdue below next
P_overdue=$(tmux split-window -v -l $(( left_rows - burn_rows - next_rows )) \
    -t "$P_next" -P -F "#{pane_id}")
```

### 5d. Pane titles + commands

```zsh
tmux select-pane -t "$P_burn"    -T "burndown"
tmux select-pane -t "$P_cal"     -T "calendar"
tmux select-pane -t "$P_bene"    -T "nota bene"
tmux select-pane -t "$P_next"    -T "next"
tmux select-pane -t "$P_overdue" -T "overdue"

# commands
tmux send-keys -t "$P_burn"    -l -- "clear; task burndown.daily" Enter
tmux send-keys -t "$P_cal"     -l -- "clear; task calendar" Enter
tmux send-keys -t "$P_bene"    -l -- "nota bene" Enter
tmux send-keys -t "$P_next"    -l -- "clear; watch -n30 'task next'" Enter
tmux send-keys -t "$P_overdue" -l -- "clear; watch -n60 'task overdue'" Enter
```

Note: `task next` and `task overdue` wrapped in `watch` so they auto-refresh.

### 5e. Update `_pane_cmd` and `_refresh_pane`

Add/update in `_pane_cmd()`:
```zsh
"bene") print "nota bene" ;;
"next") print "clear; task next" ;;
"overdue") print "clear; task overdue" ;;
```

Remove `summary`, `maps`, `shell` entries (those panes are gone).
Update `_refresh_all` to call `_refresh_pane bene`, `_refresh_pane next`, etc.

For the `bene` pane, `_refresh_pane` should NOT re-run `nota bene` (it's already
running interactively). Skip it:
```zsh
_refresh_pane() {
    local title=$1
    [[ $title == "bene" ]] && return 0  # bene manages itself
    ...
```

### 5f. Key binding update

Update tmux key bindings in the script to reflect new pane set:
```zsh
tmux bind-key -T prefix B select-pane -t "$P_bene"
tmux bind-key -T prefix N select-pane -t "$P_next"
tmux bind-key -T prefix D select-pane -t "$P_overdue"
tmux bind-key -T prefix C select-pane -t "$P_cal"
tmux bind-key -T prefix U select-pane -t "$P_burn"
```

### 5g. Update header comment

```zsh
#   |  burndown.daily           |  nota bene (interactive TUI)      |
#   |                           |                                    |
#   |  task next (watch 30s)    |                                    |
#   |  task overdue (watch 60s) |                                    |
#   |  task calendar (full width, bottom strip)                      |
```

---

## PART 6 — README update

**File:** `~/dev/nota/README.md`

Add sections:

**Smart edit panel** (under TUI key table):
```
e   smart edit panel — h/l or ←/→ between fields; j/k between options;
    tab to focus text input; enter to commit; m for $EDITOR fallback
```

**Fuzzy search:**
```
ctrl+f   fuzzy search — matches description, project, tags, annotations
         j/k to navigate results; enter to jump; esc to cancel
```

**Mobile push:**
```
## Mobile push notifications

nota cron-check runs every 30 minutes via launchd. When tasks are due
within 2 hours it POSTs to $NOTA_PUSH_URL.

Set up an iOS Shortcut with a URL Session automation trigger:
  Trigger: Receives URL from webhook POST
  Action: Show notification with task descriptions

Or use a Pushover/ntfy URL as NOTA_PUSH_URL for zero-config push.
```

**notadash:**
```
## notadash

nota bene + taskwarrior tmux dashboard:

    notadash

Layout: burndown · nota bene (interactive) · task next/overdue · calendar
```

---

## PART 7 — Syntax checks + commit

```zsh
cd ~/dev/nota
python3 -m py_compile src/tui/app.py src/webhook.py bin/nota && echo "syntax ok"
zsh -n bin/notadash && echo "notadash syntax ok"
git add src/tui/app.py src/webhook.py bin/nota bin/notadash README.md \
    ~/Library/LaunchAgents/help.cassette.nota.cron.plist 2>/dev/null || \
git add src/tui/app.py src/webhook.py bin/nota bin/notadash README.md
git commit -m "bene: smart edit, fuzzy search, tearing fix, arrow keys, logo, mobile push, notadash bene pane"
```

Do NOT run `git push`.

---

## DELIVERABLE

Report each part: complete / partial / failed.
For any failure: exact error message + file:line.
If Part 1 partially fails, specify which sub-parts (1a–1h) succeeded.
Git commit hash.
Regressions in: j/k navigation, c (complete), a (add), q/ESC, search (/), bene launch.
