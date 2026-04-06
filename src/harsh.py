# maps · cassette.help · MIT
"""
Minimal harsh interface for nota CLI.
Reads/writes ~/.config/harsh/{habits,log} directly.
Full HarshStore (with harsh CLI JSON integration) lives in ~/dev/bene/src/tui/harsh_store.py.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Dict

HARSH_DIR = Path(os.environ.get("HARSHPATH", Path.home() / ".config" / "harsh"))
HABITS_FILE = HARSH_DIR / "habits"
LOG_FILE = HARSH_DIR / "log"


def habit_names() -> List[str]:
    if not HABITS_FILE.exists():
        return []
    names = []
    for line in HABITS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        name = line.split(":")[0].strip()
        if name:
            names.append(name)
    return names


def add_habit(name: str, frequency: str = "0") -> None:
    """Append new habit to habits file (idempotent)."""
    HARSH_DIR.mkdir(parents=True, exist_ok=True)
    if name in habit_names():
        return
    with HABITS_FILE.open("a") as f:
        f.write(f"{name}: {frequency}\n")


def log_habit(
    name: str, result: str = "y", day: Optional[date] = None, comment: str = ""
) -> bool:
    """Append a log entry. Returns False if already logged today."""
    HARSH_DIR.mkdir(parents=True, exist_ok=True)
    d = day or date.today()
    date_str = d.isoformat()
    if LOG_FILE.exists():
        for line in LOG_FILE.read_text().splitlines():
            parts = [p.strip() for p in line.split(":")]
            if len(parts) >= 2 and parts[0] == date_str and parts[1] == name:
                return False
    parts = [date_str, name, result]
    if comment:
        parts.append(comment)
    with LOG_FILE.open("a") as f:
        f.write(" : ".join(parts) + "\n")
    return True


def log_habit_count(name: str, day: Optional[date] = None, comment: str = "") -> int:
    """
    Append a count entry (always, no duplicate guard). Returns today's total count.
    Use for habits you want to track multiple times per day (e.g. cigarettes, drinks).
    """
    HARSH_DIR.mkdir(parents=True, exist_ok=True)
    add_habit(name)
    d = day or date.today()
    date_str = d.isoformat()
    parts = [date_str, name, "1"]
    if comment:
        parts.append(comment)
    with LOG_FILE.open("a") as f:
        f.write(" : ".join(parts) + "\n")
    return count_today(name, day=d)


def count_today(name: str, day: Optional[date] = None) -> int:
    """Return how many times a habit was logged today (sums numeric results)."""
    if not LOG_FILE.exists():
        return 0
    d = day or date.today()
    date_str = d.isoformat()
    total = 0
    for line in LOG_FILE.read_text().splitlines():
        parts = [p.strip() for p in line.split(":")]
        if len(parts) >= 3 and parts[0] == date_str and parts[1] == name:
            try:
                total += int(parts[2])
            except ValueError:
                total += 1  # treat 'y' entries as 1
    return total


def today_results() -> dict:
    """Return {habit_name: result} for today's entries."""
    if not LOG_FILE.exists():
        return {}
    today_str = date.today().isoformat()
    out = {}
    for line in LOG_FILE.read_text().splitlines():
        parts = [p.strip() for p in line.split(":")]
        if len(parts) >= 3 and parts[0] == today_str:
            out[parts[1]] = parts[2]
    return out


def get_history(name: str, days: int = 30) -> List[Dict[str, str]]:
    """Get history for a habit over N days."""
    if not LOG_FILE.exists():
        return []

    history = []
    for i in range(days):
        d = date.today() - timedelta(days=i)
        date_str = d.isoformat()
        count = 0
        for line in LOG_FILE.read_text().splitlines():
            parts = [p.strip() for p in line.split(":")]
            if len(parts) >= 3 and parts[0] == date_str and parts[1] == name:
                try:
                    count += int(parts[2])
                except ValueError:
                    count += 1
        history.append({"date": date_str, "count": count})
    return history


def get_streak(name: str) -> int:
    """Get current streak for a habit (consecutive days with count > 0)."""
    history = get_history(name, days=365)
    streak = 0
    for entry in history:
        if entry["count"] > 0:
            streak += 1
        elif streak > 0:
            break
    return streak


def get_longest_streak(name: str) -> int:
    """Get longest streak for a habit."""
    history = get_history(name, days=365)
    longest = 0
    current = 0
    for entry in history:
        if entry["count"] > 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def get_completion_rate(name: str, days: int = 30) -> float:
    """Get completion rate over N days (days with count > 0 / total days)."""
    history = get_history(name, days=days)
    completed = sum(1 for e in history if e["count"] > 0)
    return (completed / days) * 100 if days > 0 else 0
