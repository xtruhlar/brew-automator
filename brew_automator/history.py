"""Record a line per run in history.jsonl and show it via `brew-automator history`."""

import json
from datetime import datetime
from pathlib import Path

HISTORY_FILE = Path.home() / ".config" / "brew-automator" / "history.jsonl"

# Keep the file from growing forever; a few years of daily runs is plenty.
MAX_ENTRIES = 1000


def _pkg(p: dict) -> dict:
    return {"name": p["name"], "kind": p["kind"], "from": p["from"], "to": p["to"]}


def record_run(result: dict, notified: bool, now: datetime = None) -> dict:
    """Append a history entry built from a run_maintenance() result and return it.

    In `no-upgrade` mode nothing is installed, so the packages that would have
    been upgraded are recorded as `outdated` instead of `upgraded`.
    """
    now = now or datetime.now()
    candidates = [_pkg(p) for p in result["upgraded"]]
    entry = {
        "timestamp": now.isoformat(timespec="seconds"),
        "mode": result["mode"],
        "status": "problem" if result["has_problem"] else "ok",
        "upgraded": candidates if result["mode"] == "normal" else [],
        "outdated": candidates if result["mode"] != "normal" else [],
        "failed": [_pkg(p) for p in result["failed"]],
        "skipped": [{**_pkg(p), "reason": p["reason"]} for p in result["skipped"]],
        "freed": result["freed"],
        "doctor_ok": result["doctor_ok"],
        "missing_ok": not result["missing_output"],
        "duration_s": result["duration_s"],
        "notified": notified,
    }

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = HISTORY_FILE.read_text().splitlines() if HISTORY_FILE.exists() else []
    lines.append(json.dumps(entry))
    HISTORY_FILE.write_text("\n".join(lines[-MAX_ENTRIES:]) + "\n")
    return entry


def load_history() -> list:
    """Return all entries, oldest first. Unparseable lines are skipped."""
    if not HISTORY_FILE.exists():
        return []
    entries = []
    for line in HISTORY_FILE.read_text().splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def last_run():
    """Return the most recent entry, or None."""
    entries = load_history()
    return entries[-1] if entries else None


def _touches(entry: dict, package: str) -> bool:
    return any(
        p["name"] == package
        for key in ("upgraded", "outdated", "failed", "skipped")
        for p in entry.get(key, [])
    )


def format_entry(entry: dict) -> str:
    """Multi-line human-readable rendering of one entry."""
    timestamp = entry["timestamp"].replace("T", " ")
    mode = "" if entry.get("mode") == "normal" else f" [{entry.get('mode')}]"
    status = "OK" if entry["status"] == "ok" else "PROBLEM"
    lines = [f"{timestamp}  {status}{mode}  ({entry.get('duration_s', 0):.0f}s)"]

    def pkgs(key, label):
        items = entry.get(key, [])
        if items:
            joined = ", ".join(f"{p['name']} {p['from']} -> {p['to']}" for p in items)
            lines.append(f"    {label}: {joined}")

    pkgs("upgraded", "upgraded")
    pkgs("outdated", "outdated")
    pkgs("failed", "FAILED")
    if entry.get("skipped"):
        lines.append("    skipped: " + ", ".join(p["name"] for p in entry["skipped"]))
    if not entry.get("doctor_ok", True):
        lines.append("    brew doctor: issues found")
    if not entry.get("missing_ok", True):
        lines.append("    brew missing: missing dependencies")
    if entry.get("freed"):
        lines.append(f"    freed: {entry['freed']}")
    return "\n".join(lines)


def show_history(limit: int = 10, package: str = None):
    """Entry point for `brew-automator history`."""
    entries = load_history()
    if package:
        entries = [e for e in entries if _touches(e, package)]
    if not entries:
        if package:
            print(f"No runs in history involving '{package}'.")
        else:
            print("No runs recorded yet. History is written by 'brew-automator run'.")
        return

    shown = entries[-limit:] if limit > 0 else entries
    for entry in reversed(shown):
        print(format_entry(entry))
    if len(shown) < len(entries):
        print(f"\n(showing {len(shown)} of {len(entries)} runs - use -n to see more)")
