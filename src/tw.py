# maps · cassette.help · MIT
"""
nota taskwarrior subprocess wrapper.

All taskwarrior interaction goes through here. Callers never shell out
directly — use these functions instead.

Taskwarrior field reference (what we use):
  description   — task title (string)
  project       — project name, supports hierarchy with dots (Home.Kitchen)
  priority      — H / M / L / "" (maps from p1→H, p2→H, p3→M, p4→L)
  due           — due date string (taskwarrior parses naturally: today, eow, 2026-04-10)
  wait          — hide until date (for waiting/deferred tasks)
  scheduled     — date after which task is actionable
  recur         — recurrence frequency (daily, weekly, monthly…)
  depends       — comma-separated task IDs this task depends on (blocking tasks)
  tags          — list of strings (+tag)
  status        — pending / completed / deleted / waiting / recurring
  entry         — creation timestamp (auto)
  modified      — last-modified timestamp (auto)
  uuid          — permanent unique ID (auto)
  id            — working-set integer ID (can change; use uuid for permanence)
  urgency       — computed score (higher = more urgent)
  UDA scope     — custom field: meatspace/digital/server/opencassette/
                  appointment/recurring/waiting/creative/admin/errand
"""

import json
import subprocess
import sys
from typing import Any, Dict, List, Optional


TASK_BIN = "task"
PRIORITY_FROM_P = {"p1": "H", "p2": "H", "p3": "M", "p4": "L", "": ""}
PRIORITY_TO_LABEL = {"H": "!!!!", "M": "!!", "L": "~", "": ""}


# ── low-level subprocess ───────────────────────────────────────────────────────

def _run(*args: str, input_data: Optional[str] = None, confirm: bool = False) -> str:
    """
    Run a task command. Returns stdout as string.
    Raises RuntimeError on non-zero exit (unless it's a confirmation prompt).
    """
    cmd = [TASK_BIN, "rc.confirmation=off", "rc.recurrence.confirmation=off"] + list(args)
    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and result.stderr.strip():
        # Some task commands exit non-zero for informational output — check stderr
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def _run_json(*args: str) -> List[Dict[str, Any]]:
    """Run task export command, return parsed JSON list."""
    out = _run(*args)
    if not out:
        return []
    return json.loads(out)


# ── UDA / setup ───────────────────────────────────────────────────────────────

SCOPE_VALUES = "meatspace,digital,server,opencassette,appointment,recurring,waiting,creative,admin,errand"

def setup_udas() -> List[str]:
    """
    Install nota UDAs into ~/.taskrc. Idempotent.
    Returns list of actions taken.
    """
    actions = []
    configs = [
        ("uda.scope.type",   "string"),
        ("uda.scope.label",  "Scope"),
        ("uda.scope.values", SCOPE_VALUES),
    ]
    for key, value in configs:
        try:
            current = _run("_get", f"rc.{key}").strip()
        except Exception:
            current = ""
        if current != value:
            _run("config", key, value)
            actions.append(f"set {key}={value}")
    return actions


# ── add ───────────────────────────────────────────────────────────────────────

def task_add(
    description: str,
    project: Optional[str] = None,
    priority_p: Optional[str] = None,   # "p1"–"p4"
    due: Optional[str] = None,
    wait: Optional[str] = None,
    scheduled: Optional[str] = None,
    recur: Optional[str] = None,
    tags: Optional[List[str]] = None,
    scope: Optional[str] = None,
    depends: Optional[List[int]] = None,  # list of task IDs
    body: Optional[str] = None,           # added as annotation after creation
) -> Dict[str, Any]:
    """
    Add a task via `task add`. Returns the created task dict (from export).
    """
    args = ["add"]

    if project:
        args.append(f"project:{project}")
    if priority_p and priority_p in PRIORITY_FROM_P:
        pri = PRIORITY_FROM_P[priority_p]
        if pri:
            args.append(f"priority:{pri}")
    if due:
        args.append(f"due:{due}")
    if wait:
        args.append(f"wait:{wait}")
    if scheduled:
        args.append(f"scheduled:{scheduled}")
    if recur:
        args.append(f"recur:{recur}")
    if scope:
        args.append(f"scope:{scope}")
    if depends:
        args.append(f"depends:{','.join(str(d) for d in depends)}")
    for tag in (tags or []):
        args.append(f"+{tag}")

    # Description must come last
    args.append(description)

    out = _run(*args)
    # Output: "Created task 5." — extract ID
    task_id = None
    for word in out.split():
        w = word.rstrip(".,")
        if w.isdigit():
            task_id = int(w)
            break

    if task_id and body:
        try:
            _run(str(task_id), "annotate", body)
        except Exception:
            pass  # annotation failure is non-fatal

    if task_id:
        tasks = _run_json(str(task_id), "export")
        return tasks[0] if tasks else {"id": task_id}
    return {"raw": out}


# ── query ─────────────────────────────────────────────────────────────────────

def task_get(task_id: int) -> Optional[Dict[str, Any]]:
    """Return full task dict for one task ID. None if not found."""
    tasks = _run_json(str(task_id), "export")
    return tasks[0] if tasks else None


def task_list(
    project: Optional[str] = None,
    scope: Optional[str] = None,
    priority_p: Optional[str] = None,
    status: str = "pending",
    extra_filter: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Export tasks matching filters.
    Returns list of task dicts ordered by urgency desc (taskwarrior default).
    """
    args = []
    if status:
        args.append(f"status:{status}")
    if project:
        args.append(f"project:{project}")
    if scope:
        args.append(f"scope:{scope}")
    if priority_p and priority_p in PRIORITY_FROM_P:
        pri = PRIORITY_FROM_P[priority_p]
        if pri:
            args.append(f"priority:{pri}")
    if extra_filter:
        args.extend(extra_filter.split())
    args.append("export")
    tasks = _run_json(*args)
    # Sort by urgency descending
    tasks.sort(key=lambda t: t.get("urgency", 0), reverse=True)
    return tasks[:limit]


def task_next(limit: int = 20) -> List[Dict[str, Any]]:
    """Return most urgent ready (unblocked, actionable) tasks."""
    tasks = _run_json("+READY", "export")
    tasks.sort(key=lambda t: t.get("urgency", 0), reverse=True)
    return tasks[:limit]


def task_blocked() -> List[Dict[str, Any]]:
    """Return all currently blocked tasks."""
    return _run_json("+BLOCKED", "export")


def task_export_all() -> List[Dict[str, Any]]:
    """Full export of all tasks (all statuses)."""
    return _run_json("export")


def task_projects() -> List[Dict[str, Any]]:
    """Return list of {project, count} for pending tasks."""
    tasks = _run_json("status:pending", "export")
    counts: Dict[str, int] = {}
    for t in tasks:
        proj = t.get("project") or "inbox"
        counts[proj] = counts.get(proj, 0) + 1
    return [{"project": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]


# ── modify ────────────────────────────────────────────────────────────────────

def task_done(task_id: int) -> bool:
    """Mark task complete. Returns True on success."""
    try:
        _run(str(task_id), "done")
        return True
    except RuntimeError:
        return False


def task_delete(task_id: int) -> bool:
    """Delete (soft-delete) a task."""
    try:
        _run(str(task_id), "delete")
        return True
    except RuntimeError:
        return False


def task_modify(task_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Modify arbitrary fields on a task.
    Accepts same kwargs as task_add (project, priority_p, due, tags_add, tags_remove, scope).
    """
    args = [str(task_id), "modify"]
    if "project" in kwargs:
        args.append(f"project:{kwargs['project']}")
    if "priority_p" in kwargs:
        pri = PRIORITY_FROM_P.get(kwargs["priority_p"], "")
        args.append(f"priority:{pri}")
    if "due" in kwargs:
        args.append(f"due:{kwargs['due']}")
    if "scope" in kwargs:
        args.append(f"scope:{kwargs['scope']}")
    if "description" in kwargs:
        args.append(kwargs["description"])
    for tag in kwargs.get("tags_add", []):
        args.append(f"+{tag}")
    for tag in kwargs.get("tags_remove", []):
        args.append(f"-{tag}")
    try:
        _run(*args)
        return task_get(task_id)
    except RuntimeError as e:
        return None


def task_depend(task_id: int, depends_on_id: int) -> bool:
    """Add a dependency: task_id depends on depends_on_id."""
    try:
        _run(str(task_id), "modify", f"depends:{depends_on_id}")
        return True
    except RuntimeError:
        return False


def task_annotate(task_id: int, note: str) -> bool:
    """Add an annotation (timestamped note) to a task."""
    try:
        _run(str(task_id), "annotate", note)
        return True
    except RuntimeError:
        return False


# ── import ────────────────────────────────────────────────────────────────────

def task_import(tasks_json: List[Dict[str, Any]]) -> str:
    """
    Import tasks from a JSON list. Used by braindump.
    Returns taskwarrior's output string.
    """
    return _run("import", input_data=json.dumps(tasks_json))


# ── formatting helpers ────────────────────────────────────────────────────────

def fmt_row(t: Dict[str, Any]) -> str:
    tid = t.get("id", "?")
    desc = t.get("description", "")
    pri = PRIORITY_TO_LABEL.get(t.get("priority", ""), "")
    proj = t.get("project", "")
    due = t.get("due", "")[:8] if t.get("due") else ""  # 20260406T... → 20260406
    scope = t.get("scope", "")
    tags = " ".join(f"+{tag}" for tag in (t.get("tags") or []))
    blocked = " [BLOCKED]" if "BLOCKED" in (t.get("virtual_tags") or []) else ""
    parts = [f"[{tid:>4}]", f"{pri:<4}", desc]
    if proj:
        parts.append(f"@{proj}")
    if scope:
        parts.append(f"scope:{scope}")
    if due:
        parts.append(f"due:{due}")
    if tags:
        parts.append(tags)
    if blocked:
        parts.append(blocked)
    return "  ".join(p for p in parts if p)


def fmt_detail(t: Dict[str, Any]) -> str:
    lines = [
        f"Task #{t.get('id')} — {t.get('description')}",
        f"  UUID:     {t.get('uuid','')}",
        f"  Project:  {t.get('project','(none)')}",
        f"  Priority: {t.get('priority','(none)')} {PRIORITY_TO_LABEL.get(t.get('priority',''),'')}",
        f"  Scope:    {t.get('scope','(none)')}",
        f"  Due:      {(t.get('due') or '')[:8] or '(none)'}",
        f"  Status:   {t.get('status','')}",
        f"  Urgency:  {t.get('urgency',0):.2f}",
        f"  Tags:     {', '.join(t.get('tags') or []) or '(none)'}",
    ]
    if t.get("annotations"):
        lines.append("  Notes:")
        for ann in t["annotations"]:
            lines.append(f"    {ann.get('description','')}")
    if t.get("depends"):
        lines.append("  Depends on (prerequisites):")
        for dep_uuid in t["depends"]:
            # Look up by uuid
            found = _run_json(f"uuid:{dep_uuid}", "export")
            if found:
                d = found[0]
                mark = "✓" if d.get("status") == "completed" else "○"
                lines.append(f"    {mark} [{d.get('id','?')}] {d.get('description','')}")
    return "\n".join(lines)
