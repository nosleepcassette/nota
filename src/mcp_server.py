# maps · cassette.help · MIT
"""
nota MCP server — exposes nota/taskwarrior as MCP tools.

Start with: nota mcp
Add to ~/.claude.json mcpServers:
  "nota": {
    "command": "/Users/maps/dev/nota/bin/nota",
    "args": ["mcp"]
  }

Available tools:
  nota_add          — add a task (full inline syntax supported)
  nota_braindump    — dump freeform text → tasks (Phase 1: passthrough to nota_add for now)
  nota_list         — list pending tasks
  nota_next         — most urgent actionable tasks
  nota_blocked      — blocked tasks
  nota_show         — full task detail
  nota_done         — mark task complete
  nota_depend       — set dependency between tasks
  nota_annotate     — add note to task
  nota_projects     — project summary
  nota_did          — mark a habit done for today (once per day, yes/no habits)
  nota_log          — log a countable habit instance (multiple per day, e.g. cigarettes)
"""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from src.parse import parse_inline
from src.tw import (
    task_add,
    task_get,
    task_list,
    task_next,
    task_blocked,
    task_done,
    task_depend,
    task_annotate,
    task_projects,
    task_modify,
    fmt_detail,
    _run,
)
from src.harsh import log_habit, log_habit_count, count_today
from src.query import build_filter

server = Server("nota")


@server.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="nota_add",
            description=(
                "Add one or more tasks. Supports inline syntax: "
                "title p1-p4 @project #tag scope:X due:DATE -> prerequisite :: related. "
                "Use -> to mean 'cannot complete until prerequisite is done'. "
                "Use :: to mark related tasks."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title with optional inline syntax",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional notes (added as annotation)",
                    },
                },
                "required": ["title"],
            },
        ),
        types.Tool(
            name="nota_braindump",
            description=(
                "Accept a freeform brain dump of tasks and add them all. "
                "For now, treats the whole text as a single task via inline syntax. "
                "Full LLM parsing is Phase 1 (braindump.py). "
                "For multi-task dumps, call nota_add multiple times."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Freeform text to parse into tasks",
                    },
                },
                "required": ["text"],
            },
        ),
        types.Tool(
            name="nota_list",
            description="List pending tasks, optionally filtered. Returns list of task objects.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "scope": {
                        "type": "string",
                        "enum": [
                            "meatspace",
                            "digital",
                            "server",
                            "opencassette",
                            "appointment",
                            "recurring",
                            "waiting",
                            "creative",
                            "admin",
                            "errand",
                        ],
                    },
                    "priority": {"type": "integer", "enum": [1, 2, 3, 4]},
                },
            },
        ),
        types.Tool(
            name="nota_next",
            description="Return the most urgent actionable (unblocked) tasks, sorted by urgency.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                },
            },
        ),
        types.Tool(
            name="nota_blocked",
            description="Return all tasks that are blocked by unfinished prerequisites.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="nota_show",
            description="Get full detail for one task including prerequisites, annotations, tags.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Task ID"},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="nota_done",
            description="Mark a task as complete.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="nota_depend",
            description="Set a dependency: task ID cannot be completed until task prerequisite_id is done.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "The blocked task"},
                    "prerequisite_id": {
                        "type": "integer",
                        "description": "Must be completed first",
                    },
                },
                "required": ["id", "prerequisite_id"],
            },
        ),
        types.Tool(
            name="nota_annotate",
            description="Add a timestamped note to a task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "note": {"type": "string"},
                },
                "required": ["id", "note"],
            },
        ),
        types.Tool(
            name="nota_projects",
            description="List all projects with pending task counts.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="nota_did",
            description=(
                "Mark a habit as done for today (once per day). "
                "Use for yes/no habits: 'meditated', 'took meds', 'exercised'. "
                "Returns ok=false if already logged today."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "habit": {
                        "type": "string",
                        "description": "Habit name, must match entry in ~/.config/harsh/habits",
                    },
                    "comment": {"type": "string", "description": "Optional note"},
                },
                "required": ["habit"],
            },
        ),
        types.Tool(
            name="nota_log",
            description=(
                "Log a countable habit instance — can be called multiple times per day. "
                "Use for things you want to count: 'smoked cigarette', 'coffee', 'drink'. "
                "Returns total count logged today."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "habit": {"type": "string", "description": "Habit name"},
                    "comment": {
                        "type": "string",
                        "description": "Optional note for this instance",
                    },
                },
                "required": ["habit"],
            },
        ),
        types.Tool(
            name="nota_modify",
            description=(
                "Modify an existing task. "
                "Can change title, project, priority, due date, scope, add/remove tags, or add body/annotation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Task ID to modify"},
                    "title": {"type": "string", "description": "New title"},
                    "project": {"type": "string", "description": "New project"},
                    "priority": {
                        "type": "integer",
                        "enum": [1, 2, 3, 4],
                        "description": "Priority (1=urgent, 4=someday)",
                    },
                    "due": {
                        "type": "string",
                        "description": "Due date (NL supported, e.g. 'friday', 'tomorrow')",
                    },
                    "scope": {
                        "type": "string",
                        "description": "Scope (meatspace, digital, server, etc.)",
                    },
                    "tags_add": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to add",
                    },
                    "tags_remove": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to remove",
                    },
                    "body": {"type": "string", "description": "Add annotation/note"},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="nota_find",
            description=(
                "Advanced search/filter tasks. "
                "Supports project, scope, priority filters plus custom filters: "
                "overdue, due-this-week, unblocked, has-annotation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "scope": {"type": "string"},
                    "priority": {"type": "integer", "enum": [1, 2, 3, 4]},
                    "status": {"type": "string", "default": "pending"},
                    "overdue": {"type": "boolean"},
                    "due_this_week": {"type": "boolean"},
                    "has_annotation": {"type": "boolean"},
                    "unblocked": {"type": "boolean"},
                    "expression": {
                        "type": "string",
                        "description": "Raw taskwarrior expression",
                    },
                    "limit": {"type": "integer", "default": 50},
                },
            },
        ),
        types.Tool(
            name="nota_scopes",
            description="List all available scopes (default + user-defined).",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    def text(content) -> list:
        return [
            types.TextContent(
                type="text", text=json.dumps(content, indent=2, default=str)
            )
        ]

    if name == "nota_add":
        title = arguments["title"]
        body = arguments.get("body", "")
        parsed = parse_inline(title)
        pri_p = f"p{parsed['priority']}"

        task = task_add(
            description=parsed["title"],
            project=parsed["project"] if parsed["project"] != "inbox" else None,
            priority_p=pri_p,
            due=parsed["due_date"],
            tags=parsed["tags"],
            scope=parsed["scope"] or None,
            body=body or None,
        )
        main_id = task.get("id")
        dep_ids = []

        for sub_title in parsed["subtasks"]:
            sub_p = parse_inline(sub_title)
            sub_task = task_add(
                description=sub_p["title"],
                project=sub_p["project"]
                if sub_p["project"] != "inbox"
                else (parsed["project"] if parsed["project"] != "inbox" else None),
                priority_p=f"p{sub_p['priority']}",
                due=sub_p["due_date"],
                scope=sub_p["scope"] or parsed["scope"] or None,
            )
            sub_id = sub_task.get("id")
            if sub_id:
                dep_ids.append(sub_id)

        if main_id and dep_ids:
            _run(str(main_id), "modify", f"depends:{','.join(str(i) for i in dep_ids)}")

        for rel_title in parsed["related_titles"]:
            all_tasks = task_list(status="pending", limit=500)
            existing = next(
                (
                    t
                    for t in all_tasks
                    if rel_title.lower() in t.get("description", "").lower()
                ),
                None,
            )
            rel_id = (
                existing["id"]
                if existing
                else task_add(description=rel_title).get("id")
            )
            if main_id and rel_id:
                task_annotate(main_id, f"related: [{rel_id}] {rel_title}")
                task_annotate(rel_id, f"related: [{main_id}] {parsed['title']}")

        result = task_get(main_id) if main_id else task
        return text({"ok": True, "task": result, "linked": dep_ids})

    elif name == "nota_braindump":
        # Phase 1 stub: treat as nota_add. Real LLM parsing in braindump.py.
        return await call_tool("nota_add", {"title": arguments["text"]})

    elif name == "nota_list":
        pri = arguments.get("priority")
        tasks = task_list(
            project=arguments.get("project"),
            scope=arguments.get("scope"),
            priority_p=f"p{pri}" if pri else None,
        )
        return text(tasks)

    elif name == "nota_next":
        tasks = task_next(limit=arguments.get("limit", 10))
        return text(tasks)

    elif name == "nota_blocked":
        return text(task_blocked())

    elif name == "nota_show":
        t = task_get(arguments["id"])
        if not t:
            return text({"error": f"Task {arguments['id']} not found"})
        return text(t)

    elif name == "nota_done":
        ok = task_done(arguments["id"])
        return text({"ok": ok})

    elif name == "nota_depend":
        ok = task_depend(arguments["id"], arguments["prerequisite_id"])
        return text({"ok": ok})

    elif name == "nota_annotate":
        ok = task_annotate(arguments["id"], arguments["note"])
        return text({"ok": ok})

    elif name == "nota_projects":
        return text(task_projects())

    elif name == "nota_did":
        habit = arguments["habit"]
        comment = arguments.get("comment", "")
        ok = log_habit(habit, comment=comment)
        today_count = count_today(habit)
        return text(
            {
                "ok": ok,
                "habit": habit,
                "today_count": today_count,
                "message": "logged" if ok else "already logged today",
            }
        )

    elif name == "nota_log":
        habit = arguments["habit"]
        comment = arguments.get("comment", "")
        today_count = log_habit_count(habit, comment=comment)
        return text({"ok": True, "habit": habit, "today_count": today_count})

    elif name == "nota_modify":
        task_id = arguments["id"]
        updates = {}

        if "title" in arguments and arguments["title"]:
            updates["description"] = arguments["title"]
        if "project" in arguments and arguments["project"]:
            updates["project"] = arguments["project"]
        if "priority" in arguments and arguments["priority"]:
            updates["priority_p"] = f"p{arguments['priority']}"
        if "due" in arguments and arguments["due"]:
            from src.dateparse import parse_date

            updates["due"] = parse_date(arguments["due"]) or arguments["due"]
        if "scope" in arguments and arguments["scope"]:
            updates["scope"] = arguments["scope"]
        if "tags_add" in arguments and arguments["tags_add"]:
            updates["tags_add"] = arguments["tags_add"]
        if "tags_remove" in arguments and arguments["tags_remove"]:
            updates["tags_remove"] = arguments["tags_remove"]
        if "body" in arguments and arguments["body"]:
            task_annotate(task_id, arguments["body"])

        result = task_modify(task_id, **updates) if updates else task_get(task_id)
        return text({"ok": True, "task": result})

    elif name == "nota_find":
        from src.dateparse import parse_date

        due = arguments.get("due")
        due_arg = parse_date(due) if due else None

        extra_parts = build_filter(
            project=arguments.get("project"),
            scope=arguments.get("scope"),
            priority=arguments.get("priority"),
            status=arguments.get("status", "pending"),
            overdue=arguments.get("overdue"),
            due_this_week=arguments.get("due_this_week"),
            has_annotation=arguments.get("has_annotation"),
            unblocked=arguments.get("unblocked"),
            extra=arguments.get("expression"),
        )
        extra = " ".join(extra_parts) if extra_parts else None

        tasks = task_list(
            project=arguments.get("project"),
            scope=arguments.get("scope"),
            priority_p=f"p{arguments.get('priority')}"
            if arguments.get("priority")
            else None,
            status=arguments.get("status", "pending"),
            extra_filter=extra,
            limit=arguments.get("limit", 50),
        )
        return text(tasks)

    elif name == "nota_scopes":
        from src.scopes import list_scopes

        return text(list_scopes())

    return text({"error": f"Unknown tool: {name}"})


def run():
    import asyncio

    asyncio.run(_run_server())


async def _run_server():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )
