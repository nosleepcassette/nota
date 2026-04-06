# maps · cassette.help · MIT
"""
nota bene - TUI entrypoint.

Launch with: nota bene
Style: vim keybindings, table-based, no emojis, amber theme.
"""

import os
import sys
import select
import termios
import tty
from io import StringIO
from typing import Optional, List, Dict

try:
    from rich import box
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


AMBER = "rgb(255,176,0)"
AMBER_BRIGHT = "rgb(255,200,50)"
AMBER_DIM = "rgb(150,100,0)"
CURSOR_AMBER = "rgb(255,140,0)"


def strip_markup(text: str) -> str:
    import re

    return (
        re.sub(r"\[/?[^\]]+\]", "", str(text)).replace(r"\[", "[").replace(r"\]", "]")
    )


def read_key() -> str:
    if not sys.stdin.isatty():
        return input().strip()[:1] if input().strip() else ""

    def decode(seq: str) -> str:
        if seq == "":
            return ""
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


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def get_term_size():
    try:
        return os.get_terminal_size()
    except:
        return os.terminal_size((80, 24))


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


def render_table_plain(tasks: List[Dict], cursor: int, width: int) -> List[str]:
    lines = []
    header = f"{'ID':<4} {'Pri':<3} {'Proj':<8} {'Scope':<8} {'Due':<8} Description"
    lines.append(header)
    lines.append("─" * width)

    for i, t in enumerate(tasks):
        marker = ">" if i == cursor else " "
        pri = t.get("priority", "")
        pri_display = {"H": "!!!", "M": "!!", "L": "~", "": "-"}.get(pri, "-")
        proj = (t.get("project", "") or "")[:8]
        scope = (t.get("scope", "") or "")[:8]
        due = t.get("due", "")[:8] if t.get("due") else "-"
        desc = (t.get("description", "") or "")[:50]
        line = (
            f"{marker}{i + 1:<3} {pri_display:<3} {proj:<8} {scope:<8} {due:<8} {desc}"
        )
        lines.append(line)

    return lines


def render_tasks_table(tasks: list, cursor: int = 0, width: int = 80) -> List[str]:
    if not tasks:
        return ["  (no tasks)"]

    if HAS_RICH:
        w = width
        id_w = 4
        pri_w = 3
        proj_w = 10
        scope_w = 10
        due_w = 10
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
        table.add_column(f"[{AMBER}]Project[/{AMBER}]", style=AMBER, width=proj_w)
        table.add_column(f"[{AMBER}]Scope[/{AMBER}]", style=AMBER, width=scope_w)
        table.add_column(
            f"[{AMBER}]Due[/{AMBER}]", style=AMBER, width=due_w, no_wrap=True
        )
        table.add_column(f"[{AMBER}]Description[/{AMBER}]", min_width=desc_w)

        for i, t in enumerate(tasks):
            is_cursor = i == cursor
            pri = t.get("priority", "")
            pri_display = {"H": "!!!", "M": "!!", "L": "~", "": "-"}.get(pri, "-")

            status = t.get("status", "pending")
            if status == "completed":
                prefix = f"[{AMBER}]+[/{AMBER}]"
            elif status == "waiting":
                prefix = f"[{AMBER}]~[/{AMBER}]"
            else:
                prefix = " "

            proj = (t.get("project", "") or "")[:proj_w]
            scope = (t.get("scope", "") or "")[:scope_w]
            due = t.get("due", "")[:10] if t.get("due") else "-"
            desc = t.get("description", "") or ""

            if is_cursor:
                row_style = f"reverse {AMBER}"
                style_open = f"[{row_style}]"
                style_close = "[/]"
            else:
                style_open = ""
                style_close = ""

            table.add_row(
                f"{style_open}{i + 1:<{id_w}}{style_close}",
                f"{style_open}{pri_display:<{pri_w}}{style_close}",
                f"{style_open}{proj:<{proj_w}}{style_close}",
                f"{style_open}{scope:<{scope_w}}{style_close}",
                f"{style_open}{due:<{due_w}}{style_close}",
                f"{style_open}{prefix} {desc}{style_close}",
            )

        console = Console(force_terminal=True)
        with console.capture() as cap:
            console.print(table)
        lines = cap.get().split("\n")
        return lines
    else:
        return render_table_plain(tasks, cursor, width)


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
            lines.append("  [bold]Notes:[/bold]")
            for ann in annotations:
                lines.append(f"    - {ann.get('description', '')}")

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
                lines.append(f"    - {ann.get('description', '')}")

        return "\n".join(lines)


def render_help() -> str:
    return """
  [bold]Commands[/bold]
    (a)dd  (d)one  (D)elete  (v)iew  (e)dit  (s)ort  (q)uit

  [dim]press ? for full help[/dim]
"""


def render_full_help() -> str:
    return """
  [bold amber]Navigation[/bold amber]
    j/k or arrows   move up/down
    h/l             prev/next task (in detail view)
    gg              go to top
    G               go to bottom

  [bold amber]Actions[/bold amber]
    enter or v      view task detail
    d               mark done
    dd              delete task
    a               add new task
    e               edit task (opens in editor)
    / or r          search tasks
    s               sort menu
    ?               toggle this help
    q               quit

  [bold amber]Sort options[/bold amber]
    s p             sort by project
    s s             sort by scope
    s r             sort by priority
    s d             sort by due date
    s t             sort by description
    s i             sort by id (default)
    s .             toggle reverse
"""


def render_sort_menu() -> str:
    return """
  [bold amber]Sort by:[/bold amber]
    (p)roject  (s)cope  (r)riority  (d)ue  (t)itle  (i)d
    (.)toggle reverse  (q)uit
"""


def run():
    from src.tw import task_list, task_get, task_done, task_add, task_delete

    tasks = task_list(status="pending", limit=50)
    cursor = 0
    sort_by = "id"
    sort_reverse = False

    show_help = False
    show_full_help = False
    show_detail = False
    show_sort = False
    detail_task = None
    search_query = ""
    pending_key = ""

    term_width = get_term_size().columns
    first_render = True

    hide_cursor()

    while True:
        display_tasks = tasks
        if search_query:
            q = search_query.lower()
            display_tasks = [t for t in tasks if q in t.get("description", "").lower()]

        display_tasks = sort_tasks(display_tasks, sort_by, sort_reverse)

        if first_render:
            clear_screen()
            first_render = False

        frame = []

        if HAS_RICH:
            console = Console(force_terminal=True)
            banner = Panel(
                "(a)dd  (d)one  (D)elete  (v)iew  (e)dit  (s)ort  (q)uit  (g)o top/bot",
                border_style=AMBER,
                box=box.ROUNDED,
                padding=(0, 2),
            )
            with console.capture() as cap:
                console.print(banner)
            frame.extend(cap.get().split("\n"))
        else:
            frame.append(
                "  (a)dd  (d)one  (D)elete  (v)iew  (e)dit  (s)ort  (q)uit  (g)o top/bot"
            )
            frame.append("─" * term_width)

        sort_indicator = (
            f" \033[90msorted by {sort_by}"
            + (" (reverse)" if sort_reverse else "")
            + "\033[0m"
        )
        frame.append(
            f"\033[1;33mnota\033[0m{sort_indicator}  \033[90m│\033[0m press \033[1;33m?\033[0m for help"
        )
        frame.append("\033[90m" + "─" * (term_width - 1) + "\033[0m")
        frame.append("")

        if show_sort:
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

        else:
            table_lines = render_tasks_table(display_tasks, cursor, term_width)
            frame.extend(table_lines)

        frame.append("")
        status_line = f"\033[90m[\033[0m"
        if search_query:
            status_line += f" search: {search_query}  │"
        status_line += f" {len(display_tasks)} tasks"
        if show_detail:
            status_line += "  │ h/l prev/next, q close"
        status_line += "\033[90m]\033[0m"
        frame.append(status_line)

        sys.stdout.write("\033[2J\033[H")
        output = "\n".join(frame)
        sys.stdout.write(output)
        if not frame or frame[-1] != "\n":
            sys.stdout.write("\n")
        sys.stdout.flush()

        key = read_key()

        if key == "q":
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
                show_sort = False
            elif key == "s":
                sort_by = "scope"
                show_sort = False
            elif key == "r":
                sort_by = "priority"
                show_sort = False
            elif key == "d":
                sort_by = "due"
                show_sort = False
            elif key == "t":
                sort_by = "description"
                show_sort = False
            elif key == "i":
                sort_by = "id"
                show_sort = False
            elif key == ".":
                sort_reverse = not sort_reverse
            else:
                show_sort = False

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
                tasks = task_list(status="pending", limit=50)
                display_tasks = tasks
                if search_query:
                    q = search_query.lower()
                    display_tasks = [
                        t for t in tasks if q in t.get("description", "").lower()
                    ]
                if cursor >= len(display_tasks):
                    cursor = max(0, len(display_tasks) - 1)
            pending_key = ""

        elif key == "d":
            pending_key = "d"

        elif key == "D":
            if display_tasks and cursor < len(display_tasks):
                t = display_tasks[cursor]
                task_delete(t.get("id"))
                tasks = task_list(status="pending", limit=50)
                display_tasks = tasks
                if search_query:
                    q = search_query.lower()
                    display_tasks = [
                        t for t in tasks if q in t.get("description", "").lower()
                    ]
                if cursor >= len(display_tasks):
                    cursor = max(0, len(display_tasks) - 1)
            pending_key = ""

        elif key in ("\n", "ENTER"):
            if display_tasks and cursor < len(display_tasks):
                t = display_tasks[cursor]
                detail_task = task_get(t.get("id"))
                show_detail = True
                show_help = False
                show_sort = False
            pending_key = ""

        elif key == "h" and show_detail:
            if cursor > 0:
                cursor -= 1
                t = display_tasks[cursor]
                detail_task = task_get(t.get("id"))
            pending_key = ""

        elif key == "l" and show_detail:
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
                os.system(f"task {t.get('id')} edit")
                tasks = task_list(status="pending", limit=50)
                display_tasks = tasks
                if search_query:
                    q = search_query.lower()
                    display_tasks = [
                        t for t in tasks if q in t.get("description", "").lower()
                    ]
            pending_key = ""

        elif key == "/":
            show_cursor()
            sys.stdout.write("  \033[90msearch: \033[0m")
            sys.stdout.flush()
            search_query = input().strip()
            hide_cursor()
            cursor = 0
            show_detail = False
            pending_key = ""

        elif key == "a":
            show_cursor()
            sys.stdout.write("  \033[90madd task: \033[0m")
            sys.stdout.flush()
            new_task = input().strip()
            hide_cursor()
            if new_task:
                task_add(description=new_task)
                tasks = task_list(status="pending", limit=50)
                display_tasks = tasks
                if search_query:
                    q = search_query.lower()
                    display_tasks = [
                        t for t in tasks if q in t.get("description", "").lower()
                    ]
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
