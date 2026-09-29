"""Command-line entry point for brew-automator (init/run/history/status/settings/schedule)."""

import argparse
import sys
from datetime import datetime

from brew_automator import (
    __version__,
    config,
    history,
    mailer,
    maintenance,
    scheduler,
    settings_ui,
    state,
    status,
    webhook,
)


def cmd_init(_args):
    """Handler for `brew-automator init`."""
    config.run_init()


def _print_report(report: str, name: str):
    print(f"________{name}__________")
    print(report)
    print("-" * 40)


def cmd_run(args):
    """Handler for `brew-automator run`: run maintenance, send the report to the
    configured channels (email and/or webhook), record it in the history, and
    always show a local notification.

    Config is optional: if it was never set up (no config.env), this runs in
    local-only mode and just skips sending. A config.env that exists but is
    malformed is treated as a real error, since that means setup was attempted
    and something is actually broken.

    --dry-run sends nothing and writes no report/state/history; --no-upgrade
    is a normal run (report, notifications, history) that just doesn't
    upgrade or clean up anything.
    """
    if args.dry_run:
        mode = maintenance.MODE_DRY_RUN
    elif args.no_upgrade:
        mode = maintenance.MODE_NO_UPGRADE
    else:
        mode = maintenance.MODE_NORMAL

    cfg = None
    if mode == maintenance.MODE_DRY_RUN:
        print("Dry run - nothing will be upgraded, cleaned up or sent.", file=sys.stderr)
    elif config.config_exists():
        try:
            cfg = config.load_config()
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
    else:
        print(
            "No config found - running locally only (no email/webhook will be sent). "
            "Run 'brew-automator init' to enable reports.",
            file=sys.stderr,
        )

    result = maintenance.run_maintenance(mode)

    if mode == maintenance.MODE_DRY_RUN:
        _print_report(result["report"], "dry-run report")
        return

    previous_state = state.load_state()
    date_str = datetime.now().strftime("%Y-%m-%d")
    warning_key = None
    skip_reason = None

    if result["has_problem"]:
        subject = f"⚠️ Homebrew Warning - {date_str}"
        failed_names = ",".join(sorted(p["name"] for p in result["failed"]))
        warning_key = state.warning_signature(
            result["doctor_output"], result["missing_output"], failed_names
        )
        if previous_state.get("last_warning_key") == warning_key:
            skip_reason = "Warning unchanged since last run - skipping notifications"
    else:
        subject = f"🍺 Homebrew OK - {date_str}"
    if mode == maintenance.MODE_NO_UPGRADE:
        subject += " (report only)"

    channels = []
    if cfg is not None and config.smtp_enabled(cfg):
        channels.append(("email", lambda: mailer.send_report(cfg, subject, result["report"])))
    if cfg is not None and config.webhook_enabled(cfg):
        channels.append(
            (
                "webhook",
                lambda: webhook.send(
                    cfg, subject, result["summary"], result["report"], result["has_problem"]
                ),
            )
        )
    if not channels:
        skip_reason = skip_reason or "No email/webhook configured - skipping (local-only run)"

    errors = []
    notified = False
    if skip_reason:
        maintenance.log(skip_reason)
        print(f"→ {skip_reason}")
    else:
        for name, send in channels:
            print(f"→ Sending {name} report")
            try:
                send()
                notified = True
            except Exception as e:
                errors.append(f"Failed to send {name}: {e}")

    history.record_run(result, notified)
    # Only remember the warning once it's actually been delivered everywhere,
    # so a failed send is retried on the next run instead of deduplicated away.
    if not errors:
        state.save_state({"last_warning_key": warning_key, "last_run": date_str})

    maintenance.notify_local(result["short_summary"])
    _print_report(result["report"], maintenance.REPORT_FILE.name)

    if errors:
        for error in errors:
            maintenance.log(error)
            print(error, file=sys.stderr)
        sys.exit(1)


def cmd_history(args):
    """Handler for `brew-automator history`."""
    history.show_history(limit=args.limit, package=args.package)


def cmd_status(_args):
    """Handler for `brew-automator status`."""
    status.show_status()


def cmd_settings(_args):
    """Handler for `brew-automator settings`."""
    settings_ui.run_settings()


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

    init_parser = subparsers.add_parser("init", help="Interactively set up email (SMTP) and/or webhook notifications")
    init_parser.set_defaults(func=cmd_init)

    run_parser = subparsers.add_parser("run", help="Run brew maintenance and send a report")
    run_mode = run_parser.add_mutually_exclusive_group()
    run_mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be upgraded/cleaned up without changing anything or sending reports",
    )
    run_mode.add_argument(
        "--no-upgrade",
        action="store_true",
        help="Check and report as usual, but don't upgrade or clean up anything",
    )
    run_parser.set_defaults(func=cmd_run)

    history_parser = subparsers.add_parser("history", help="Show past runs")
    history_parser.add_argument(
        "-n", "--limit", type=int, default=10, help="Number of runs to show (0 = all, default 10)"
    )
    history_parser.add_argument(
        "-p", "--package", help="Only show runs that upgraded, failed or skipped this formula/cask"
    )
    history_parser.set_defaults(func=cmd_history)

    status_parser = subparsers.add_parser(
        "status", help="Show last run, schedule, notification channels and excluded packages"
    )
    status_parser.set_defaults(func=cmd_status)

    settings_parser = subparsers.add_parser(
        "settings", help="Interactively choose formulae/casks to exclude from automatic upgrades"
    )
    settings_parser.set_defaults(func=cmd_settings)

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
