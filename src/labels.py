# maps · cassette.help · MIT
"""Energy/context label taxonomy for nota tasks."""

ENERGY_TAGS = {
    "quick": {"desc": "under 5 minutes", "color": "#a07800"},
    "easy": {"desc": "low cognitive load", "color": "#a07800"},
    "deep": {"desc": "requires uninterrupted focus", "color": "#ffb000"},
    "call": {"desc": "phone or video required", "color": "#e8e8e8"},
    "errand": {"desc": "requires leaving the house", "color": "#c87800"},
    "waiting": {"desc": "blocked on someone else", "color": "#666666"},
    "anywhere": {"desc": "location-independent", "color": "#a07800"},
    "creative": {"desc": "creative output required", "color": "#ffb000"},
    "admin": {"desc": "paperwork/forms/bureaucracy", "color": "#a07800"},
}


def is_energy_tag(tag: str) -> bool:
    return tag.lower() in ENERGY_TAGS


def energy_tag_color(tag: str) -> str:
    return ENERGY_TAGS.get(tag.lower(), {}).get("color", "#a07800")
