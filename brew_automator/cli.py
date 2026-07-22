"""Command-line entry point for brew-automator (init/run/schedule subcommands)."""

import argparse
import sys
from datetime import datetime

from brew_automator import config, mailer, maintenance, scheduler, state


def cmd_init(_args):
    """Handler for `brew-automator init`."""
    config.run_init()


def cmd_run(_args):
    """Handler for `brew-automator run`: run maintenance, email the report,
    and show a local notification.
    """
    try:
        cfg = config.load_config()
    except (FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    result = maintenance.run_maintenance()
    previous_state = state.load_state()

    date_str = datetime.now().strftime("%Y-%m-%d")
    warning_key = None
    skip_email = False

    if result["has_problem"]:
        subject = f"⚠️ Homebrew Warning - {date_str}"
        warning_key = state.warning_signature(result["doctor_output"], result["missing_output"])
        if previous_state.get("last_warning_key") == warning_key:
            skip_email = True
    else:
        subject = f"🍺 Homebrew OK - {date_str}"

    if skip_email:
        maintenance.log("Warning unchanged since last run - skipping email")
    else:
        try:
            mailer.send_report(cfg, subject, result["report"])
        except Exception as e:
            print(f"Failed to send email: {e}", file=sys.stderr)
            sys.exit(1)

    state.save_state({"last_warning_key": warning_key, "last_run": date_str})

    summary = result["outdated"].replace("\n", ", ").strip(", ") or "Nothing to update"
    maintenance.notify_local(summary)


def cmd_schedule_install(_args):
    """Handler for `brew-automator schedule install`."""
    scheduler.install_schedule()


def cmd_schedule_remove(_args):
    """Handler for `brew-automator schedule remove`."""
    scheduler.remove_schedule()


def cmd_schedule_status(_args):
    """Handler for `brew-automator schedule status`."""
    scheduler.show_status()


def main():
    """Parse CLI arguments and dispatch to the matching subcommand handler."""
    parser = argparse.ArgumentParser(prog="brew-automator", description="Homebrew maintenance automation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Interactively set up SMTP config")
    init_parser.set_defaults(func=cmd_init)

    run_parser = subparsers.add_parser("run", help="Run brew maintenance and send a report")
    run_parser.set_defaults(func=cmd_run)

    schedule_parser = subparsers.add_parser("schedule", help="Manage the launchd schedule for automatic runs")
    schedule_subparsers = schedule_parser.add_subparsers(dest="schedule_command", required=True)

    schedule_install_parser = schedule_subparsers.add_parser(
        "install", help="Interactively pick days/times and install the schedule"
    )
    schedule_install_parser.set_defaults(func=cmd_schedule_install)

    schedule_remove_parser = schedule_subparsers.add_parser("remove", help="Remove the installed schedule")
    schedule_remove_parser.set_defaults(func=cmd_schedule_remove)

    schedule_status_parser = schedule_subparsers.add_parser(
        "status", help="Show whether the schedule is installed and loaded"
    )
    schedule_status_parser.set_defaults(func=cmd_schedule_status)

    args = parser.parse_args()
    try:
        args.func(args)
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
