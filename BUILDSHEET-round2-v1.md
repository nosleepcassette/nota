# BUILDSHEET: nota Round 2 — Smart Add, Recur, Dependency View, URL Capture
# maps · cassette.help · MIT
# Target: Codex (autonomous execution)
# Read ALL target files fully before editing. Make one coherent pass per file.

---

## CONTEXT

State after Round 1 (BUILDSHEET-edit-batch-v1.md):
- `src/tui/app.py` — smart edit panel, batch select, sort cycle, tab view, `read_line()`
- `src/parse.py` — `parse_inline()` + `_looks_freeform()`
- `src/tw.py` — `task_modify()`, `task_projects()`, `task_depend()`, `fmt_detail()` (dep resolution)
- `bin/nota` — NLP routing for `cmd_add`, `--dry-run`, `--confirm` flags on braindump

`nota add` NLP fires on freeform text (≥4 words, no syntax tokens) but silently saves
without showing the user what was inferred. Dependency titles are resolved in `tw.fmt_detail`
but NOT shown in the TUI's `render_task_detail`. `parse_inline` has no `recur:` token.
URL capture (`nota add https://...`) does nothing smart.

Target files:
- `~/dev/nota/src/parse.py`
- `~/dev/nota/src/tui/app.py`
- `~/dev/nota/bin/nota`

---

## PART 1 — `nota add` NLP confirm-before-save

**File:** `~/dev/nota/bin/nota` — in `cmd_add()`, after `t = nlp_single_task(text)` succeeds.

Currently the task is added silently. Insert a confirm step:

```python
# After nlp_single_task() returns t:
pri_display = t.get("priority", "M")
due_display = t.get("due") or "-"
scope_display = t.get("scope") or "-"
tags_display = ", ".join(t.get("tags") or []) or "-"
proj_display = t.get("project") or "inbox"
desc_display = text   # always use original text as description

print(f"\n  \033[1;33m→\033[0m {desc_display}")
print(f"     project: {proj_display}  |  priority: {pri_display}  |  due: {due_display}")
print(f"     scope: {scope_display}  |  tags: {tags_display}")
print(f"\n  \033[33m[enter] save  [e] edit fields  [n] cancel\033[0m  ", end="", flush=True)

try:
    choice = input().strip().lower()
except (EOFError, KeyboardInterrupt):
    print("\ncancelled")
    return

if choice == "n":
    print("cancelled")
    return

if choice == "e":
    # Let user override each field interactively
    new_proj = input(f"  project [{proj_display}]: ").strip() or proj_display
    new_due = input(f"  due [{due_display}]: ").strip() or (t.get("due") or None)
    new_scope = input(f"  scope [{scope_display}]: ").strip() or scope_display
    new_tags_raw = input(f"  tags [{tags_display}]: ").strip()
    new_tags = [x.strip() for x in new_tags_raw.split(",") if x.strip()] if new_tags_raw else (t.get("tags") or [])
    proj_display = new_proj
    if new_due and new_due != "-":
        t["due"] = new_due
    else:
        t["due"] = None
    scope_display = new_scope if new_scope != "-" else ""
    tags_display_list = new_tags
else:
    tags_display_list = t.get("tags") or []
    scope_display = t.get("scope") or ""

# Now save with confirmed values
from src.scopes import is_valid_scope
scope = scope_display.strip() if scope_display and is_valid_scope(scope_display.strip()) else None

task = task_add(
    description=text,
    project=proj_display or "inbox",
    priority_p=_priority_map(str(t.get("priority", "M")).upper()),
    due=t.get("due") or None,
    tags=tags_display_list if isinstance(tags_display_list, list) else [],
    scope=scope,
)
print(f"+ [{task.get('id','?')}] {task.get('description','')}  (nlp)")
return
```

Replace the existing `task = task_add(...)` + `print(...)` + `return` block in the NLP
branch of `cmd_add()`. Keep the `except Exception as e` fallback intact beneath it.

Also: add `--yes` / `-y` flag to `nota add` argparse that skips the confirm step (for
piping / scripting). When `args.yes` is True, skip the confirm block and save directly.

```python
# in argparse setup for `add` subcommand:
p_add.add_argument("--yes", "-y", action="store_true",
                   help="Skip NLP confirm prompt (for scripting)")
```

Pass `args.yes` into `cmd_add` and gate the confirm block: `if not args.yes:`.

---

## PART 2 — `recur:` token in `parse_inline`

**File:** `~/dev/nota/src/parse.py`

Add `recur` and `until` to the token parser in `parse_inline()`.

### 2a. Update return dict

Add to the `return` dict:
```python
"recur": recur,     # str or None — e.g. "daily", "weekly", "monthly"
"until": until,     # str or None — end date for recurrence
```

Initialize at top of function body:
```python
recur = None
until = None
```

### 2b. Token parsing

In the `for token in text.split():` loop, add after the `due:` branch:

```python
elif low.startswith("recur:"):
    recur = token[6:]
    tokens_to_remove.append(token)
elif low.startswith("until:"):
    until = token[6:]
    tokens_to_remove.append(token)
```

Valid recur values to accept as-is (no normalization needed):
`daily`, `weekly`, `biweekly`, `monthly`, `quarterly`, `annual`, `weekdays`

### 2c. Wire recur into `cmd_add` (inline branch)

**File:** `~/dev/nota/bin/nota` — in `cmd_add()`, in the `parse_inline` branch (not the NLP branch).

After `parsed = parse_inline(text)`, if `parsed["recur"]` is set and `args.recur` is not
already set, use `parsed["recur"]` as `recur`. Same for `parsed["until"]`.

```python
recur = args.recur or parsed.get("recur")
until = args.until or parsed.get("until")
```

This makes `nota add "take meds p1 @health due:today recur:daily"` work end-to-end.

---

## PART 3 — URL capture

**File:** `~/dev/nota/bin/nota` — in `cmd_add()`, before the `_looks_freeform` check.

If `text` starts with `http://` or `https://`, treat it as a URL capture:

```python
import re as _re
_URL_RE = _re.compile(r'^https?://', _re.I)

if _URL_RE.match(text):
    _handle_url_add(text, args)
    return
```

Add `_handle_url_add(url, args)` function near `cmd_add`:

```python
def _handle_url_add(url: str, args) -> None:
    """Fetch page title from URL and create task with URL annotated."""
    title = None
    try:
        import urllib.request, html
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 nota/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read(8192).decode("utf-8", errors="ignore")
        import re
        m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
        if m:
            title = html.unescape(m.group(1)).strip()[:120]
    except Exception:
        pass

    description = title or url
    print(f"  url: {url}")
    print(f"  title: {title or '(could not fetch)'}")

    task = task_add(
        description=description,
        project=args.project if hasattr(args, "project") and args.project else "inbox",
        tags=["url"],
    )
    if task and task.get("id"):
        from src.tw import task_annotate
        task_annotate(task["id"], url)
        print(f"+ [{task.get('id','?')}] {description}  (url)")
    else:
        print("  failed to create task", file=sys.stderr)
```

---

## PART 4 — Dependency view in TUI detail panel

**File:** `~/dev/nota/src/tui/app.py` — in `render_task_detail(t)`.

Currently `render_task_detail` does NOT show dependencies. The resolution logic already
exists in `src/tw.py:fmt_detail` (lines ~357–368): it walks `t["depends"]` (list of UUIDs),
looks up each by `uuid:X export`, and formats `✓ [id] description` or `○ [id] description`.

Port that logic into `render_task_detail` for both Rich and plain branches.

After the annotations block, add (Rich branch):

```python
depends = t.get("depends") or []
if depends:
    lines.append(f"  [bold {AMBER}]Depends on (prerequisites)[/]")
    for dep_uuid in depends:
        try:
            from src.tw import _run_json
            found = _run_json(f"uuid:{dep_uuid}", "export")
            if found:
                d = found[0]
                mark = "[green]✓[/green]" if d.get("status") == "completed" else "[yellow]○[/yellow]"
                lines.append(f"    {mark} [{d.get('id','?')}] {d.get('description','')}")
        except Exception:
            lines.append(f"    ○ (uuid: {dep_uuid[:8]}...)")

# Also show tasks that depend ON this task (it blocks them)
this_uuid = t.get("uuid", "")
if this_uuid:
    try:
        from src.tw import _run_json
        blocking = _run_json(f"depends.is:{this_uuid}", "export") or []
        if blocking:
            lines.append(f"  [bold {AMBER}]Blocks[/]")
            for b in blocking:
                lines.append(f"    → [{b.get('id','?')}] {b.get('description','')}")
    except Exception:
        pass
```

Add the same without Rich markup to the plain text branch.

---

## PART 5 — `nota add` `--project` and `--scope` flags

**File:** `~/dev/nota/bin/nota` — argparse setup for the `add` subcommand.

Add explicit flags as shortcuts (they override anything parsed from the inline text):

```python
p_add.add_argument("--project", "-p", help="Override project")
p_add.add_argument("--scope",   "-s", help="Override scope")
p_add.add_argument("--due",     "-d", help="Override due date")
p_add.add_argument("--priority","-r", help="Override priority (p1-p4 or H/M/L)")
```

In `cmd_add()`, after `parse_inline()`:
```python
if args.project:
    parsed["project"] = args.project
if args.scope:
    parsed["scope"] = args.scope
if getattr(args, "due", None):
    parsed["due_date"] = args.due
if getattr(args, "priority", None):
    # normalize p1-p4 or H/M/L
    pr = args.priority.lower()
    pmap = {"p1":"1","p2":"2","p3":"3","p4":"4","h":"1","m":"3","l":"4"}
    if pr in pmap:
        parsed["priority"] = int(pmap[pr])
```

In the NLP branch, apply the same overrides to `t` dict after `nlp_single_task()`.

---

## PART 6 — `nota add` quick confirmation display (non-NLP)

**File:** `~/dev/nota/bin/nota` — in `cmd_add()`, inline branch (after `parse_inline`).

Currently the inline branch adds silently. Print a one-line confirmation:

```python
print(f"+ [{task.get('id','?')}] {task.get('description','')}  "
      f"[{parsed['project']}] {f'due:{parsed[\"due_date\"]}' if parsed['due_date'] else ''}")
```

This is already partially there — make sure it's present and includes project + due.

---

## PART 7 — Smoke tests

```zsh
# NLP confirm flow
nota add "remind me to call the pharmacy on monday"
# → should print inferred fields and wait for enter/e/n

# NLP with --yes (no prompt)
nota add --yes "remind me to call the pharmacy on monday"
# → should save immediately, print one-line confirmation

# recur inline
nota add "take meds p1 @health due:today recur:daily"
nota show <ID>
# → should show recur:daily in taskwarrior

# URL capture
nota add "https://en.wikipedia.org/wiki/Taskwarrior"
# → should create task with title as description, URL as annotation

# --project flag override
nota add "test override @inbox --project health"
# → should save to project:health (flag wins)

# dependency view in TUI
# Open nota bene → select a task with depends → press enter/v
# → should show "Depends on" section with titles

# batch select smoke
# nota bene → x on 3 tasks → B → c → confirm all complete
```

Report pass/fail per test. Include first 3 lines of output for each.

---

## PART 8 — Syntax check + commit

```zsh
cd ~/dev/nota
python3 -m py_compile src/parse.py src/tui/app.py bin/nota 2>&1
git add src/parse.py src/tui/app.py bin/nota
git commit -m "nota: NLP confirm, recur: token, URL capture, dep view in TUI, --project/--scope flags"
```

Do NOT run `git push`.

---

## DELIVERABLE

1. Part 1 (NLP confirm + --yes): complete / partial / failed
2. Part 2 (recur: token): complete / partial / failed
3. Part 3 (URL capture): complete / partial / failed
4. Part 4 (dep view in TUI): complete / partial / failed
5. Part 5 (--project/--scope flags): complete / partial / failed
6. Part 6 (inline confirm line): complete / partial / failed
7. Smoke test results: pass/fail per test (with first 3 lines of output)
8. Syntax check: pass / fail (error + line if fail)
9. Git commit hash

Any failure: exact error message and file:line.
