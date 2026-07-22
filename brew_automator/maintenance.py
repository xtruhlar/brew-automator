"""Run the actual Homebrew maintenance steps and build a report.

Also handles local logging (~/.config/brew-automator/logs) and the
macOS notification shown after each run.
"""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

STATE_DIR = Path.home() / ".config" / "brew-automator"
LOG_DIR = STATE_DIR / "logs"
REPORT_FILE = STATE_DIR / "report.txt"
LOG_FILE = LOG_DIR / "brew-maintenance.log"

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
ICON_FILE = PACKAGE_ROOT / "assets" / "beer-icon.png"


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
    """
    log("Starting brew maintenance run")

    update_output = _run("update")
    outdated_output = _run("outdated")
    upgrade_output = _run("upgrade")
    cleanup_output = _run("cleanup")
    doctor_output, doctor_exit = _run_with_exit("doctor")
    missing_output = _run("missing")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = (
        f"Homebrew maintenance report - {timestamp}\n\n"
        f"== brew update ==\n{update_output}\n\n"
        f"== brew outdated (before upgrade) ==\n{outdated_output}\n\n"
        f"== brew upgrade ==\n{upgrade_output}\n\n"
        f"== brew cleanup ==\n{cleanup_output}\n\n"
        f"== brew doctor ==\n{doctor_output}\n\n"
        f"== brew missing ==\n{missing_output}\n"
    )

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report)

    has_problem = doctor_exit != 0 or bool(missing_output)
    log(f"Finished brew maintenance run (problem={has_problem})")

    return {
        "report": report,
        "outdated": outdated_output,
        "has_problem": has_problem,
        "doctor_output": doctor_output,
        "missing_output": missing_output,
    }


def notify_local(summary: str, title: str = "🍺 Homebrew"):
    """Show a macOS notification with a custom beer icon via terminal-notifier,
    falling back to plain osascript (generic icon, no customization) if
    terminal-notifier isn't installed.
    """
    terminal_notifier = shutil.which("terminal-notifier")
    if terminal_notifier and ICON_FILE.exists():
        subprocess.run(
            [
                terminal_notifier,
                "-title", title,
                "-message", summary,
                "-appIcon", str(ICON_FILE),
            ]
        )
        return

    escaped_summary = summary.replace("\\", "\\\\").replace('"', '\\"')
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(
        [
            "osascript",
            "-e",
            f'display notification "{escaped_summary}" with title "{escaped_title}"',
        ]
    )
