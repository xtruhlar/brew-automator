"""Track the signature of the last reported warning so an unchanged problem
doesn't trigger a fresh email on every scheduled run.
"""

import hashlib
import json
from pathlib import Path

STATE_DIR = Path.home() / ".config" / "brew-automator"
STATE_FILE = STATE_DIR / "state.json"


def load_state() -> dict:
    """Return the saved state, or {} if none exists yet or it's unreadable."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict):
    """Persist the state as JSON."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def warning_signature(doctor_output: str, missing_output: str) -> str:
    """Hash the warning content, used to tell whether a problem is new or
    the same one already reported on a previous run.
    """
    combined = f"{doctor_output}\n{missing_output}"
    return hashlib.sha256(combined.encode()).hexdigest()
