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
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text

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
    """Read a keypress with escape sequence support."""
    if not sys.stdin.isatty():
        return input().strip()[:1] if input().strip() else ""

    def decode(seq: str) -> str:
        if seq.startswith("[A") or seq.startswith("OA"):
            return "UP"
        if seq.startswith("[B") or seq.startswith("OB"):
            return "DOWN"
        if seq.startswith("[C") or seq.startswith("OC"):
            return "RIGHT"
        if seq.startswith("[D") or seq.startswith("OD"):
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


def clear_screen():
    """Clear screen without flickering - use direct ANSI."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def erase_lines(n: int):
    """Erase n lines upwards (for cursor movement)."""
    for _ in range(n):
        sys.stdout.write("\033[A\033[2K")
    sys.stdout.flush()


def get_term_size():
    """Get terminal size."""
    try:
        return os.get_terminal_size()
    except:
        return os.terminal_size((80, 24))


def render_tasks_table(tasks: list, cursor: int = 0, width: int = 80) -> str:
    """Render tasks in clean table format with amber theme."""
    if not tasks:
        return "  (no tasks)"

    if HAS_RICH:
        console = Console(width=width, highlight=False, force_terminal=True)

        from rich.box import Box

        table = Table(
            show_header=True,
            header_style=f"bold {AMBER}",
            border_style=AMBER_DIM,
            box=Box(
                HORIZONTALS="─",
                VERTICALS="│",
                INTERSECTIONS="┼",
                TOP_INTERSECTIONS="┬",
                BOTTOM_INTERSECTIONS="┴",
                TOP_LEFT="┌",
                TOP_RIGHT="┐",
                BOTTOM_LEFT="└",
                BOTTOM_RIGHT="┘",
            ),
            padding=(0, 1),
            pad_edge=False,
        )

        w = min(width, 80)
        id_w = 4
        pri_w = 3
        proj_w = 8
        scope_w = 8
        due_w = 8
        desc_w = w - id_w - pri_w - proj_w - scope_w - due_w - 10

        table.add_column(
            f"[{AMBER}]ID[/{AMBER}]", style=f"{AMBER_DIM}", width=id_w, no_wrap=True
        )
        table.add_column(f"[{AMBER}]Pri[/{AMBER}]", width=pri_w, no_wrap=True)
        table.add_column(f"[{AMBER}]Proj[/{AMBER}]", style=AMBER, width=proj_w)
        table.add_column(f"[{AMBER}]Scope[/{AMBER}]", style=AMBER, width=scope_w)
        table.add_column(
            f"[{AMBER}]Due[/{AMBER}]", style=AMBER, width=due_w, no_wrap=True
        )
        table.add_column(
            f"[{AMBER}]Description[/{AMBER}]", min_width=desc_w, max_width=desc_w
        )

        for i, t in enumerate(tasks):
            is_cursor = i == cursor

            pri = t.get("priority", "")
            pri_display = {"H": "!!!", "M": "!!", "L": "~", "": "-"}.get(pri, "-")

            status = t.get("status", "pending")
            if status == "completed":
                prefix = f"[{AMBER}]+[/{AMBER}]"
                desc_style = f"{AMBER_DIM}"
            elif status == "waiting":
                prefix = f"[{AMBER}]~[/{AMBER}]"
                desc_style = AMBER
            else:
                prefix = " "
                desc_style = "white" if not is_cursor else f"bold {AMBER}"

            proj = (t.get("project", "") or "")[:proj_w]
            scope = (t.get("scope", "") or "")[:scope_w]
            due = t.get("due", "")[:8] if t.get("due") else "-"
            desc = (t.get("description", "") or "")[:desc_w]

            row_style = f"on black {CURSOR_AMBER}" if is_cursor else "on black"

            table.add_row(
                f"[{row_style}]{i + 1:<{id_w}}[/{row_style}]",
                f"[{row_style}]{pri_display:<{pri_w}}[/{row_style}]",
                f"[{row_style}]{proj:<{proj_w}.{proj_w}}[/{row_style}]",
                f"[{row_style}]{scope:<{scope_w}.{scope_w}}[/{row_style}]",
                f"[{row_style}]{due:<{due_w}}[/{row_style}]",
                f"[{row_style}]{prefix} {desc:<{desc_w - 2}}[/{row_style}]",
            )

        console.print(table)
        return ""
    else:
        header = f"{'ID':<4} {'Pri':<3} {'Proj':<8} {'Scope':<8} {'Due':<8} Description"
        print(header)
        print("─" * width)

        for i, t in enumerate(tasks):
            marker = ">" if i == cursor else " "
            pri = t.get("priority", "")
            pri_display = {"H": "!!!", "M": "!!", "L": "~", "": "-"}.get(pri, "-")
            proj = (t.get("project", "") or "")[:8]
            scope = (t.get("scope", "") or "")[:8]
            due = t.get("due", "")[:8] if t.get("due") else "-"
            desc = (t.get("description", "") or "")[:50]
            print(
                f"{marker}{i + 1:<3} {pri_display:<3} {proj:<8} {scope:<8} {due:<8} {desc}"
            )

        return ""


def render_task_detail(t) -> str:
    """Render single task detail in clean panel."""
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
    """Render help panel."""
    return """
  [bold amber]Keys[/bold amber]
    j/k or arrows   move up/down
    h/l             prev/next task detail
    enter           view selected task
    d               mark done
    a               add task
    /               search
    g               go to top
    G               go to bottom
    q               quit
    ?               toggle help
"""


def run():
    """Run the TUI."""
    from src.tw import task_list, task_get, task_done, task_add

    tasks = task_list(status="pending", limit=50)
    cursor = 0

    show_help = False
    show_detail = False
    detail_task = None
    search_query = ""

    term_width = get_term_size().columns

    while True:
        display_tasks = tasks
        if search_query:
            q = search_query.lower()
            display_tasks = [t for t in tasks if q in t.get("description", "").lower()]

        clear_screen()

        print(
            f"\033[1;33mnota\033[0m - taskwarrior  \033[90m│\033[0m press \033[1;33m?\033[0m for help"
        )
        print("\033[90m" + "─" * (term_width - 1) + "\033[0m")
        print()

        if show_help:
            if HAS_RICH:
                help_panel = Panel(
                    render_help(),
                    title="\033[1;33mhelp\033[0m",
                    border_style=AMBER,
                    box=Box(
                        HORIZONTALS="─",
                        VERTICALS="│",
                        INTERSECTIONS="├",
                        TOP_INTERSECTIONS="┬",
                        BOTTOM_INTERSECTIONS="┴",
                        TOP_LEFT="┌",
                        TOP_RIGHT="┐",
                        BOTTOM_LEFT="└",
                        BOTTOM_RIGHT="┘",
                    ),
                )
                print(help_panel)
            else:
                print(render_help())

        elif show_detail and detail_task:
            if HAS_RICH:
                detail = Panel(
                    render_task_detail(detail_task),
                    title=f"\033[1;33mtask #{detail_task.get('id', '?')}\033[0m",
                    border_style=AMBER,
                    padding=(1, 2),
                    box=Box(
                        HORIZONTALS="─",
                        VERTICALS="│",
                        INTERSECTIONS="├",
                        TOP_INTERSECTIONS="┬",
                        BOTTOM_INTERSECTIONS="┴",
                        TOP_LEFT="┌",
                        TOP_RIGHT="┐",
                        BOTTOM_LEFT="└",
                        BOTTOM_RIGHT="┘",
                    ),
                )
                print(detail)
            else:
                print(render_task_detail(detail_task))

        else:
            render_tasks_table(display_tasks, cursor, term_width)

        print()
        status_line = f"\033[90m[\033[0m"
        if search_query:
            status_line += f" search: {search_query}  │"
        status_line += f" {len(display_tasks)} tasks"
        if show_detail:
            status_line += "  │ press h/l for prev/next, q to quit"
        status_line += "\033[90m]\033[0m"
        print(status_line)

        key = read_key()

        if key == "q":
            break

        elif key == "ESC":
            show_help = False
            show_detail = False

        elif key == "?":
            show_help = not show_help
            show_detail = False

        elif key in ("j", "DOWN", "k", "UP"):
            if key in ("j", "DOWN"):
                if display_tasks and cursor < len(display_tasks) - 1:
                    cursor += 1
            else:
                if cursor > 0:
                    cursor -= 1
            show_detail = False

        elif key == "g":
            cursor = 0
            show_detail = False

        elif key == "G":
            if display_tasks:
                cursor = len(display_tasks) - 1
            show_detail = False

        elif key in ("\n", "ENTER"):
            if display_tasks and cursor < len(display_tasks):
                t = display_tasks[cursor]
                detail_task = task_get(t.get("id"))
                show_detail = True
                show_help = False

        elif key == "h" and show_detail:
            if cursor > 0:
                cursor -= 1
                t = display_tasks[cursor]
                detail_task = task_get(t.get("id"))

        elif key == "l" and show_detail:
            if cursor < len(display_tasks) - 1:
                cursor += 1
                t = display_tasks[cursor]
                detail_task = task_get(t.get("id"))

        elif key == "d":
            if display_tasks and cursor < len(display_tasks):
                t = display_tasks[cursor]
                task_done(t.get("id"))
                tasks = task_list(status="pending", limit=50)
                display_tasks = tasks
                if search_query:
                    q = search_query.lower()
                    display_tasks = [
                        t for t in tasks if q in t.get("description", "").lower()
                    ]
                if cursor >= len(display_tasks):
                    cursor = max(0, len(display_tasks) - 1)

        elif key == "/":
            sys.stdout.write("  \033[90msearch: \033[0m")
            sys.stdout.flush()
            search_query = input().strip()
            cursor = 0
            show_detail = False

        elif key == "a":
            sys.stdout.write("  \033[90madd task: \033[0m")
            sys.stdout.flush()
            new_task = input().strip()
            if new_task:
                task_add(description=new_task)
                tasks = task_list(status="pending", limit=50)
                display_tasks = tasks
                if search_query:
                    q = search_query.lower()
                    display_tasks = [
                        t for t in tasks if q in t.get("description", "").lower()
                    ]

    clear_screen()


if __name__ == "__main__":
    run()
