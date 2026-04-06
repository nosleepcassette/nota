# maps · cassette.help · MIT
"""
nota scopes management.

Manages default + user-defined scopes.
"""

from typing import Dict, List, Optional, Tuple
from src.config import get_config, load_config


DEFAULT_SCOPES = {
    "meatspace": ("🏠", "Physical, real-world tasks"),
    "digital": ("💻", "Computer/online tasks"),
    "server": ("🖥️", "System admin, sextile tasks"),
    "opencassette": ("📼", "Opencassette server tasks"),
    "appointment": ("📅", "Time-bound external obligations"),
    "recurring": ("🔄", "Recurring tasks"),
    "waiting": ("⏳", "Waiting on external response"),
    "creative": ("🎨", "Creative work"),
    "admin": ("📋", "Administrative tasks"),
    "errand": ("🚶", "Quick errands"),
}


def get_all_scopes() -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """Get all scopes (defaults + user-defined)."""
    config = load_config()
    user_scopes = config.get("scopes", {})
    meta = config.get("scopes_meta", {})

    all_scopes = dict(DEFAULT_SCOPES)

    for name, value in user_scopes.items():
        meta_str = meta.get(name, "")
        # Try to parse "emoji description" format
        parts = meta_str.split(" ", 1)
        emoji = parts[0] if parts else ""
        desc = parts[1] if len(parts) > 1 else ""
        all_scopes[name] = (emoji, desc)

    return all_scopes


def list_scopes() -> List[Dict[str, str]]:
    """List all scopes as dicts with name, emoji, description."""
    scopes = get_all_scopes()
    return [
        {"name": name, "emoji": emoji or "", "description": desc or ""}
        for name, (emoji, desc) in scopes.items()
    ]


def is_valid_scope(scope_name: str) -> bool:
    """Check if scope name is valid."""
    return scope_name.lower() in get_all_scopes()


def add_scope(
    name: str, emoji: Optional[str] = None, description: Optional[str] = None
) -> bool:
    """Add a user-defined scope. Returns True if added."""
    config = load_config()
    scopes = config.setdefault("scopes", {})

    if name in DEFAULT_SCOPES:
        return False

    if name in scopes:
        return False

    if emoji or description:
        meta = config.setdefault("scopes_meta", {})
        meta[name] = f"{emoji or ''} {description or ''}".strip()

    scopes[name] = name

    from src.config import save_config

    save_config(config)

    # Also add to taskwarrior UDA
    try:
        import subprocess

        current = subprocess.run(
            ["task", "_get", "rc.uda.scope.values"], capture_output=True, text=True
        ).stdout.strip()
        if name not in current:
            new_values = f"{current},{name}"
            subprocess.run(["task", "config", "rc.uda.scope.values", new_values])
    except Exception:
        pass

    return True


def rm_scope(name: str) -> bool:
    """Remove a user-defined scope. Returns True if removed."""
    config = load_config()
    scopes = config.get("scopes", {})

    if name in DEFAULT_SCOPES:
        return False

    if name not in scopes:
        return False

    del scopes[name]
    from src.config import save_config

    save_config(config)
    return True
