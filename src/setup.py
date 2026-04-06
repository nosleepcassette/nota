# maps · cassette.help · MIT
"""
nota setup — installs UDAs and contexts into ~/.taskrc.
Run once: `nota setup`
Safe to re-run (idempotent).
"""

from .tw import setup_udas, _run


NOTA_CONTEXTS = {
    "meatspace": "scope:meatspace",
    "digital":   "scope:digital",
    "server":    "scope:server",
    "waiting":   "+WAITING",
    "blocked":   "+BLOCKED",
    "ready":     "+READY",
}


def run_setup(verbose: bool = True) -> None:
    """Install UDAs and nota contexts. Idempotent."""

    # 1. UDAs
    actions = setup_udas()
    if verbose:
        if actions:
            for a in actions:
                print(f"  ✓ {a}")
        else:
            print("  UDAs already configured.")

    # 2. Contexts
    for name, definition in NOTA_CONTEXTS.items():
        try:
            current = _run("_get", f"rc.context.{name}.read").strip()
        except Exception:
            current = ""
        if current != definition:
            _run("context", "define", name, definition)
            if verbose:
                print(f"  ✓ context '{name}' = {definition}")
        else:
            if verbose:
                print(f"  context '{name}' already set.")

    if verbose:
        print("\nnota setup complete. Run `task udas` to verify.")
