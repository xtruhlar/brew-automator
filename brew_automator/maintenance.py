"""Run the actual Homebrew maintenance steps and build a report.

Also handles local logging (~/.config/brew-automator/logs) and the
macOS notification shown after each run.
"""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from brew_automator import ignorelist

STATE_DIR = Path.home() / ".config" / "brew-automator"
LOG_DIR = STATE_DIR / "logs"
REPORT_FILE = STATE_DIR / "report.txt"
LOG_FILE = LOG_DIR / "brew-maintenance.log"


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
    result = subprocess.run([BREW, *args], capture_output=True, text=True)
    return (result.stdout + result.stderr).strip()


def _run_with_exit(*args: str):
    """Like _run, but also return the exit code (used for brew doctor's status)."""
    result = subprocess.run([BREW, *args], capture_output=True, text=True)
    return (result.stdout + result.stderr).strip(), result.returncode


def log(message: str):
    """Append a timestamped line to the maintenance log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a") as f:
        f.write(f"[{timestamp}] {message}\n")


def run_maintenance() -> dict:
    """Run update/outdated/upgrade/cleanup/doctor/missing, write the report file,
    and return a dict with the report text, the outdated-package summary, and
    whether a problem was detected (non-zero `brew doctor` or `brew missing` output).

    `brew upgrade` and `brew cleanup` already cover both formulae and casks by
    default, but `brew outdated` is reported separately for each (with
    `--greedy-latest` for casks, since version :latest casks otherwise aren't
    flagged as outdated) so the report clearly shows what's stale on each side.
    `--greedy-latest` deliberately skips auto_updates-true casks (e.g. browsers
    that update themselves) - those would just be noise here since brew isn't
    managing their updates anyway.

    Formulae/casks excluded via `brew-automator settings` are left out of the
    upgrade step (but still shown in the outdated sections, so you know they
    exist and are being skipped on purpose, not silently ignored).
    """
    log("Starting brew maintenance run")

    print("→ brew update")
    update_output = _run("update")

    print("→ brew outdated (formulae)")
    outdated_formula_output = _run("outdated", "--formula")
    outdated_formula_names = [n for n in _run("outdated", "--formula", "--quiet").splitlines() if n]

    print("→ brew outdated (casks)")
    outdated_cask_output = _run("outdated", "--cask", "--greedy-latest")
    outdated_cask_names = [
        n for n in _run("outdated", "--cask", "--greedy-latest", "--quiet").splitlines() if n
    ]

    ignored = ignorelist.load_ignored()
    formulae_to_upgrade = [n for n in outdated_formula_names if n not in ignored["formulae"]]
    casks_to_upgrade = [n for n in outdated_cask_names if n not in ignored["casks"]]
    skipped_formulae = [n for n in outdated_formula_names if n in ignored["formulae"]]
    skipped_casks = [n for n in outdated_cask_names if n in ignored["casks"]]

    print("→ brew upgrade")
    upgrade_parts = []
    if formulae_to_upgrade:
        upgrade_parts.append(_run("upgrade", "--formula", *formulae_to_upgrade))
    if casks_to_upgrade:
        upgrade_parts.append(_run("upgrade", "--cask", *casks_to_upgrade))
    upgrade_output = "\n".join(part for part in upgrade_parts if part) or "Nothing to upgrade."

    print("→ brew cleanup")
    cleanup_output = _run("cleanup")

    print("→ brew doctor")
    doctor_output, doctor_exit = _run_with_exit("doctor")

    print("→ brew missing")
    missing_output = _run("missing")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = (
        f"Homebrew maintenance report - {timestamp}\n\n"
        f"== brew update ==\n{update_output}\n\n"
        f"== brew outdated — Formulae (before upgrade) ==\n{outdated_formula_output}\n\n"
        f"== brew outdated — Casks (before upgrade, --greedy-latest) ==\n{outdated_cask_output}\n\n"
        f"== brew upgrade ==\n{upgrade_output}\n\n"
        f"== Skipped (excluded via 'brew-automator settings') ==\n"
        f"Formulae: {', '.join(skipped_formulae) or 'none'}\n"
        f"Casks: {', '.join(skipped_casks) or 'none'}\n\n"
        f"== brew cleanup ==\n{cleanup_output}\n\n"
        f"== brew doctor ==\n{doctor_output}\n\n"
        f"== brew missing ==\n{missing_output}\n"
    )

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report)

    has_problem = doctor_exit != 0 or bool(missing_output)
    log(f"Finished brew maintenance run (problem={has_problem})")
    print(f"→ Done ({'problem detected' if has_problem else 'all OK'})")

    outdated_summary = "\n".join(
        part for part in (outdated_formula_output, outdated_cask_output) if part
    )

    return {
        "report": report,
        "outdated": outdated_summary,
        "has_problem": has_problem,
        "doctor_output": doctor_output,
        "missing_output": missing_output,
    }


def notify_local(summary: str, title: str = "🍺 Homebrew"):
    """Show a macOS notification via osascript. Quotes/backslashes are escaped
    since `summary` is interpolated into an AppleScript string literal.
    """
    escaped_summary = summary.replace("\\", "\\\\").replace('"', '\\"')
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(
        [
            "osascript",
            "-e",
            f'display notification "{escaped_summary}" with title "{escaped_title}"',
        ]
    )
