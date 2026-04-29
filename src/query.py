# maps · cassette.help · MIT
"""
nota query/filter builder.

Builds taskwarrior filter expressions from arguments.
"""

from typing import Any, Dict, List, Optional


CUSTOM_FILTERS = {
    "overdue": "due < today",
    "due-this-week": "due <= eow",
    "due-today": "due = today",
    "unblocked": "not depends:",
    "has-annotation": "has:annotation",
    "no-due": "not due:",
}


def build_filter(
    project: Optional[str] = None,
    scope: Optional[str] = None,
    priority: Optional[int] = None,
    status: str = "pending",
    extra: Optional[str] = None,
    **custom_filters,
) -> List[str]:
    """
    Build taskwarrior filter expression from arguments.

    Args:
        project: Filter by project
        scope: Filter by scope UDA
        priority: Filter by priority (1-4)
        status: Filter by status
        extra: Raw taskwarrior expression
        **custom_filters: Custom filters like overdue=True, due_this_week=True

    Returns:
        List of filter parts to pass to taskwarrior
    """
    filters = []

    if status:
        filters.append(f"status:{status}")

    if project:
        filters.append(f"project:{project}")

    if scope:
        filters.append(f"scope:{scope}")

    if priority:
        p_map = {1: "H", 2: "H", 3: "M", 4: "L"}
        p = p_map.get(priority)
        if p:
            filters.append(f"priority:{p}")

    for key, value in custom_filters.items():
        if not value:
            continue

        key_underscore = key.replace("-", "_")
        if key_underscore in CUSTOM_FILTERS and value:
            filters.append(CUSTOM_FILTERS[key_underscore])

    if extra:
        filters.append(extra)

    return filters


def nlp_to_filter(text: str) -> Dict[str, Any]:
    """
    Convert a natural language query to nota filter kwargs.
    Returns dict suitable for passing to build_filter().
    Calls the fast braindump provider.
    """
    NL_FILTER_PROMPT = """Convert a natural language task search query to a JSON filter object.

Output ONLY a JSON object with these optional keys:
{
  "project": "project name or null",
  "scope": "scope name or null",
  "priority": 1|2|3|4 or null,
  "extra": "raw taskwarrior expression or null (e.g. 'due.before:today' for overdue)",
  "status": "pending|completed|all (default: pending)"
}

Examples:
"overdue tasks" -> {"extra": "due.before:today", "status": "pending"}
"health tasks" -> {"project": "health"}
"everything in comms scope digital" -> {"project": "comms", "scope": "digital"}
"urgent meatspace" -> {"scope": "meatspace", "priority": 1}

Output ONLY the JSON. No prose."""

    try:
        from src.braindump import _call_with_prompt
        import json

        result = _call_with_prompt(NL_FILTER_PROMPT, f"Query: {text}")
        parsed = json.loads(result)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}  # fallback: empty filter = show all
