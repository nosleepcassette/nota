# maps · cassette.help · MIT
"""
nota bene - TUI entrypoint.

Launch with: nota bene
Style: vim keybindings, table-based, no emojis, amber theme.
"""

import datetime
import json
import os
import os as _os
import signal as _signal
import sys
import select
import termios
import tty
from io import StringIO
from pathlib import Path
from typing import Optional, List, Dict

try:
    from rich import box
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


_term_resized = False


def _handle_sigwinch(signum, frame):
    global _term_resized
    _term_resized = True


_signal.signal(_signal.SIGWINCH, _handle_sigwinch)

AMBER = "rgb(255,176,0)"
AMBER_BRIGHT = "rgb(255,200,50)"
AMBER_DIM = "rgb(210,160,0)"
CURSOR_AMBER = "rgb(255,140,0)"

_TUI_STATE_PATH = Path.home() / ".config" / "nota" / "tui_state.json"
_LOGO_PATH = _os.path.realpath(
    _os.path.join(_os.path.dirname(__file__), "..", "..", "notabene")
)
_LOGO_LINES: list = []
try:
    with open(_LOGO_PATH, encoding="utf-8") as _f:
        _LOGO_LINES = [ln.rstrip("\n") for ln in _f]
except Exception:
    pass

EDIT_FIELDS = [
    {"key": "description", "label": "Description", "type": "text"},
    {"key": "project", "label": "Project", "type": "pick"},
    {"key": "scope", "label": "Scope", "type": "pick"},
    {"key": "priority", "label": "Priority", "type": "cycle", "options": ["H", "M", "L"]},
    {"key": "due", "label": "Due", "type": "time"},
    {"key": "tags", "label": "Tags", "type": "text"},
]


def _load_tui_state() -> dict:
    try:
        if _TUI_STATE_PATH.exists():
            return json.loads(_TUI_STATE_PATH.read_text())
    except Exception:
        pass
    return {}


def _save_tui_state(state: dict) -> None:
    try:
        _TUI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TUI_STATE_PATH.write_text(json.dumps(state))
    except Exception:
        pass


def _due_display(task: dict) -> tuple:
    """Returns (display_str, style) for due date column."""
    due = task.get("due") or task.get("dueDate") or ""
    if not due:
        return "-", ""
    try:
        due = str(due)
        if due[:8].isdigit():
            dt = datetime.datetime.strptime(due[:8], "%Y%m%d").date()
        elif len(due) >= 10:
            dt = datetime.date.fromisoformat(due[:10])
        else:
            return due[:5], ""
        today = datetime.date.today()
        delta = (dt - today).days
        if delta < 0:
            return f"{abs(delta)}d ago", "bold red"
        if delta == 0:
            return "today", "bold yellow"
        if delta == 1:
            return "tmrw", "yellow"
        if delta <= 7:
            return f"{delta}d", "rgb(255,176,0)"
        return dt.strftime("%m/%d"), ""
    except Exception:
        return due[:5], ""


def strip_markup(text: str) -> str:
    import re

    return (
        re.sub(r"\[/?[^\]]+\]", "", str(text)).replace(r"\[", "[").replace(r"\]", "]")
    )


def read_key() -> str:
    if not sys.stdin.isatty():
        try:
            text = input().strip()
        except EOFError:
            return "q"
        if text == "\x1b":
            return "ESC"
        return text[:1] if text else ""

    def decode(seq: str) -> str:
        if seq == "":
            return ""
        seq = seq.lstrip("[O")
        first_char = seq[0] if seq else ""
        if first_char == "A":
            return "UP"
        if first_char == "B":
            return "DOWN"
        if first_char == "C":
            return "RIGHT"
        if first_char == "D":
            return "LEFT"
        return ""

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)

        if ch == "\x1b":
            suffix = ""
            while True:
                ready, _, _ = select.select([sys.stdin], [], [], 0.05)
                if not ready:
                    break
                suffix += os.read(fd, 16).decode(errors="ignore")
                if len(suffix) > 10:
                    break
            decoded = decode(suffix)
            if decoded:
                return decoded
            return "ESC"
        if ch == "\x03":
            return "CTRL_C"
        if ch == "\x04":
            return "CTRL_D"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def hide_cursor():
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def read_line(prompt: str) -> tuple:
    """Read a line of input in raw mode. Returns (text, cancelled).
    ESC or CTRL+C → (None, True). Supports backspace and basic editing."""
    sys.stdout.write(prompt)
    sys.stdout.flush()

    if not sys.stdin.isatty():
        try:
            return (input(), False)
        except EOFError:
            return ("", True)

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    buf = []

    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)

            if ch in ("\x1b", "\x03"):          # ESC or Ctrl+C → cancel
                return (None, True)
            elif ch in ("\r", "\n"):             # Enter → confirm
                sys.stdout.write("\n")
                sys.stdout.flush()
                return ("".join(buf), False)
            elif ch in ("\x7f", "\x08"):         # Backspace
                if buf:
                    buf.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif ch == "\x1b":                  # escape seq (shouldn't reach here)
                return (None, True)
            elif ord(ch) >= 32:                 # printable
                buf.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def get_term_size():
    try:
        return os.get_terminal_size()
    except:
        return os.terminal_size((80, 24))


def render_logo(term_width: int) -> list:
    if not _LOGO_LINES:
        return []
    import re

    logo_w = max(len(re.sub(r"\033\[[^m]*m", "", line)) for line in _LOGO_LINES)
    if term_width < logo_w + 2:
        return []
    pad = " " * ((term_width - logo_w) // 2)
    return [f"\033[33m{pad}{line}\033[0m" for line in _LOGO_LINES]


def _load_edit_picks(field_key: str) -> list:
    if field_key == "project":
        try:
            from src.tw import task_projects

            return sorted({p.get("project", "") for p in task_projects() if p.get("project")})
        except Exception:
            return []
    if field_key == "scope":
        try:
            from src.scopes import list_scopes

            scopes = list_scopes()
            if isinstance(scopes, dict):
                return sorted(scopes.keys())
            return sorted(s.get("name", "") for s in scopes if s.get("name"))
        except Exception:
            return []
    return []


def _build_time_options() -> list:
    opts = ["clear", "today", "tomorrow", "end of week"]
    today = datetime.date.today()
    for i in range(1, 15):
        d = today + datetime.timedelta(days=i)
        opts.append(f"{d:%Y-%m-%d} ({d:%a} {d:%b} {d.day})")

    now = datetime.datetime.now()
    base = now.replace(second=0, microsecond=0)
    mins = (base.minute // 15 + 1) * 15
    base = base.replace(minute=0) + datetime.timedelta(minutes=mins)
    for i in range(16):
        t = base + datetime.timedelta(minutes=i * 15)
        opts.append("today " + t.strftime("%I:%M%p").lstrip("0").lower())
    return opts


def _edit_field_options(field_idx: int, edit_pick: list) -> list:
    field_def = EDIT_FIELDS[field_idx]
    ftype = field_def["type"]
    if ftype == "cycle":
        return field_def.get("options", [])
    if ftype == "time":
        return _build_time_options()
    return edit_pick


def _edit_current_value(task: dict, field_key: str) -> str:
    if field_key == "tags":
        return ", ".join(task.get("tags") or []) or "-"
    value = task.get(field_key)
    if field_key == "due" and value:
        return str(value)
    return str(value or "-")


def render_edit_panel(
    task: dict,
    field: int,
    col: int,
    picks: list,
    input_buf: str,
    input_active: bool,
    term_width: int,
) -> List[str]:
    field_def = EDIT_FIELDS[field]
    ftype = field_def["type"]
    label = field_def["label"]
    current = _edit_current_value(task, field_def["key"])
    panel_width = max(52, min(term_width - 4, 92))
    input_cursor = "_" if input_active else ""
    input_label = f"[ {input_buf}{input_cursor} ]" if input_buf or input_active else "[ new value ]"

    lines = [
        f"Edit Task #{task.get('id', '?')}    [m=manual]",
        "",
        f"  ◀  {label}  ▶   {current}",
        "",
    ]

    if ftype == "text":
        lines.append("  Input:")
        lines.append(f"  {input_label}")
    else:
        lines.append("  Options:".ljust(30) + "Input:")
        if not picks:
            picks = ["-"]
        max_rows = min(16, max(6, len(picks)))
        for i in range(max_rows):
            opt = picks[i] if i < len(picks) else ""
            marker = ">" if i == col and not input_active else " "
            if i == col and not input_active:
                left = f"\033[7m{marker} {opt[:24]:<24}\033[0m"
            else:
                left = f"{marker} {opt[:24]:<24}"
            right = input_label if i == 0 else ""
            if input_active and i == 0:
                right = f"\033[7m{right}\033[0m"
            lines.append(f"  {left}  │  {right}")

    lines.extend([
        "",
        "j/k options   h/l fields   tab input   enter commit   esc cancel",
    ])

    if HAS_RICH:
        console = Console(force_terminal=True, width=panel_width)
        panel = Panel(
            "\n".join(lines),
            border_style=AMBER,
            box=box.ROUNDED,
            padding=(0, 2),
        )
        with console.capture() as cap:
            console.print(panel)
        return cap.get().split("\n")

    border_w = panel_width - 2
    out = ["  ┌" + "─" * border_w + "┐"]
    for line in lines:
        clean = line[:border_w - 2]
        out.append("  │ " + clean.ljust(border_w - 2) + " │")
    out.append("  └" + "─" * border_w + "┘")
    return out


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
        new_tags = [tag.strip() for tag in value.replace(",", " ").split() if tag.strip()]
        old_tags = task.get("tags") or []
        task_modify(
            task_id,
            tags_add=[tag for tag in new_tags if tag not in old_tags],
            tags_remove=[tag for tag in old_tags if tag not in new_tags],
        )


def _fuzzy_score(query: str, task: dict) -> int:
    """Score a task against a fuzzy query. Higher = better match. 0 = no match."""
    q = query.lower()
    haystack = " ".join(filter(None, [
        task.get("description", ""),
        task.get("project", ""),
        task.get("scope", ""),
        " ".join(task.get("tags") or []),
        " ".join(a.get("description", "") for a in (task.get("annotations") or [])),
    ])).lower()

    if not q:
        return 0
    if q in haystack:
        return 100 + (50 if q in (task.get("description", "") or "").lower() else 0)

    idx = 0
    for ch in q:
        pos = haystack.find(ch, idx)
        if pos == -1:
            return 0
        idx = pos + 1
    return max(1, 80 - (idx - len(q)))


def _run_fuzzy(query: str, tasks: list) -> list:
    if not query:
        return []
    scored = [(score, t) for t in tasks if (score := _fuzzy_score(query, t)) > 0]
    return sorted(scored, key=lambda x: -x[0])[:15]


def sort_tasks(tasks: List[Dict], sort_by: str, reverse: bool = False) -> List[Dict]:
    """Sort tasks by given field."""

    def get_sort_key(t):
        if sort_by == "project":
            return (t.get("project") or "").lower()
        elif sort_by == "scope":
            return (t.get("scope") or "").lower()
        elif sort_by == "priority":
            prio = t.get("priority", "")
            return {"H": 0, "M": 1, "L": 2, "": 3}.get(prio, 3)
        elif sort_by == "due":
            return t.get("due") or ""
        elif sort_by == "description":
            return (t.get("description") or "").lower()
        elif sort_by == "status":
            return t.get("status", "")
        else:
            return t.get("id", 0)

    return sorted(tasks, key=get_sort_key, reverse=reverse)


def render_table_plain(
    tasks: List[Dict], cursor: int, width: int, selected_ids: Optional[set] = None
) -> List[str]:
    lines = []
    header = f"{'ID':<4} {'Pri':<3} {'Due':<7} {'Proj':<8} {'Scope':<8} Description"
    lines.append(header)
    lines.append("─" * width)
    selected_ids = selected_ids or set()

    for i, t in enumerate(tasks):
        marker = ">" if i == cursor else ("x" if t.get("id") in selected_ids else " ")
        pri = t.get("priority", "")
        pri_display = {"H": "!!!", "M": "!!", "L": "~", "": "-"}.get(pri, "-")
        due_display, _ = _due_display(t)
        proj = (t.get("project", "") or "")[:8]
        scope = (t.get("scope", "") or "")[:8]
        desc = (t.get("description", "") or "")[:50]
        line = (
            f"{marker}{i + 1:<3} {pri_display:<3} {due_display:<7} {proj:<8} {scope:<8} {desc}"
        )
        lines.append(line)

    return lines


def render_tasks_table(
    tasks: list, cursor: int = 0, width: int = 80, selected_ids: Optional[set] = None
) -> List[str]:
    if not tasks:
        return ["  (no tasks)"]
    selected_ids = selected_ids or set()

    if HAS_RICH:
        w = width
        id_w = 4
        pri_w = 3
        due_w = 7
        proj_w = 10
        scope_w = 10
        desc_w = w - id_w - pri_w - proj_w - scope_w - due_w - 12

        table = Table(
            show_header=True,
            header_style=f"bold {AMBER}",
            border_style=AMBER,
            box=box.ROUNDED,
            padding=(0, 1),
            pad_edge=False,
        )

        table.add_column(
            f"[{AMBER}]ID[/{AMBER}]", style=f"{AMBER_DIM}", width=id_w, no_wrap=True
        )
        table.add_column(f"[{AMBER}]Pri[/{AMBER}]", width=pri_w, no_wrap=True)
        table.add_column(f"[{AMBER}]DUE[/{AMBER}]", style="", width=due_w, no_wrap=True)
        table.add_column(f"[{AMBER}]Project[/{AMBER}]", style=AMBER, width=proj_w)
        table.add_column(f"[{AMBER}]Scope[/{AMBER}]", style=AMBER, width=scope_w)
        table.add_column(f"[{AMBER}]Description[/{AMBER}]", min_width=desc_w)

        for i, t in enumerate(tasks):
            is_cursor = i == cursor
            pri = t.get("priority", "")
            pri_display = {"H": "!!!", "M": "!!", "L": "~", "": "-"}.get(pri, "-")

            status = t.get("status", "pending")
            if t.get("id") in selected_ids:
                prefix = f"[{AMBER}]x[/{AMBER}]"
            elif status == "completed":
                prefix = f"[{AMBER}]+[/{AMBER}]"
            elif status == "waiting":
                prefix = f"[{AMBER}]~[/{AMBER}]"
            else:
                prefix = " "

            proj = (t.get("project", "") or "")[:proj_w]
            scope = (t.get("scope", "") or "")[:scope_w]
            due_display, due_style = _due_display(t)
            desc = t.get("description", "") or ""

            if is_cursor:
                row_style = f"reverse {AMBER}"
                style_open = f"[{row_style}]"
                style_close = "[/]"
            else:
                style_open = ""
                style_close = ""

            due_cell = f"{due_display:<{due_w}}"
            if due_style and not is_cursor:
                due_cell = f"[{due_style}]{due_cell}[/]"

            table.add_row(
                f"{style_open}{i + 1:<{id_w}}{style_close}",
                f"{style_open}{pri_display:<{pri_w}}{style_close}",
                f"{style_open}{due_cell}{style_close}",
                f"{style_open}{proj:<{proj_w}}{style_close}",
                f"{style_open}{scope:<{scope_w}}{style_close}",
                f"{style_open}{prefix} {desc}{style_close}",
            )

        console = Console(force_terminal=True)
        with console.capture() as cap:
            console.print(table)
        lines = cap.get().split("\n")
        return lines
    else:
        return render_table_plain(tasks, cursor, width, selected_ids)


def render_batch_panel(selected_tasks: List[Dict]) -> str:
    lines = [
        "  [bold amber]Batch[/bold amber]",
        f"    {len(selected_tasks)} selected",
        "",
    ]
    for t in selected_tasks[:12]:
        lines.append(f"    x [{t.get('id','?')}] {t.get('description','')}")
    if len(selected_tasks) > 12:
        lines.append(f"    ... {len(selected_tasks) - 12} more")
    lines.extend([
        "",
        "    c complete selected   q back",
    ])
    return "\n".join(lines)


def _dependency_detail_lines(t: dict, rich: bool) -> List[str]:
    lines: List[str] = []
    depends = t.get("depends") or []
    if depends:
        lines.append(
            f"  [bold {AMBER}]Depends on (prerequisites)[/]"
            if rich
            else "  Depends on (prerequisites):"
        )
        for dep_uuid in depends:
            try:
                from src.tw import _run_json

                found = _run_json(f"uuid:{dep_uuid}", "export")
                if found:
                    d = found[0]
                    if rich:
                        mark = "[green]✓[/green]" if d.get("status") == "completed" else "[yellow]○[/yellow]"
                    else:
                        mark = "✓" if d.get("status") == "completed" else "○"
                    lines.append(f"    {mark} [{d.get('id','?')}] {d.get('description','')}")
            except Exception:
                lines.append(f"    ○ (uuid: {str(dep_uuid)[:8]}...)")

    this_uuid = t.get("uuid", "")
    if this_uuid:
        try:
            from src.tw import _run_json

            blocking = _run_json(f"depends.is:{this_uuid}", "export") or []
            if blocking:
                lines.append(f"  [bold {AMBER}]Blocks[/]" if rich else "  Blocks:")
                for b in blocking:
                    lines.append(f"    → [{b.get('id','?')}] {b.get('description','')}")
        except Exception:
            pass

    return lines


def render_task_detail(t) -> str:
    if not t:
        return "Select a task to view details"

    if HAS_RICH:
        lines = [
            f"[bold]Task #[/bold]{t.get('id', '?')}",
            f"  [bold]Description:[/bold] {t.get('description', '')}",
            f"  [bold]Project:[/bold]  {t.get('project', '(none)') or '(none)'}",
            f"  [bold]Priority:[/bold] {t.get('priority', '(none)')}",
            f"  [bold]Scope:[/bold]   {t.get('scope', '(none)') or '(none)'}",
            f"  [bold]Due:[/bold]     {t.get('due', '(none)') or '(none)'}",
            f"  [bold]Status:[/bold]  {t.get('status', 'pending')}",
            f"  [bold]Urgency:[/bold] {t.get('urgency', 0):.2f}",
        ]

        tags = t.get("tags", [])
        if tags:
            lines.append(f"  [bold]Tags:[/bold]    {', '.join(tags)}")

        annotations = t.get("annotations", [])
        if annotations:
            lines.append(f"  [bold {AMBER}]Notes[/]")
            for ann in annotations:
                desc = ann.get("description") or str(ann)
                entry = ann.get("entry") or ""
                date_str = ""
                if entry:
                    try:
                        dt = datetime.datetime.strptime(entry[:8], "%Y%m%d")
                        date_str = f"[{AMBER_DIM}]{dt.strftime('%m/%d')}[/{AMBER_DIM}]  "
                    except Exception:
                        pass
                lines.append(f"    {date_str}{desc}")

        lines.extend(_dependency_detail_lines(t, rich=True))

        return "\n".join(lines)
    else:
        lines = [
            f"Task #{t.get('id', '?')}",
            f"  Description: {t.get('description', '')}",
            f"  Project:  {t.get('project', '(none)') or '(none)'}",
            f"  Priority: {t.get('priority', '(none)')}",
            f"  Scope:   {t.get('scope', '(none)') or '(none)'}",
            f"  Due:     {t.get('due', '(none)') or '(none)'}",
            f"  Status:  {t.get('status', 'pending')}",
            f"  Urgency: {t.get('urgency', 0):.2f}",
        ]

        tags = t.get("tags", [])
        if tags:
            lines.append(f"  Tags:    {', '.join(tags)}")

        annotations = t.get("annotations", [])
        if annotations:
            lines.append("  Notes:")
            for ann in annotations:
                desc = ann.get("description") or str(ann)
                entry = ann.get("entry") or ""
                date_str = ""
                if entry:
                    try:
                        dt = datetime.datetime.strptime(entry[:8], "%Y%m%d")
                        date_str = f"{dt.strftime('%m/%d')}  "
                    except Exception:
                        pass
                lines.append(f"    {date_str}{desc}")

        lines.extend(_dependency_detail_lines(t, rich=False))

        return "\n".join(lines)


def render_help() -> str:
    return """
  [bold]Commands[/bold]
    (a)dd  (c)omplete  (D)elete  (v)iew  (e)dit  (m)anual  (ctrl+f)uzzy  (q)uit

  [dim]DUE column shows countdowns; detail view includes notes and dependencies.[/dim]

  [dim]press ? for full help[/dim]
"""


def render_full_help() -> str:
    return """
  [bold amber]Navigation[/bold amber]
    j/k or arrows   move up/down
    h/l or ←/→      prev/next task (in detail view)
    ←/→             pending/completed view switch
    gg              go to top
    G               go to bottom

  [bold amber]Actions[/bold amber]
    enter or v      view task detail
    c               mark complete
    dd              delete task
    a               add new task
    e               smart edit panel
    m               manual edit in $EDITOR
    / or r          search tasks
    ctrl+f          fuzzy search (description/project/tags/notes)
    f / F           filter by project / clear project filter
    x / B           select task / batch selected tasks
    s               sort menu
    ?               toggle this help
    q               quit

  [bold amber]Display[/bold amber]
    DUE column      countdown: today, tmrw, 3d, 05/12, or overdue
    Detail view     shows task annotations, prerequisites, and blocked tasks

  [bold amber]Sort options[/bold amber]
    s p             sort by project
    s s             sort by scope
    s r             sort by priority
    s d             sort by due date
    s t             sort by description
    s i             sort by id (default)
    s .             toggle reverse

  [bold amber]Add syntax[/bold amber]  (CLI `nota add` only — TUI `a` saves raw text)
    @project        assign project        "fix router @homelab"
    #tag            add tag               "#quick #errand"
    p1–p4           priority (p1=urgent)  "p2 call dentist"
    due:DATE        due date (tw NL)      "due:tomorrow  due:eow  due:friday"
    scope:X         scope                 "scope:meatspace"
    ->              prerequisite          "reply to email -> find attachment"
    ::              related-to            "task A :: task B"
"""


def render_sort_menu() -> str:
    return """
  [bold amber]Sort by:[/bold amber]
    (p)roject  (s)cope  (r)riority  (d)ue  (t)itle  (i)d
    (.)toggle reverse  (q)uit
"""


def _tui_add(text: str) -> dict:
    """Parse and add a task from the TUI prompt. Tries NLP for freeform input,
    falls back to inline syntax parser."""
    from src.tw import task_add
    from src.parse import parse_inline, _looks_freeform

    if _looks_freeform(text):
        try:
            from src.braindump import MODELS, _detect_fast_provider, _get_api_key, _priority_map, nlp_single_task
            from src.scopes import is_valid_scope
            model_alias = _detect_fast_provider()
            cfg = MODELS.get(model_alias, {})
            key_env = cfg.get("key_env")
            if key_env and _get_api_key(key_env):
                t = nlp_single_task(text)
                scope = str(t.get("scope") or "").strip()
                if not scope or not is_valid_scope(scope):
                    scope = None
                tags = t.get("tags") or []
                # Preserve the user's original text — only take metadata from NLP
                return task_add(
                    description=text,
                    project=t.get("project") or "inbox",
                    priority_p=_priority_map(str(t.get("priority", "M")).upper()),
                    due=t.get("due") or None,
                    tags=tags if isinstance(tags, list) else [],
                    scope=scope,
                )
        except Exception:
            pass  # fall through to inline parser

    p = parse_inline(text)
    return task_add(
        description=p["title"] or text,
        project=p.get("project") or "inbox",
        priority_p=f"p{p.get('priority', 3)}",
        due=p.get("due_date"),
        tags=p.get("tags") or [],
        scope=p.get("scope") or None,
    )


def run():
    from src.tw import task_list, task_get, task_done, task_add, task_delete

    global _term_resized

    view_mode = "pending"
    tasks = task_list(status=view_mode, limit=50)
    cursor = 0
    _state = _load_tui_state()
    sort_by = _state.get("sort_by", "id")
    sort_reverse = _state.get("sort_reverse", False)

    show_help = False
    show_full_help = False
    show_detail = False
    show_edit = False
    show_sort = False
    detail_task = None
    edit_task = None
    edit_field = 0
    edit_col = 0
    edit_pick = []
    edit_input = ""
    edit_input_active = False
    search_query = ""
    filter_project = ""
    fuzzy_query = ""
    fuzzy_results = []
    fuzzy_active = False
    fuzzy_cursor = 0
    selected: set = set()
    batch_mode = False
    show_logo = True
    pending_key = ""

    term_width = get_term_size().columns

    hide_cursor()

    def current_display_tasks() -> List[Dict]:
        display = tasks
        if search_query:
            q = search_query.lower()
            display = [t for t in display if q in t.get("description", "").lower()]
        if filter_project:
            display = [
                t for t in display
                if (t.get("project") or "").lower() == filter_project.lower()
            ]
        return sort_tasks(display, sort_by, sort_reverse)

    def save_sort_state() -> None:
        _save_tui_state({"sort_by": sort_by, "sort_reverse": sort_reverse})

    while True:
        if _term_resized:
            term_width = get_term_size().columns
            _term_resized = False
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()

        display_tasks = current_display_tasks()

        frame = []

        if HAS_RICH:
            console = Console(force_terminal=True)
            banner = Panel(
                "(a)dd  (c)omplete  (D)elete  (v)iew  (e)dit  (m)anual  (s)ort  (f)ilter  (x)select  (q)uit",
                border_style=AMBER,
                box=box.ROUNDED,
                padding=(0, 2),
            )
            with console.capture() as cap:
                console.print(banner)
            frame.extend(cap.get().split("\n"))
        else:
            frame.append(
                "  (a)dd  (c)omplete  (D)elete  (v)iew  (e)dit  (m)anual  (s)ort  (f)ilter  (x)select  (q)uit"
            )
            frame.append("─" * term_width)

        sort_indicator = (
            f" \033[33msorted by {sort_by}"
            + (" (reverse)" if sort_reverse else "")
            + "\033[0m"
        )
        frame.append(
            f"\033[1;33mnota\033[0m  {view_mode}{sort_indicator}  \033[33m│\033[0m press \033[1;33m?\033[0m for help"
        )
        frame.append("\033[33m" + "─" * (term_width - 1) + "\033[0m")
        frame.append("")

        if fuzzy_active:
            frame.append(f"  \033[33mfuzzy search:\033[0m {fuzzy_query}\033[1m_\033[0m")
            frame.append("")
            if not fuzzy_query:
                frame.append("  type to search description · project · tags · notes")
            elif not fuzzy_results:
                frame.append("  no matches")
            else:
                for i, (score, t) in enumerate(fuzzy_results):
                    marker = "\033[7m" if i == fuzzy_cursor else ""
                    reset = "\033[0m" if i == fuzzy_cursor else ""
                    proj = f"[{t.get('project','')}]" if t.get("project") else ""
                    due_s, _ = _due_display(t)
                    frame.append(
                        f"  {marker}  {t.get('id','?'):>3}  {t.get('description','')[:60]}"
                        f"  {proj}  {due_s}{reset}"
                    )
            frame.append("")
            frame.append("  \033[33mj/k navigate  enter jump  esc cancel\033[0m")

        elif show_sort:
            if HAS_RICH:
                sort_panel = Panel(
                    render_sort_menu(),
                    title="\033[1;33msort\033[0m",
                    border_style=AMBER,
                    box=box.ROUNDED,
                    padding=(1, 2),
                )
                console = Console(force_terminal=True)
                with console.capture() as cap:
                    console.print(sort_panel)
                frame.extend(cap.get().split("\n"))
            else:
                frame.append(render_sort_menu())

        elif show_help:
            if HAS_RICH:
                help_text = render_full_help() if show_full_help else render_help()
                help_panel = Panel(
                    help_text,
                    title="\033[1;33mhelp\033[0m",
                    border_style=AMBER,
                    box=box.ROUNDED,
                    padding=(1, 2),
                )
                console = Console(force_terminal=True)
                with console.capture() as cap:
                    console.print(help_panel)
                frame.extend(cap.get().split("\n"))
            else:
                frame.append(render_help())

        elif show_detail and detail_task:
            if HAS_RICH:
                detail = Panel(
                    render_task_detail(detail_task),
                    title=f"\033[1;33mtask #{detail_task.get('id', '?')}\033[0m",
                    border_style=AMBER,
                    padding=(1, 2),
                    box=box.ROUNDED,
                )
                console = Console(force_terminal=True)
                with console.capture() as cap:
                    console.print(detail)
                frame.extend(cap.get().split("\n"))
            else:
                frame.append(render_task_detail(detail_task))

        elif show_edit and edit_task:
            panel_options = _edit_field_options(edit_field, edit_pick)
            panel_lines = render_edit_panel(
                edit_task,
                edit_field,
                edit_col,
                panel_options,
                edit_input,
                edit_input_active,
                term_width,
            )
            frame.extend(panel_lines)

        elif batch_mode:
            selected_tasks = [t for t in tasks if t.get("id") in selected]
            if HAS_RICH:
                batch_panel = Panel(
                    render_batch_panel(selected_tasks),
                    title="\033[1;33mbatch\033[0m",
                    border_style=AMBER,
                    padding=(1, 2),
                    box=box.ROUNDED,
                )
                console = Console(force_terminal=True)
                with console.capture() as cap:
                    console.print(batch_panel)
                frame.extend(cap.get().split("\n"))
            else:
                frame.append(render_batch_panel(selected_tasks))

        else:
            if show_logo or not display_tasks:
                logo = render_logo(term_width)
                if logo:
                    frame.extend(logo)
                    frame.append("")
            if not display_tasks:
                frame.append("  (no tasks)  — press a to add")
            else:
                table_lines = render_tasks_table(display_tasks, cursor, term_width, selected)
                frame.extend(table_lines)

        frame.append("")
        status_line = f"\033[33m[\033[0m"
        if search_query:
            status_line += f" search: {search_query}  │"
        status_line += f" {len(display_tasks)} tasks"
        if selected:
            status_line += f"  │ selected: {len(selected)}"
        if filter_project:
            status_line += f"  │ project: {filter_project}  (F to clear)"
        if show_detail:
            status_line += "  │ h/l prev/next, q close"
        arrow = "\033[33m→\033[0m completed" if view_mode == "pending" else "\033[33m←\033[0m pending"
        status_line += f"  │ {arrow}"
        status_line += "\033[33m]\033[0m"
        frame.append(status_line)

        output = "\n".join(frame)
        sys.stdout.write("\033[H")
        sys.stdout.write(output)
        sys.stdout.write("\033[J")
        sys.stdout.flush()

        key = read_key()
        if show_logo:
            show_logo = False

        if show_edit and edit_task:
            field_def = EDIT_FIELDS[edit_field]
            ftype = field_def["type"]
            fkey = field_def["key"]
            active_options = _edit_field_options(edit_field, edit_pick)

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
                if active_options:
                    edit_col = (edit_col + 1) % len(active_options)
            elif key in ("k", "UP") and not edit_input_active:
                if active_options:
                    edit_col = (edit_col - 1) % len(active_options)
            elif key == "\t":
                edit_input_active = not edit_input_active
            elif key in ("\r", "\n", "ENTER"):
                val = None
                if ftype == "text":
                    val = edit_input.strip() if edit_input.strip() else None
                elif ftype == "pick":
                    if edit_input_active and edit_input.strip():
                        val = edit_input.strip()
                    elif active_options and 0 <= edit_col < len(active_options):
                        val = active_options[edit_col]
                elif ftype == "cycle":
                    if active_options:
                        val = active_options[edit_col % len(active_options)]
                elif ftype == "time":
                    if edit_input_active and edit_input.strip():
                        val = edit_input.strip()
                    elif active_options and 0 <= edit_col < len(active_options):
                        val = active_options[edit_col]

                if val is not None:
                    _apply_edit_field(edit_task, fkey, val)
                    edit_task = task_get(edit_task.get("id"))
                    tasks = task_list(status=view_mode, limit=50)

                edit_field = (edit_field + 1) % len(EDIT_FIELDS)
                edit_pick = _load_edit_picks(EDIT_FIELDS[edit_field]["key"])
                edit_col = 0
                edit_input = ""
                edit_input_active = False
            elif key in ("q", "ESC"):
                show_edit = False
                edit_task = None
            elif key == "m":
                os.system(f"task {edit_task.get('id')} edit")
                tasks = task_list(status=view_mode, limit=50)
                show_edit = False
                edit_task = None
            elif edit_input_active:
                if key in ("\x7f", "\x08"):
                    edit_input = edit_input[:-1]
                elif len(key) == 1 and ord(key) >= 32:
                    edit_input += key

            pending_key = ""
            continue

        if fuzzy_active:
            if key in ("\x06", "ESC", "q"):
                fuzzy_active = False
                fuzzy_query = ""
            elif key in ("\r", "\n", "ENTER"):
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

        if batch_mode:
            if key in ("q", "ESC"):
                batch_mode = False
            elif key == "c":
                show_cursor()
                text, cancelled = read_line(
                    f"  \033[33mcomplete {len(selected)} selected? [y/N]: \033[0m"
                )
                hide_cursor()
                if not cancelled and text and text.strip().lower() in ("y", "yes"):
                    for tid in list(selected):
                        task_done(tid)
                    selected.clear()
                    tasks = task_list(status=view_mode, limit=50)
                    display_tasks = current_display_tasks()
                    if cursor >= len(display_tasks):
                        cursor = max(0, len(display_tasks) - 1)
                    batch_mode = False
            pending_key = ""
            continue

        if key == "q":
            if show_detail or show_full_help or show_sort or show_help:
                show_detail = False
                show_full_help = False
                show_sort = False
                show_help = False
            else:
                break

        elif key == "ESC":
            show_help = False
            show_detail = False
            show_sort = False

        elif key == "?":
            if not show_help:
                show_help = True
                show_full_help = False
            elif not show_full_help:
                show_full_help = True
            else:
                show_help = False
                show_full_help = False
            show_detail = False
            show_sort = False

        elif key == "s" and not show_sort:
            show_sort = True
            show_help = False
            show_detail = False

        elif key == "s" and show_sort:
            show_sort = False

        elif show_sort:
            if key == "p":
                sort_by = "project"
                save_sort_state()
                show_sort = False
            elif key == "s":
                sort_by = "scope"
                save_sort_state()
                show_sort = False
            elif key == "r":
                sort_by = "priority"
                save_sort_state()
                show_sort = False
            elif key == "d":
                sort_by = "due"
                save_sort_state()
                show_sort = False
            elif key == "t":
                sort_by = "description"
                save_sort_state()
                show_sort = False
            elif key == "i":
                sort_by = "id"
                save_sort_state()
                show_sort = False
            elif key == ".":
                sort_reverse = not sort_reverse
                save_sort_state()
            else:
                show_sort = False

        elif key == "\x06":
            fuzzy_active = True
            fuzzy_query = ""
            fuzzy_results = []
            fuzzy_cursor = 0
            pending_key = ""

        elif key == "RIGHT" and not show_detail and not show_edit:
            view_mode = "completed"
            tasks = task_list(status=view_mode, limit=50)
            cursor = 0
            selected = set()
            pending_key = ""

        elif key == "LEFT" and not show_detail and not show_edit:
            view_mode = "pending"
            tasks = task_list(status=view_mode, limit=50)
            cursor = 0
            selected = set()
            pending_key = ""

        elif key in ("j", "DOWN", "k", "UP"):
            if key in ("j", "DOWN"):
                if display_tasks and cursor < len(display_tasks) - 1:
                    cursor += 1
            else:
                if cursor > 0:
                    cursor -= 1
            show_detail = False
            pending_key = ""

        elif key == "g":
            cursor = 0
            show_detail = False

        elif key == "G":
            if display_tasks:
                cursor = len(display_tasks) - 1
            show_detail = False
            pending_key = ""

        elif pending_key == "d" and key == "d":
            if display_tasks and cursor < len(display_tasks):
                t = display_tasks[cursor]
                task_delete(t.get("id"))
                selected.discard(t.get("id"))
                tasks = task_list(status=view_mode, limit=50)
                display_tasks = current_display_tasks()
                if cursor >= len(display_tasks):
                    cursor = max(0, len(display_tasks) - 1)
            pending_key = ""

        elif key == "c":
            if display_tasks and cursor < len(display_tasks):
                t = display_tasks[cursor]
                task_done(t.get("id"))
                selected.discard(t.get("id"))
                tasks = task_list(status=view_mode, limit=50)
                display_tasks = current_display_tasks()
                if cursor >= len(display_tasks):
                    cursor = max(0, len(display_tasks) - 1)
            pending_key = ""

        elif key == "d":
            pending_key = "d"

        elif key == "D":
            if display_tasks and cursor < len(display_tasks):
                t = display_tasks[cursor]
                task_delete(t.get("id"))
                selected.discard(t.get("id"))
                tasks = task_list(status=view_mode, limit=50)
                display_tasks = current_display_tasks()
                if cursor >= len(display_tasks):
                    cursor = max(0, len(display_tasks) - 1)
            pending_key = ""

        elif key == "x":
            if display_tasks and cursor < len(display_tasks):
                tid = display_tasks[cursor].get("id")
                if tid in selected:
                    selected.discard(tid)
                else:
                    selected.add(tid)
                if cursor < len(display_tasks) - 1:
                    cursor += 1
            pending_key = ""

        elif key == "B":
            if selected:
                batch_mode = True
                show_detail = False
                show_help = False
                show_sort = False
            pending_key = ""

        elif key in ("\r", "\n", "ENTER"):
            if display_tasks and cursor < len(display_tasks):
                t = display_tasks[cursor]
                detail_task = task_get(t.get("id"))
                show_detail = True
                show_help = False
                show_sort = False
            pending_key = ""

        elif key in ("h", "LEFT") and show_detail:
            if cursor > 0:
                cursor -= 1
                t = display_tasks[cursor]
                detail_task = task_get(t.get("id"))
            pending_key = ""

        elif key in ("l", "RIGHT") and show_detail:
            if cursor < len(display_tasks) - 1:
                cursor += 1
                t = display_tasks[cursor]
                detail_task = task_get(t.get("id"))
            pending_key = ""

        elif key == "v":
            if display_tasks and cursor < len(display_tasks):
                t = display_tasks[cursor]
                detail_task = task_get(t.get("id"))
                show_detail = True
                show_help = False
                show_sort = False
            pending_key = ""

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

        elif key == "/":
            show_cursor()
            text, cancelled = read_line("  \033[33msearch: \033[0m")
            hide_cursor()
            if not cancelled and text is not None:
                search_query = text.strip()
            cursor = 0
            show_detail = False
            pending_key = ""

        elif key == "f":
            show_cursor()
            text, cancelled = read_line("  \033[33mfilter project (blank=all): \033[0m")
            hide_cursor()
            if not cancelled and text is not None:
                filter_project = text.strip()
            cursor = 0
            show_detail = False
            pending_key = ""

        elif key == "F":
            filter_project = ""
            cursor = 0
            show_detail = False
            pending_key = ""

        elif key == "a":
            show_cursor()
            text, cancelled = read_line("  \033[33madd task: \033[0m")
            hide_cursor()
            if not cancelled and text and text.strip():
                _tui_add(text.strip())
                tasks = task_list(status=view_mode, limit=50)
                display_tasks = current_display_tasks()
            pending_key = ""

        elif key == "r":
            search_query = ""
            pending_key = ""

        else:
            pending_key = ""

    show_cursor()
    clear_screen()


if __name__ == "__main__":
    run()
