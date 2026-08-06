"""Load/save the list of formulae and casks excluded from automatic upgrades.

Kept dependency-free (no import of `maintenance`) so `maintenance` can import
this module without creating a circular import with the `settings` UI, which
itself needs both `maintenance` (to list installed packages) and this module.
"""

import json
from pathlib import Path

IGNORE_FILE = Path.home() / ".config" / "brew-automator" / "ignored.json"


def load_ignored() -> dict:
    """Return {"formulae": [...], "casks": [...]}, empty lists if none saved yet."""
    if not IGNORE_FILE.exists():
        return {"formulae": [], "casks": []}
    try:
        data = json.loads(IGNORE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"formulae": [], "casks": []}
    return {
        "formulae": data.get("formulae", []),
        "casks": data.get("casks", []),
    }


def save_ignored(ignored: dict):
    """Persist {"formulae": [...], "casks": [...]} as JSON."""
    IGNORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    IGNORE_FILE.write_text(json.dumps(ignored, indent=2))
