# maps · cassette.help · MIT
"""
nota bene - TUI entrypoint.

Launch with: nota bene
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, ListView, ListItem, Input
from textual.containers import Container, Horizontal, Vertical
from textual import on


class TaskListItem(ListItem):
    def __init__(self, task_id, description, priority="", project="", due="", scope=""):
        super().__init__()
        self.task_id = task_id
        self.description = description
        self.priority = priority
        self.project = project
        self.due = due
        self.scope = scope

    def compose(self) -> ComposeResult:
        priority_icon = {"H": "🔴", "M": "🟡", "L": "🟢", "": "⚪"}.get(
            self.priority, "⚪"
        )
        yield Static(f"[{self.task_id}] {priority_icon} {self.description[:50]}")


class NotaBeneApp(App):
    """nota TUI - Rich terminal interface."""

    CSS = """
    Screen {
        background: $surface;
    }
    
    #task-list {
        height: 60%;
        border: solid $primary;
        padding: 1;
    }
    
    #task-detail {
        height: 40%;
        border: solid $secondary;
        padding: 1;
    }
    
    #input-area {
        height: 3;
        background: $surface-lighten-1;
        padding: 1;
    }
    
    #input {
        width: 100%;
    }
    
    Static {
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("a", "add_task", "Add task"),
        ("d", "done_task", "Done"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("/", "focus_search", "Search"),
        ("p", "filter_project", "Filter project"),
        ("s", "filter_scope", "Filter scope"),
    ]

    def __init__(self):
        super().__init__()
        self.tasks = []
        self.selected_task = None
        self.filter_project = None
        self.filter_scope = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with Container(id="task-list"):
                yield ListView(id="task-list-view")
            with Container(id="task-detail"):
                yield Static("Select a task to view details", id="detail-text")
        with Container(id="input-area"):
            yield Input(placeholder="Type task or press a to add...", id="input")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_tasks()

    def refresh_tasks(self):
        """Load tasks from taskwarrior."""
        from src.tw import task_list
        from src.parse import parse_inline

        # TODO: Apply filters
        tasks = task_list(status="pending", limit=50)

        list_view = self.query_one("#task-list-view", ListView)
        list_view.clear()

        for t in tasks:
            item = TaskListItem(
                task_id=t.get("id"),
                description=t.get("description", ""),
                priority=t.get("priority", ""),
                project=t.get("project", ""),
                due=t.get("due", "")[:10] if t.get("due") else "",
                scope=t.get("scope", ""),
            )
            list_view.append(item)

        self.tasks = tasks

    @on(ListView.Selected)
    def on_task_selected(self, event: ListView.Selected):
        if event.item:
            self.selected_task = event.item.task_id
            self.show_task_detail(event.item.task_id)

    def show_task_detail(self, task_id):
        from src.tw import task_get, fmt_detail

        t = task_get(task_id)
        if t:
            detail = fmt_detail(t)
            self.query_one("#detail-text", Static).update(detail)

    def action_add_task(self):
        """Focus input for adding task."""
        input_widget = self.query_one("#input", Input)
        input_widget.focus()

    def action_done_task(self):
        """Mark selected task as done."""
        from src.tw import task_done

        list_view = self.query_one("#task-list-view", ListView)
        if list_view.index is not None and list_view.index < len(self.tasks):
            task = self.tasks[list_view.index]
            task_id = task.get("id")
            if task_id:
                task_done(task_id)
                self.refresh_tasks()

    def action_quit(self):
        self.exit()

    def key_j(self):
        self.query_one("#task-list-view", ListView).cursor_down()

    def key_k(self):
        self.query_one("#task-list-view", ListView).cursor_up()


def run():
    app = NotaBeneApp()
    app.run()


if __name__ == "__main__":
    run()
