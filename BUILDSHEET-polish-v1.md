# BUILDSHEET: nota bene — Arrow Keys, Screen Tearing, Logo, README
# maps · cassette.help · MIT
# Target: Codex (autonomous execution)
# Read ~/dev/nota/src/tui/app.py IN FULL before editing. One coherent pass.

---

## CONTEXT

`nota bene` is a raw-terminal TUI at `~/dev/nota/src/tui/app.py`.

Current rendering:
- Every frame: `sys.stdout.write("\033[2J\033[H")` — full clear → redraw. This is
  the source of visible screen tearing/flicker on every keypress.
- `first_render` flag only clears on the very first frame; subsequent clears happen
  inside the main render block at line ~736.

Current arrow key state:
- `read_key()` decodes escape sequences and returns `"UP"` / `"DOWN"` / `"LEFT"` / `"RIGHT"`.
- The main key dispatch handles `j/DOWN` and `k/UP` for navigation.
- `LEFT` / `RIGHT` are not handled anywhere — they fall through to `pending_key = ""`.
- Terminal resize (`SIGWINCH`) is not caught — `term_width` is set once at startup and
  never updated.

Logo:
- File at `~/dev/nota/notabene` — 11 lines of block-character ASCII art, 96 chars wide
  (including border chars `▐` / `▌`).
- Currently not displayed anywhere in the TUI.

README at `~/dev/nota/README.md` — last updated this session; needs a polish pass.

---

## PART 1 — Fix screen tearing (double-buffer render)

**File:** `~/dev/nota/src/tui/app.py`

### 1a. Replace full-clear with cursor-home + erase-to-end

The standard fix for tearing in raw-terminal apps: instead of `\033[2J\033[H`
(clear entire screen), use `\033[H` (move to home) then render the frame, then
`\033[J` (erase from cursor to end of screen) AFTER writing all content.

Replace this block:
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
sys.stdout.write("\033[H")          # move cursor to top-left
sys.stdout.write(output)            # write full frame
sys.stdout.write("\033[J")          # erase everything after current cursor
sys.stdout.flush()
```

Also update `clear_screen()` to keep using full `\033[2J\033[H` (that's fine on initial
launch and explicit clears — only the per-frame render needs the fix).

### 1b. Remove the `first_render` flag

With the new approach, the first render is identical to every subsequent render —
`\033[H` on an empty screen is effectively a clear. Remove:
- `first_render = True` state variable
- The `if first_render: clear_screen(); first_render = False` block

### 1c. Handle terminal resize (SIGWINCH)

Add at the top of the file (after imports):
```python
import signal

_term_resized = False

def _handle_sigwinch(signum, frame):
    global _term_resized
    _term_resized = True

signal.signal(signal.SIGWINCH, _handle_sigwinch)
```

In the main render loop, at the very top of the `while True:` body (before building
`frame`), add:
```python
global _term_resized
if _term_resized:
    term_width = get_term_size().columns
    _term_resized = False
    sys.stdout.write("\033[2J\033[H")  # full clear on resize to avoid artifacts
    sys.stdout.flush()
```

---

## PART 2 — Arrow key navigation (left/right for view switching)

**File:** `~/dev/nota/src/tui/app.py`

### 2a. LEFT / RIGHT in normal mode

`LEFT` and `RIGHT` currently fall through to `pending_key = ""` with no effect.
Wire them to view switching (pending / completed toggle):

Find the key dispatch block. After the existing `j/k/UP/DOWN` handler, add:

```python
elif key == "RIGHT":
    if view_mode == "pending":
        view_mode = "completed"
        tasks = task_list(status="completed", limit=50)
        cursor = 0
        selected = set()
    pending_key = ""

elif key == "LEFT":
    if view_mode == "completed":
        view_mode = "pending"
        tasks = task_list(status="pending", limit=50)
        cursor = 0
        selected = set()
    pending_key = ""
```

### 2b. LEFT / RIGHT in sort menu

When `show_sort` is True, LEFT/RIGHT should not interfere with the sort menu — they
should just close the sort menu and switch view (same as above). The existing dispatch
already handles `show_sort` before the general key block, so no change needed there.

### 2c. LEFT / RIGHT in detail view (already wired as h/l)

`h`/`l` already navigate prev/next task in detail view. Wire LEFT/RIGHT as aliases:

Find:
```python
elif key == "h" and show_detail:
```
Change to:
```python
elif key in ("h", "LEFT") and show_detail:
```

Find:
```python
elif key == "l" and show_detail:
```
Change to:
```python
elif key in ("l", "RIGHT") and show_detail:
```

### 2d. Arrow indicator in status bar

When multiple views are available, show a directional hint:
```python
if view_mode == "pending":
    status_line += "  \033[33m→\033[0m completed"
else:
    status_line += "  \033[33m←\033[0m pending"
```

---

## PART 3 — Centered dynamic logo

**File:** `~/dev/nota/src/tui/app.py`

### 3a. Load logo from file

Add a module-level loader after the imports:

```python
import os as _os
_LOGO_PATH = _os.path.join(_os.path.dirname(__file__), "..", "..", "notabene")
_LOGO_LINES: list = []
try:
    with open(_os.path.realpath(_LOGO_PATH), encoding="utf-8") as _f:
        _LOGO_LINES = [line.rstrip("\n") for line in _f.readlines()]
except Exception:
    pass
```

### 3b. `render_logo(term_width)` function

Add this function:

```python
def render_logo(term_width: int) -> list:
    """Return logo lines centered for the current terminal width.
    Falls back to empty list if terminal is too narrow or logo not loaded."""
    if not _LOGO_LINES:
        return []
    # Strip ANSI from logo lines to measure visual width
    import re
    def visual_width(line):
        return len(re.sub(r'\033\[[^m]*m', '', line))
    logo_w = max(visual_width(l) for l in _LOGO_LINES) if _LOGO_LINES else 0
    if term_width < logo_w + 2:
        return []   # too narrow — skip logo
    pad = (term_width - logo_w) // 2
    return [(" " * pad) + line for line in _LOGO_LINES]
```

### 3c. Show logo when task list is empty or on startup

The logo should appear:
- **Always at startup** if the terminal is wide enough, above the task table, for the
  first render only (use a `show_logo` state that turns False after first keypress OR
  after any task interaction)
- **When task list is empty** — replace the "(no tasks)" placeholder with the logo

For the startup splash: add state `show_logo = True`. After the first keypress, set
`show_logo = False`.

In the render block, BEFORE building the task table section:
```python
if show_logo or not display_tasks:
    frame.extend(render_logo(term_width))
    frame.append("")
```

If `show_logo` is True and there ARE tasks, show logo above the table.
If task list is empty, logo replaces the table entirely (append a hint line after it):
```python
if not display_tasks:
    frame.extend(render_logo(term_width))
    frame.append("")
    frame.append("  (no tasks)  — press a to add")
```

Set `show_logo = False` after the first `read_key()` call returns.

### 3d. Add amber color to logo

Wrap the centered logo lines in ANSI amber `\033[33m` ... `\033[0m` (per line):

```python
return [f"\033[33m{(' ' * pad)}{line}\033[0m" for line in _LOGO_LINES]
```

---

## PART 4 — README update

**File:** `~/dev/nota/README.md`

Rewrite the README. Keep it under 150 lines. Structure:

```markdown
# nota bene
**maps · cassette.help · MIT**

Intelligent task CLI + TUI backed by taskwarrior. NLP-forward input, agent-first design.
iOS capture via webhook. Vim keybindings.

---

## Install

```bash
cd ~/dev/nota
pip install -r requirements.txt
make dev          # creates ~/.bin/nota symlink (run once)
```

No rebuild step. `bin/nota` runs from source via symlink.

---

## nota bene (TUI)

```
nota bene
```

| Key | Action |
|-----|--------|
| j / ↓ | move down |
| k / ↑ | move up |
| ← / → | switch pending / completed view |
| a | add task (inline syntax or freeform NLP) |
| c | mark complete |
| e | smart edit panel |
| m | manual edit ($EDITOR) |
| n | add note/annotation |
| x / X | select task / select all |
| B | batch action (complete/delete/project/scope/priority) |
| o / O | cycle sort / reverse sort |
| f / F | filter by project / clear filter |
| tab | toggle pending / completed |
| v / enter | view task detail |
| dd / D | delete task |
| / | search |
| ? | help |
| q / ESC | back / quit |

---

## nota add — inline syntax

```
nota add "call dentist @health due:friday p2 scope:meatspace #quick"
nota add "take meds @health due:today recur:daily p1"
nota add "https://example.com"       # URL capture — fetches title
nota add "remind me to call mom"     # freeform → NLP (Gemini), confirm before save
nota add --yes "reminder for codex"  # skip NLP confirm
```

**Syntax tokens:**

| Token | Meaning | Example |
|-------|---------|---------|
| `@project` | project | `@health` |
| `#tag` | tag | `#quick #errand` |
| `p1`–`p4` | priority | `p1` urgent, `p4` someday |
| `due:DATE` | due date (taskwarrior NL) | `due:friday` `due:eow` |
| `scope:X` | scope | `scope:meatspace` `scope:digital` |
| `recur:X` | recurrence | `recur:daily` `recur:weekly` |
| `until:DATE` | recurrence end | `until:2026-12-31` |
| `->` | prereq (A depends on B) | `"reply -> find stamps"` |
| `::` | related-to | `"task A :: task B"` |

---

## Other commands

```
nota list [--project X] [--scope X]   list tasks
nota next                              top urgent tasks
nota done ID                           mark complete
nota show ID                           full task detail
nota capture "text"                    instant inbox (no NLP, no confirm)
nota braindump "text"                  multi-task NLP parse
nota triage                            interactive inbox processing
nota sync                              git backup of ~/.task/
nota webhook [--port 5055]             iOS capture server
nota mcp                               MCP stdio server
```

---

## iOS integration

Webhook runs at `https://nota.cassette.quest/nota/`

```
POST /nota/capture   {"text": "task description"}   → creates task
GET  /nota/next                                      → top 5 tasks
GET  /nota/health                                    → {"status": "ok"}
```

Add `Authorization: Bearer $NOTA_WEBHOOK_TOKEN` header if token is set.

**iOS Shortcut (Add to nota):**
1. Ask for Input → prompt: "Task"
2. Get Contents of URL: POST `https://nota.cassette.quest/nota/capture`
   Body JSON: `{"text": "[Provided Input]"}`
   Header: `Authorization: Bearer <your token>`

---

## Agent integration (MCP)

```json
"nota": { "command": "/Users/maps/.bin/nota", "args": ["mcp"] }
```

Tools: `nota_add`, `nota_list`, `nota_show`, `nota_done`, `nota_capture`, `nota_projects`

---

## Data

`~/.task/` — taskwarrior data. Back up with `nota sync`.
`~/.config/nota/tui_state.json` — sort/view preferences.
```

Write this content verbatim to `~/dev/nota/README.md`, replacing the existing file entirely.

---

## PART 5 — Syntax check + commit

```zsh
cd ~/dev/nota
python3 -m py_compile src/tui/app.py && echo "syntax ok"
git add src/tui/app.py README.md
git commit -m "bene: double-buffer render, arrow keys, centered logo, README rewrite"
```

Do NOT run `git push`.

---

## DELIVERABLE

1. Part 1 (tearing fix): complete / partial / failed + describe what changed
2. Part 2 (arrow keys): complete / partial / failed
3. Part 3 (logo): complete / partial / failed — does it display on launch?
4. Part 4 (README): complete / partial / failed
5. Syntax check: pass / fail (error + line if fail)
6. Git commit hash
7. Any regressions in existing keys (j/k/c/a/q/ESC)
