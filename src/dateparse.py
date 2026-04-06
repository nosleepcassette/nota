# maps · cassette.help · MIT
"""
Local natural language date parsing for nota.

Converts NL dates to ISO 8601 for taskwarrior.
"""

import dateparser
from typing import Optional


TW_SHORTCUTS = {
    "today": "today",
    "tomorrow": "tomorrow",
    "eod": "today",
    "eow": "eow",
    "eom": "eom",
    "eoq": "eoq",
    "eoy": "eoy",
}


def parse_date(input_str: str) -> Optional[str]:
    """
    Parse natural language date to taskwarrior-compatible format.

    Args:
        input_str: e.g., "friday", "next monday", "in 3 days", "2026-04-10"

    Returns:
        ISO date string (YYYY-MM-DD) or taskwarrior shortcut, or None on failure
    """
    if not input_str:
        return None

    s = input_str.strip().lower()

    if s in TW_SHORTCUTS:
        return TW_SHORTCUTS[s]

    parsed = dateparser.parse(
        s,
        settings={
            "STRICT_PARSING": False,
            "PREFER_DAY_OF_MONTH": "current",
        },
    )

    if parsed:
        return parsed.strftime("%Y-%m-%d")

    return None
