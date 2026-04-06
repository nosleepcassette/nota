# maps · cassette.help · MIT
"""
nota query/filter builder.

Builds taskwarrior filter expressions from arguments.
"""

from typing import List, Optional


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
