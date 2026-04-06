# maps · cassette.help · MIT
"""
nota config management.

Loads and manages configuration from ~/.nota/nota.toml
"""

import os
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CONFIG = {
    "nota": {
        "default_project": "inbox",
    },
    "scopes": {},
}


def get_config_dir() -> Path:
    """Get nota config directory."""
    return Path(os.environ.get("NOTA_CONFIG", Path.home() / ".nota"))


def get_config_path() -> Path:
    """Get config file path."""
    return get_config_dir() / "nota.toml"


def load_config() -> Dict[str, Any]:
    """Load config from ~/.nota/nota.toml, or return defaults."""
    config_path = get_config_path()

    if config_path.exists():
        with open(config_path, "rb") as f:
            return tomllib.load(f)

    return DEFAULT_CONFIG.copy()


def get_config() -> Dict[str, Any]:
    """Alias for load_config."""
    return load_config()


def save_config(config: Dict[str, Any]) -> None:
    """Save config to ~/.nota/nota.toml."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = get_config_path()
    with open(config_path, "w") as f:
        f.write("# nota configuration\n\n")
        for section, values in config.items():
            f.write(f"[{section}]\n")
            if isinstance(values, dict):
                for key, value in values.items():
                    if isinstance(value, str):
                        f.write(f'{key} = "{value}"\n')
                    else:
                        f.write(f"{key} = {value}\n")
            f.write("\n")


def ensure_config() -> Dict[str, Any]:
    """Ensure config exists, create defaults if not."""
    config = load_config()

    if config == DEFAULT_CONFIG:
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        save_config(DEFAULT_CONFIG)

    return config
