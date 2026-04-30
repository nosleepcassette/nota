# BUILDSHEET: nota bene — Smart Edit + Batch Select + TUI QOL
# maps · cassette.help · MIT
# Target: Codex (autonomous execution)
# Read the full file before any edits: ~/dev/nota/src/tui/app.py

---

## CONTEXT

`nota bene` is a raw-terminal TUI at `~/dev/nota/src/tui/app.py`.
- `task_modify(task_id, **kwargs)` exists in `src/tw.py` — use it for all field updates.
- `task_projects()` in `src/tw.py` returns list of dicts with `project` key.
- `list_scopes()` in `src/scopes.py` returns all valid scopes.
- `read_line(prompt)` already exists in `app.py` — returns `(text, cancelled)`.
- `read_key()` already exists — returns single keypress.
- All edits to ONE file only: `~/dev/nota/src/tui/app.py`.

---

## PART 1 — Smart Edit panel (replaces `e` key)

### 1a. New state variable

In `run()`, add to the state block near the top:
```python
show_edit = False
edit_task = None
edit_field = 0      # which field is highlighted in the edit panel
```

### 1b. `render_edit_panel(task, field_cursor)` function

Add this function. It renders an interactive field list for a task.
Fields (in order, 0-indexed):

| Index | Label      | Current value source        | Edit type     |
|-------|------------|-----------------------------|---------------|
| 0     | Description| `task["description"]`       | free text     |
| 1     | Project    | `task["project"]`           | pick or new   |
| 2     | Scope      | `task.get("scope", "")`     | pick or new   |
| 3     | Priority   | `task["priority"]`          | cycle H/M/L   |
| 4     | Due        | `task.get("due", "")`       | free text (NL)|
| 5     | Tags       | `task.get("tags", [])`      | comma list    |

Render using Rich if available. Each field on its own line.
Highlight the field at `field_cursor` with `reverse` style.
Show current value in amber. Show a one-line footer:
```
j/k navigate  enter edit  m manual($EDITOR)  q back
```

Example output:
```
  ┌─ Edit Task #5 ──────────────────────┐
  │ [>] Description  call the dentist   │
  │     Project      health             │
  │     Scope        digital            │
  │     Priority     M                  │
  │     Due          -                  │
  │     Tags         quick, call        │
  └─────────────────────────────────────┘
  j/k navigate  enter edit  m manual  q back
```

### 1c. Key handling for `show_edit` mode

When `show_edit` is True, handle these keys before the main key block:

```python
if show_edit and edit_task:
    if key in ("j", "DOWN"):
        edit_field = (edit_field + 1) % 6
    elif key in ("k", "UP"):
        edit_field = (edit_field - 1) % 6
    elif key in ("q", "ESC"):
        show_edit = False
        edit_task = None
    elif key == "m":
        # manual $EDITOR fallback
        os.system(f"task {edit_task.get('id')} edit")
        tasks = task_list(status="pending", limit=50)
        show_edit = False
        edit_task = None
    elif key in ("\n", "ENTER"):
        _run_edit_field(edit_task, edit_field)
        # Reload task after modify
        edit_task = task_get(edit_task.get("id"))
        tasks = task_list(status="pending", limit=50)
    pending_key = ""
    continue
```

### 1d. `_run_edit_field(task, field_idx)` function

Add this function. It handles the interactive prompt for each field type:

```python
def _run_edit_field(task: dict, field_idx: int) -> None:
    from src.tw import task_modify, task_projects
    from src.scopes import list_scopes

    task_id = task.get("id")

    if field_idx == 0:  # Description
        show_cursor()
        val, cancelled = read_line(f"  \033[33mDescription: \033[0m")
        hide_cursor()
        if not cancelled and val and val.strip():
            task_modify(task_id, description=val.strip())

    elif field_idx == 1:  # Project — pick list + new
        projects = [p.get("project", "") for p in task_projects() if p.get("project")]
        _pick_or_new(task_id, "project", "Project", projects,
                     lambda v: task_modify(task_id, project=v))

    elif field_idx == 2:  # Scope — pick list + new
        scopes = list(list_scopes().keys()) if hasattr(list_scopes(), "keys") else list_scopes()
        _pick_or_new(task_id, "scope", "Scope", scopes,
                     lambda v: task_modify(task_id, scope=v))

    elif field_idx == 3:  # Priority — cycle H/M/L
        current = task.get("priority", "M")
        cycle = ["H", "M", "L"]
        next_pri = cycle[(cycle.index(current) + 1) % len(cycle)] if current in cycle else "M"
        # Map H/M/L back to p1/p2/p3 for task_modify
        pri_map = {"H": "p1", "M": "p3", "L": "p4"}
        task_modify(task_id, priority_p=pri_map.get(next_pri, "p3"))

    elif field_idx == 4:  # Due — free text, NL accepted
        show_cursor()
        val, cancelled = read_line(f"  \033[33mDue (today/tomorrow/friday/YYYY-MM-DD, blank=clear): \033[0m")
        hide_cursor()
        if not cancelled and val is not None:
            task_modify(task_id, due=val.strip() if val.strip() else "")

    elif field_idx == 5:  # Tags — comma-separated
        current_tags = ", ".join(task.get("tags") or [])
        show_cursor()
        val, cancelled = read_line(f"  \033[33mTags (comma-separated, current: {current_tags}): \033[0m")
        hide_cursor()
        if not cancelled and val is not None:
            new_tags = [t.strip() for t in val.split(",") if t.strip()]
            old_tags = task.get("tags") or []
            to_add = [t for t in new_tags if t not in old_tags]
            to_remove = [t for t in old_tags if t not in new_tags]
            if to_add or to_remove:
                task_modify(task_id, tags_add=to_add, tags_remove=to_remove)
```

### 1e. `_pick_or_new(task_id, field, label, options, apply_fn)` helper

```python
def _pick_or_new(task_id: int, field: str, label: str, options: list, apply_fn) -> None:
    """Render a numbered pick list. User types number or freeform new value."""
    sys.stdout.write("\n")
    for i, opt in enumerate(options[:12]):  # cap at 12 to fit screen
        sys.stdout.write(f"  [{i+1}] {opt}\n")
    sys.stdout.write(f"  [n] enter new {label.lower()}\n")
    sys.stdout.flush()

    show_cursor()
    val, cancelled = read_line(f"  \033[33m{label} (number or new value): \033[0m")
    hide_cursor()

    if cancelled or val is None:
        return

    val = val.strip()
    if val.isdigit():
        idx = int(val) - 1
        if 0 <= idx < len(options):
            apply_fn(options[idx])
    elif val:
        apply_fn(val)
```

### 1f. Wire `e` key to smart edit panel, add `m` as manual fallback

Replace the existing `elif key == "e":` block with:

```python
elif key == "e":
    if display_tasks and cursor < len(display_tasks):
        t = display_tasks[cursor]
        edit_task = task_get(t.get("id"))
        show_edit = True
        show_detail = False
        show_help = False
        show_sort = False
        edit_field = 0
    pending_key = ""

elif key == "m":
    if display_tasks and cursor < len(display_tasks):
        t = display_tasks[cursor]
        os.system(f"task {t.get('id')} edit")
        tasks = task_list(status="pending", limit=50)
    pending_key = ""
```

### 1g. Add `show_edit` to the render block

In the main render block (where `show_detail`, `show_sort`, etc. are checked), add:

```python
elif show_edit and edit_task:
    frame.extend(render_edit_panel(edit_task, edit_field).split("\n"))
```

Place it after the `show_detail` branch, before the default table view.

### 1h. Update banner and help text

Banner: add `(e)dit  (m)anual`
`render_help()`: add `e  smart edit  │  m  manual ($EDITOR)`
`render_full_help()`: add full edit panel key list under Actions.

---

## PART 2 — Batch select + bulk operations

### 2a. New state

```python
selected: set = set()   # set of task IDs currently selected
batch_mode = False
```

### 2b. `x` key — toggle selection on current task

```python
elif key == "x":
    if display_tasks and cursor < len(display_tasks):
        t = display_tasks[cursor]
        tid = t.get("id")
        if tid in selected:
            selected.discard(tid)
        else:
            selected.add(tid)
        # Auto-advance cursor
        if cursor < len(display_tasks) - 1:
            cursor += 1
    pending_key = ""
```

### 2c. `X` (shift-x) — select all visible tasks

```python
elif key == "X":
    all_ids = {t.get("id") for t in display_tasks}
    if all_ids <= selected:
        selected -= all_ids   # all already selected → deselect all
    else:
        selected |= all_ids   # select all visible
    pending_key = ""
```

### 2d. Visual indicator for selected tasks

In `render_tasks_table()` (and `render_table_plain()`), for each row, if `task["id"]` is in `selected`:
- Rich: prepend `[bold green]✓[/]` to the description cell (or use `*` if no unicode)
- Plain: prepend `*` to the line

Pass `selected: set` as a parameter to `render_tasks_table(tasks, cursor, width, selected=None)`.

Update all call sites: `render_tasks_table(display_tasks, cursor, term_width, selected=selected)`

### 2e. `B` key — batch action menu (only when selection is non-empty)

```python
elif key == "B":
    if not selected:
        pass  # nothing to do
    else:
        _run_batch_menu(selected, tasks)
        selected = set()   # clear after action
        tasks = task_list(status="pending", limit=50)
    pending_key = ""
```

### 2f. `_run_batch_menu(selected_ids, tasks)` function

```python
def _run_batch_menu(selected_ids: set, tasks: list) -> None:
    from src.tw import task_done, task_delete, task_modify, task_projects
    from src.scopes import list_scopes

    count = len(selected_ids)
    sys.stdout.write(f"\n  {count} task(s) selected. Action:\n")
    sys.stdout.write("  [c] complete all\n")
    sys.stdout.write("  [d] delete all\n")
    sys.stdout.write("  [p] set project for all\n")
    sys.stdout.write("  [s] set scope for all\n")
    sys.stdout.write("  [r] set priority for all\n")
    sys.stdout.write("  [q] cancel\n")
    sys.stdout.flush()

    show_cursor()
    key, _ = read_line("  \033[33mAction: \033[0m")
    hide_cursor()

    if key == "c":
        for tid in selected_ids:
            try:
                task_done(tid)
            except Exception:
                pass

    elif key == "d":
        confirm, _ = read_line(f"  \033[33mDelete {count} tasks? (y/N): \033[0m")
        if confirm and confirm.strip().lower() == "y":
            for tid in selected_ids:
                try:
                    from src.tw import task_delete
                    task_delete(tid)
                except Exception:
                    pass

    elif key == "p":
        projects = [p.get("project", "") for p in task_projects() if p.get("project")]
        new_proj = None
        for i, opt in enumerate(projects[:12]):
            sys.stdout.write(f"  [{i+1}] {opt}\n")
        sys.stdout.flush()
        val, cancelled = read_line("  \033[33mProject (number or new): \033[0m")
        if not cancelled and val:
            val = val.strip()
            if val.isdigit() and 0 <= int(val)-1 < len(projects):
                new_proj = projects[int(val)-1]
            elif val:
                new_proj = val
        if new_proj:
            for tid in selected_ids:
                try:
                    task_modify(tid, project=new_proj)
                except Exception:
                    pass

    elif key == "s":
        scopes = list(list_scopes().keys()) if hasattr(list_scopes(), "keys") else list_scopes()
        for i, sc in enumerate(scopes[:12]):
            sys.stdout.write(f"  [{i+1}] {sc}\n")
        sys.stdout.flush()
        val, cancelled = read_line("  \033[33mScope (number or new): \033[0m")
        if not cancelled and val:
            val = val.strip()
            if val.isdigit() and 0 <= int(val)-1 < len(scopes):
                new_scope = scopes[int(val)-1]
            else:
                new_scope = val
            for tid in selected_ids:
                try:
                    task_modify(tid, scope=new_scope)
                except Exception:
                    pass

    elif key == "r":
        val, cancelled = read_line("  \033[33mPriority (H/M/L): \033[0m")
        if not cancelled and val:
            pri_map = {"h": "p1", "m": "p3", "l": "p4"}
            p = pri_map.get(val.strip().lower())
            if p:
                for tid in selected_ids:
                    try:
                        task_modify(tid, priority_p=p)
                    except Exception:
                        pass
```

### 2g. Show selection count in status bar

Append to `status_line` when `selected` is non-empty:
```python
if selected:
    status_line += f"  │ \033[33m{len(selected)} selected\033[0m  (B=batch X=all x=toggle)"
```

### 2h. Clear selection on view change / quit

Add `selected = set()` when:
- `q` exits (before `break`)
- `ESC` clears panels

---

## PART 3 — Additional QOL (smaller items, do these after Parts 1+2)

### 3a. `n` key — add annotation to current task

```python
elif key == "n":
    if display_tasks and cursor < len(display_tasks):
        t = display_tasks[cursor]
        show_cursor()
        text, cancelled = read_line("  \033[33mnote: \033[0m")
        hide_cursor()
        if not cancelled and text and text.strip():
            from src.tw import task_annotate
            task_annotate(t.get("id"), text.strip())
            # Reload if in detail view
            if show_detail and detail_task:
                detail_task = task_get(t.get("id"))
    pending_key = ""
```

### 3b. `tab` key — toggle between pending / completed views

Add state: `view_mode: str = "pending"` (values: `"pending"` / `"completed"`)

`TAB` key (`\t`):
```python
elif key == "\t":
    view_mode = "completed" if view_mode == "pending" else "pending"
    tasks = task_list(status=view_mode, limit=50)
    cursor = 0
    selected = set()
    pending_key = ""
```

Show current view in the status bar: `status_line += f"  │ view: {view_mode}"`

### 3c. `o` key — quick sort cycle

Cycle: `id → priority → due → project → scope → id`

```python
elif key == "o":
    sort_cycle = ["id", "priority", "due", "project", "scope"]
    idx = sort_cycle.index(sort_by) if sort_by in sort_cycle else 0
    sort_by = sort_cycle[(idx + 1) % len(sort_cycle)]
    _save_tui_state({"sort_by": sort_by, "sort_reverse": sort_reverse})
    pending_key = ""
```

### 3d. `O` (shift-o) — reverse current sort

```python
elif key == "O":
    sort_reverse = not sort_reverse
    _save_tui_state({"sort_by": sort_by, "sort_reverse": sort_reverse})
    pending_key = ""
```

---

## PART 4 — Update help text

Update `render_full_help()` to cover all new keys:

```
  [bold amber]Edit[/bold amber]
    e               smart edit panel (field-by-field)
    m               manual edit ($EDITOR)
    n               add note/annotation

  [bold amber]Batch select[/bold amber]
    x               toggle select current task (advances cursor)
    X               select / deselect all visible
    B               batch action menu (complete/delete/project/scope/priority)

  [bold amber]View[/bold amber]
    tab             toggle pending / completed
    o               cycle sort (id→priority→due→project→scope)
    O               reverse sort
    f / F           filter by project / clear filter
```

Update `render_help()` (short version) to fit on one banner line.

---

## PART 5 — Syntax check + commit

```zsh
cd ~/dev/nota
python3 -m py_compile src/tui/app.py && echo "syntax ok"
git add src/tui/app.py
git commit -m "bene: smart edit panel, batch select, annotation, tab view, sort cycle"
```

Do NOT run `git push`.

---

## DELIVERABLE

Report back with:
1. Part 1 (smart edit): complete / partial / failed — which sub-parts
2. Part 2 (batch): complete / partial / failed — which sub-parts
3. Part 3 (QOL): which of 3a–3d complete
4. Syntax check: pass / fail (include error if fail)
5. Git commit hash
6. Any regressions noticed in existing keys (q, c, a, /, ESC, j/k)

If any part fails, include exact error and the line number where it failed.
