# maps · cassette.help · MIT
"""
nota inline syntax parser.

Syntax reference:
  task title                    plain task
  task title p1                 priority 1 (urgent) — p1 through p4
  task title @project           assign to project
  task title #tag               add tag (multiple ok)
  task title scope:meatspace    set scope
  task title due:2026-04-10     due date (stored as string; no parsing in MVP)
  task title recur:daily        recurring task frequency
  task title until:2026-05-10   recurrence end date
  parent -> child               parent DEPENDS ON child (child is prerequisite)
  task A :: task B              task A is RELATED TO task B

Combinable: "reply to pick n pull p2 @admin -> find stamps :: clean room"
"""

import re
from typing import Any, Dict, List

from src.dateparse import parse_date as parse_nl_date
from src.scopes import get_all_scopes, is_valid_scope


PRIORITY_MAP = {"p1": 1, "p2": 2, "p3": 3, "p4": 4}


def _looks_freeform(text: str) -> bool:
    """
    True if text looks like natural language rather than nota inline syntax.
    Triggers NLP routing in nota add.
    """
    t = text.strip()
    has_syntax = (
        "@" in t
        or "#" in t
        or "::" in t
        or "->" in t
        or "scope:" in t.lower()
        or "recur:" in t.lower()
        or "until:" in t.lower()
        or "due:" in t.lower()
        or any(f" {p}" in t.lower() or t.lower().startswith(f"{p} ") for p in ("p1", "p2", "p3", "p4"))
    )
    return not has_syntax and len(t.split()) >= 4


def _get_scopes_set() -> set:
    """Get scopes as a set for validation."""
    return set(get_all_scopes().keys())


def parse_inline(text: str) -> Dict[str, Any]:
    """
    Parse a nota inline syntax string.

    Returns:
        {
          title:          str   — cleaned task title
          subtasks:       list  — list of subtask title strings (prerequisites of this task)
          related_titles: list  — list of titles to link as related_to
          project:        str   — project name (default 'inbox')
          priority:       int   — 1-4 (default 3)
          scope:          str   — scope string or ''
          tags:           list  — list of tag strings
          due_date:       str|None
          recur:          str|None
          until:          str|None
        }

    Dependency direction:
        "reply to pick n pull -> find stamps"
        → title='reply to pick n pull', subtasks=['find stamps']
        → on insert: parent depends_on each subtask (subtask is prerequisite)
    """
    text = text.strip()

    # ── Step 1: extract related_to (split on ::) ─────────────────────────────
    related_titles: List[str] = []
    if "::" in text:
        parts = text.split("::")
        text = parts[0].strip()
        related_titles = [p.strip() for p in parts[1:] if p.strip()]

    # ── Step 2: extract subtasks/prerequisites (split on ->) ─────────────────
    subtask_titles: List[str] = []
    if "->" in text:
        parts = [p.strip() for p in text.split("->")]
        text = parts[0]
        subtask_titles = [p for p in parts[1:] if p]

    # ── Step 3: extract inline tokens from the title ──────────────────────────
    project = "inbox"
    priority = 3
    scope = ""
    tags: List[str] = []
    due_date = None
    recur = None
    until = None
    tokens_to_remove: List[str] = []

    for token in text.split():
        low = token.lower()
        if low in PRIORITY_MAP:
            priority = PRIORITY_MAP[low]
            tokens_to_remove.append(token)
        elif token.startswith("@") and len(token) > 1:
            project = token[1:]
            tokens_to_remove.append(token)
        elif token.startswith("#") and len(token) > 1:
            tags.append(token[1:])
            tokens_to_remove.append(token)
        elif low.startswith("scope:"):
            sc = low[6:]
            valid_scopes = _get_scopes_set()
            if sc in valid_scopes:
                scope = sc
            else:
                tags.append(f"scope:{sc}")
            tokens_to_remove.append(token)
        elif low.startswith("due:"):
            due_raw = token[4:]
            due_date = parse_nl_date(due_raw) or due_raw  # parse NL, fallback to raw
            tokens_to_remove.append(token)
        elif low.startswith("recur:"):
            recur = token[6:]
            tokens_to_remove.append(token)
        elif low.startswith("until:"):
            until = token[6:]
            tokens_to_remove.append(token)

    for tok in tokens_to_remove:
        # Replace whole-word occurrences only
        text = re.sub(r"(?<!\S)" + re.escape(tok) + r"(?!\S)", "", text)

    title = re.sub(r"\s+", " ", text).strip()

    return {
        "title": title,
        "subtasks": subtask_titles,
        "related_titles": related_titles,
        "project": project,
        "priority": priority,
        "scope": scope,
        "tags": tags,
        "due_date": due_date,
        "recur": recur,
        "until": until,
    }
