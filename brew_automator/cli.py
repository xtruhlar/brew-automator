"""Command-line entry point for brew-automator (init/run subcommands)."""

import argparse
import sys
from datetime import datetime

from brew_automator import config, mailer, maintenance


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

    date_str = datetime.now().strftime("%Y-%m-%d")
    if result["has_problem"]:
        subject = f"⚠️ Homebrew Warning - {date_str}"
    else:
        subject = f"🍺 Homebrew OK - {date_str}"

    try:
        mailer.send_report(cfg, subject, result["report"])
    except Exception as e:
        print(f"Failed to send email: {e}", file=sys.stderr)
        sys.exit(1)

    summary = result["outdated"].replace("\n", ", ").strip(", ") or "Nothing to update"
    maintenance.notify_local(summary)


def main():
    """Parse CLI arguments and dispatch to the matching subcommand handler."""
    parser = argparse.ArgumentParser(prog="brew-automator", description="Homebrew maintenance automation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Interactively set up SMTP config")
    init_parser.set_defaults(func=cmd_init)

    run_parser = subparsers.add_parser("run", help="Run brew maintenance and send a report")
    run_parser.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
