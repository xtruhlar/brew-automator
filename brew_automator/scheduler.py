"""Interactively create and manage the launchd schedule for automatic runs.

Generates a LaunchAgent plist that runs `brew-automator run` on the
days/times the user picks, and loads/unloads it via launchctl.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_LABEL = "com.brewautomator.maintenance"
PLIST_FILE = LAUNCH_AGENTS_DIR / f"{PLIST_LABEL}.plist"
LOG_DIR = Path.home() / ".config" / "brew-automator" / "logs"

WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# launchd's default PATH doesn't include Homebrew's bin dirs, which breaks
# brew discovery and makes `brew doctor` report bogus PATH warnings.
LAUNCHD_PATH = "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin"


def _find_brew_automator() -> str:
    """Locate the running brew-automator executable to reference in the plist."""
    exe = shutil.which("brew-automator")
    if exe:
        return exe
    return os.path.realpath(sys.argv[0])


def _prompt_entries() -> list:
    """Ask the user for one or more (weekday, hour, minute) schedule entries."""
    print("Let's set up when brew-automator should run automatically.\n")
    entries = []

    while True:
        print("Days: " + ", ".join(f"{i}={name}" for i, name in enumerate(WEEKDAYS)))
        day_input = input("Weekday number (0-6): ").strip()
        if not day_input.isdigit() or not (0 <= int(day_input) <= 6):
            print("Invalid weekday, try again.\n")
            continue
        weekday = int(day_input)

        time_input = input("Time (HH:MM, 24h): ").strip()
        try:
            hour_str, minute_str = time_input.split(":")
            hour, minute = int(hour_str), int(minute_str)
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except ValueError:
            print("Invalid time, try again.\n")
            continue

        entries.append((weekday, hour, minute))
        print(f"Added: {WEEKDAYS[weekday]} at {hour:02d}:{minute:02d}\n")

        again = input("Add another day/time? [y/N]: ").strip().lower()
        if again != "y":
            break

    return entries


def _build_plist(entries: list, brew_automator_path: str) -> str:
    intervals = "\n".join(
        f"""        <dict>
            <key>Weekday</key>
            <integer>{weekday}</integer>
            <key>Hour</key>
            <integer>{hour}</integer>
            <key>Minute</key>
            <integer>{minute}</integer>
        </dict>"""
        for weekday, hour, minute in entries
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{brew_automator_path}</string>
        <string>run</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{LAUNCHD_PATH}</string>
    </dict>

    <key>StartCalendarInterval</key>
    <array>
{intervals}
    </array>

    <key>StandardOutPath</key>
    <string>{LOG_DIR / "launchd.out.log"}</string>

    <key>StandardErrorPath</key>
    <string>{LOG_DIR / "launchd.err.log"}</string>
</dict>
</plist>
"""


def install_schedule():
    """Prompt for a schedule, write the plist, and load it via launchctl."""
    entries = _prompt_entries()
    brew_automator_path = _find_brew_automator()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    if PLIST_FILE.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_FILE)], capture_output=True)

    PLIST_FILE.write_text(_build_plist(entries, brew_automator_path))
    subprocess.run(["launchctl", "load", str(PLIST_FILE)], check=True)

    print(f"\nInstalled schedule ({PLIST_FILE}):")
    for weekday, hour, minute in entries:
        print(f"  - {WEEKDAYS[weekday]} at {hour:02d}:{minute:02d}")


def remove_schedule():
    """Unload and delete the plist, if present."""
    if not PLIST_FILE.exists():
        print("No schedule is installed.")
        return

    subprocess.run(["launchctl", "unload", str(PLIST_FILE)], capture_output=True)
    PLIST_FILE.unlink()
    print(f"Removed schedule ({PLIST_FILE}).")


def show_status():
    """Print whether the schedule is installed and currently loaded."""
    if not PLIST_FILE.exists():
        print("No schedule is installed. Run 'brew-automator schedule install' to set one up.")
        return

    result = subprocess.run(
        ["launchctl", "list", PLIST_LABEL], capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"Schedule is installed and loaded ({PLIST_FILE}).")
        print(result.stdout.strip())
    else:
        print(
            f"Plist exists at {PLIST_FILE} but isn't loaded. "
            "Run 'brew-automator schedule install' again to reload it."
        )
