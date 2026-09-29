"""Run the actual Homebrew maintenance steps and build a report.

Also handles local logging (~/.config/brew-automator/logs) and the
macOS notification shown after each run.
"""

import json
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from brew_automator import ignorelist

STATE_DIR = Path.home() / ".config" / "brew-automator"
LOG_DIR = STATE_DIR / "logs"
REPORT_FILE = STATE_DIR / "report.txt"
LOG_FILE = LOG_DIR / "brew-maintenance.log"

# Run modes for run_maintenance():
#   normal     - full maintenance (upgrade + cleanup)
#   no-upgrade - check and report only; nothing installed is upgraded or cleaned up
#   dry-run    - like no-upgrade, but asks brew what upgrade/cleanup *would* do
MODE_NORMAL = "normal"
MODE_NO_UPGRADE = "no-upgrade"
MODE_DRY_RUN = "dry-run"

# Matches e.g. "This operation has freed approximately 1.2GB of disk space."
# and, for `brew cleanup --dry-run`, "This operation would free approximately 1.2GB ...".
_FREED_RE = re.compile(r"(?:freed|free) approximately ([\d.]+\s*[KMGT]?B)")


def _find_brew() -> str:
    """Locate the brew executable. launchd runs jobs with a minimal PATH that
    doesn't include /opt/homebrew/bin or /usr/local/bin, so `brew` alone isn't
    reliably found when triggered by a scheduled launchd job.
    """
    brew = shutil.which("brew")
    if brew:
        return brew
    for candidate in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if Path(candidate).exists():
            return candidate
    return "brew"


BREW = _find_brew()


def _run(*args: str) -> str:
    """Run a brew subcommand and return its combined stdout+stderr, ignoring the exit code."""
    return _run_with_exit(*args)[0]


def _run_with_exit(*args: str):
    """Like _run, but also return the exit code."""
    result = subprocess.run([BREW, *args], capture_output=True, text=True)
    return (result.stdout + result.stderr).strip(), result.returncode


def log(message: str):
    """Append a timestamped line to the maintenance log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a") as f:
        f.write(f"[{timestamp}] {message}\n")


def _version_str(versions) -> str:
    """`installed_versions` is a list in `--json=v2` (a plain string for casks on older brew)."""
    if isinstance(versions, list):
        return ", ".join(str(v) for v in versions) or "?"
    return str(versions or "?")


def _get_outdated() -> dict:
    """Return {"formulae": [...], "casks": [...]}, each entry a dict with
    name/from/to/pinned, parsed from `brew outdated --json=v2 --greedy-latest`.

    JSON is used instead of the human-readable output because `brew outdated`
    prints bare names (no versions) when stdout isn't a TTY, which is always
    the case here.
    """
    output, _ = _run_with_exit("outdated", "--json=v2", "--greedy-latest")
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        # brew may print a warning before the JSON; parse from the first "{".
        start = output.find("{")
        try:
            data = json.loads(output[start:]) if start != -1 else {}
        except json.JSONDecodeError:
            data = {}

    def entries(key):
        return [
            {
                "name": item.get("name", "?"),
                "from": _version_str(item.get("installed_versions")),
                "to": str(item.get("current_version") or "?"),
                "pinned": bool(item.get("pinned")),
            }
            for item in data.get(key, [])
        ]

    return {"formulae": entries("formulae"), "casks": entries("casks")}


def _format_packages(packages: list) -> str:
    """One `name from -> to` line per package, or `none`."""
    return "\n".join(f"{p['name']} {p['from']} -> {p['to']}" for p in packages) or "none"


def _format_names(packages: list, with_versions: bool = True) -> str:
    if not packages:
        return "none"
    if with_versions:
        return ", ".join(f"{p['name']} ({p['from']} -> {p['to']})" for p in packages)
    return ", ".join(p["name"] for p in packages)


def _build_summary(mode, status_ok, upgraded, failed, skipped, freed, upgrade_exit_codes,
                   doctor_exit, missing_output, duration_s) -> str:
    """Human-readable summary shown at the top of the report (and used as the
    body of webhook notifications)."""
    lines = [f"Status: {'OK' if status_ok else 'PROBLEM'}"]
    if mode == MODE_NORMAL:
        lines.append(f"Upgraded ({len(upgraded)}): {_format_names(upgraded)}")
        lines.append(f"Failed ({len(failed)}): {_format_names(failed)}")
        bad_exits = [code for code in upgrade_exit_codes if code != 0]
        if bad_exits and not failed:
            lines.append(f"brew upgrade exited with code {bad_exits[0]} (see details below)")
    elif mode == MODE_DRY_RUN:
        lines.append(f"Would upgrade ({len(upgraded)}): {_format_names(upgraded)}")
    else:
        lines.append(f"Outdated, not upgraded ({len(upgraded)}): {_format_names(upgraded)}")
    lines.append(
        f"Skipped ({len(skipped)}): "
        + (", ".join(f"{p['name']} ({p['reason']})" for p in skipped) or "none")
    )
    if mode != MODE_NO_UPGRADE:
        label = "Would free" if mode == MODE_DRY_RUN else "Freed by cleanup"
        lines.append(f"{label}: {freed or 'nothing'}")
    lines.append(f"brew doctor: {'OK' if doctor_exit == 0 else 'issues found'}")
    lines.append(f"brew missing: {'OK' if not missing_output else 'missing dependencies'}")
    lines.append(f"Duration: {duration_s:.0f}s")
    return "\n".join(lines)


def run_maintenance(mode: str = MODE_NORMAL) -> dict:
    """Run update/outdated/upgrade/cleanup/doctor/missing, write the report file,
    and return a dict describing the run (see the return statement).

    `brew upgrade` and `brew cleanup` already cover both formulae and casks by
    default. Outdated casks are checked with `--greedy-latest`, since version
    :latest casks otherwise aren't flagged as outdated. `--greedy-latest`
    deliberately skips auto_updates-true casks (e.g. browsers that update
    themselves) - those would just be noise here since brew isn't managing
    their updates anyway.

    Formulae/casks excluded via `brew-automator settings` (and pinned formulae)
    are left out of the upgrade step but still listed as skipped, so you know
    they're being held back on purpose, not silently ignored.

    A run counts as a problem when `brew doctor` fails, `brew missing` reports
    something, or an upgrade fails (non-zero exit, or a package that was
    upgraded is still outdated afterwards).

    In dry-run mode the report file is not written - nothing on disk changes
    apart from `brew update` refreshing Homebrew's own package index.
    """
    started = time.monotonic()
    log(f"Starting brew maintenance run (mode={mode})")

    print("→ brew update")
    update_output = _run("update")

    print("→ brew outdated")
    outdated = _get_outdated()

    ignored = ignorelist.load_ignored()
    to_upgrade = {"formulae": [], "casks": []}
    skipped = []
    for kind in ("formulae", "casks"):
        for pkg in outdated[kind]:
            if pkg["name"] in ignored[kind]:
                skipped.append({**pkg, "kind": kind, "reason": "excluded"})
            elif pkg["pinned"]:
                skipped.append({**pkg, "kind": kind, "reason": "pinned"})
            else:
                to_upgrade[kind].append(pkg)

    candidates = [{**p, "kind": kind} for kind in ("formulae", "casks") for p in to_upgrade[kind]]
    upgraded, failed, upgrade_exit_codes = [], [], []
    upgrade_parts = []
    cleanup_output = ""

    if mode == MODE_NO_UPGRADE:
        upgrade_output = "Skipped (--no-upgrade)."
        cleanup_output = "Skipped (--no-upgrade)."
        upgraded = candidates
    else:
        dry = ["--dry-run"] if mode == MODE_DRY_RUN else []
        print("→ brew upgrade" + (" --dry-run" if dry else ""))
        for kind, flag in (("formulae", "--formula"), ("casks", "--cask")):
            names = [p["name"] for p in to_upgrade[kind]]
            if names:
                output, code = _run_with_exit("upgrade", *dry, flag, *names)
                upgrade_exit_codes.append(code)
                if output:
                    upgrade_parts.append(output)
        upgrade_output = "\n".join(upgrade_parts) or "Nothing to upgrade."

        if mode == MODE_DRY_RUN or not candidates:
            upgraded = candidates
        else:
            # Anything we tried to upgrade that's still outdated afterwards failed.
            after = _get_outdated()
            still_outdated = {
                (kind, p["name"]) for kind in ("formulae", "casks") for p in after[kind]
            }
            for pkg in candidates:
                (failed if (pkg["kind"], pkg["name"]) in still_outdated else upgraded).append(pkg)

        print("→ brew cleanup" + (" --dry-run" if dry else ""))
        cleanup_output = _run("cleanup", *dry)

    freed_match = _FREED_RE.search(cleanup_output)
    freed = freed_match.group(1).replace(" ", "") if freed_match else ""

    print("→ brew doctor")
    doctor_output, doctor_exit = _run_with_exit("doctor")

    print("→ brew missing")
    missing_output = _run("missing")

    upgrade_error = bool(failed) or any(code != 0 for code in upgrade_exit_codes)
    has_problem = doctor_exit != 0 or bool(missing_output) or upgrade_error
    duration_s = time.monotonic() - started

    summary = _build_summary(
        mode, not has_problem, upgraded, failed, skipped, freed, upgrade_exit_codes,
        doctor_exit, missing_output, duration_s,
    )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode_note = "" if mode == MODE_NORMAL else f" ({mode})"
    report = (
        f"Homebrew maintenance report - {timestamp}{mode_note}\n\n"
        f"== Summary ==\n{summary}\n\n"
        f"== brew update ==\n{update_output}\n\n"
        f"== brew outdated — Formulae (before upgrade) ==\n{_format_packages(outdated['formulae'])}\n\n"
        f"== brew outdated — Casks (before upgrade, --greedy-latest) ==\n{_format_packages(outdated['casks'])}\n\n"
        f"== brew upgrade ==\n{upgrade_output}\n\n"
        f"== Skipped (excluded via 'brew-automator settings' or pinned) ==\n"
        f"Formulae: {', '.join(p['name'] for p in skipped if p['kind'] == 'formulae') or 'none'}\n"
        f"Casks: {', '.join(p['name'] for p in skipped if p['kind'] == 'casks') or 'none'}\n\n"
        f"== brew cleanup ==\n{cleanup_output}\n\n"
        f"== brew doctor ==\n{doctor_output}\n\n"
        f"== brew missing ==\n{missing_output}\n"
    )

    if mode != MODE_DRY_RUN:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text(report)

    log(f"Finished brew maintenance run (mode={mode}, problem={has_problem})")
    print(f"→ Done ({'problem detected' if has_problem else 'all OK'})")

    return {
        "mode": mode,
        "report": report,
        "summary": summary,
        "short_summary": _short_summary(mode, upgraded, failed, has_problem),
        "has_problem": has_problem,
        "doctor_ok": doctor_exit == 0,
        "doctor_output": doctor_output,
        "missing_output": missing_output,
        "upgraded": upgraded,
        "failed": failed,
        "skipped": skipped,
        "freed": freed,
        "duration_s": round(duration_s, 1),
    }


def _short_summary(mode, upgraded, failed, has_problem) -> str:
    """One-liner for the macOS notification."""
    if mode == MODE_NORMAL:
        parts = []
        if upgraded:
            parts.append(f"Upgraded: {_format_names(upgraded, with_versions=False)}")
        if failed:
            parts.append(f"Failed: {_format_names(failed, with_versions=False)}")
        text = "; ".join(parts) or "Nothing to update"
    else:
        text = f"Outdated: {_format_names(upgraded, with_versions=False)}" if upgraded else "Nothing to update"
    if has_problem and not failed:
        text += " (problem detected - see report)"
    return text


def notify_local(summary: str, title: str = "🍺 Homebrew"):
    """Show a macOS notification via osascript. Quotes/backslashes are escaped
    since `summary` is interpolated into an AppleScript string literal.
    """
    escaped_summary = summary.replace("\\", "\\\\").replace('"', '\\"')
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{escaped_summary}" with title "{escaped_title}"',
            ]
        )
    except FileNotFoundError:
        # Not on macOS - nothing to show.
        pass
