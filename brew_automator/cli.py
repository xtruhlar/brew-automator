"""Command-line entry point for brew-automator (init/run/schedule subcommands)."""

import argparse
import sys
from datetime import datetime

from brew_automator import __version__, config, mailer, maintenance, scheduler, state


def cmd_init(_args):
    """Handler for `brew-automator init`."""
    config.run_init()


def cmd_run(_args):
    """Handler for `brew-automator run`: run maintenance, email the report if
    SMTP is configured, and always show a local notification.

    SMTP config is optional: if it was never set up (no config.env), this
    runs in local-only mode and just skips the email step. A config.env that
    exists but is malformed is treated as a real error, since that means
    setup was attempted and something is actually broken.
    """
    cfg = None
    if config.config_exists():
        try:
            cfg = config.load_config()
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
    else:
        print(
            "No SMTP config found - running locally only (no email will be sent). "
            "Run 'brew-automator init' to enable email reports.",
            file=sys.stderr,
        )

    result = maintenance.run_maintenance()
    previous_state = state.load_state()

    date_str = datetime.now().strftime("%Y-%m-%d")
    warning_key = None
    skip_reason = None

    if result["has_problem"]:
        subject = f"⚠️ Homebrew Warning - {date_str}"
        warning_key = state.warning_signature(result["doctor_output"], result["missing_output"])
        if previous_state.get("last_warning_key") == warning_key:
            skip_reason = "Warning unchanged since last run - skipping email"
    else:
        subject = f"🍺 Homebrew OK - {date_str}"

    if cfg is None:
        skip_reason = skip_reason or "No SMTP config - skipping email (local-only run)"

    if skip_reason:
        maintenance.log(skip_reason)
        print(f"→ {skip_reason}")
    else:
        print("→ Sending email report")
        try:
            mailer.send_report(cfg, subject, result["report"])
        except Exception as e:
            print(f"Failed to send email: {e}", file=sys.stderr)
            sys.exit(1)

    state.save_state({"last_warning_key": warning_key, "last_run": date_str})

    summary = result["outdated"].replace("\n", ", ").strip(", ") or "Nothing to update"
    maintenance.notify_local(summary)
    print(f"→ Report saved to {maintenance.REPORT_FILE}")


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
    parser.add_argument("--version", action="version", version=f"brew-automator {__version__}")
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
