"""`brew-automator status`: one-screen overview of the last run, the schedule,
configured notification channels and excluded packages."""

from datetime import datetime

from brew_automator import config, history, ignorelist, scheduler


def _channels() -> str:
    if not config.config_exists():
        return "local notification only (run 'brew-automator init' to add email/webhook)"
    try:
        cfg = config.load_config()
    except ValueError as e:
        return f"config error - {e}"
    channels = []
    if config.smtp_enabled(cfg):
        channels.append(f"email -> {cfg['MAIL_TO']}")
    if config.webhook_enabled(cfg):
        channels.append(f"webhook ({cfg['WEBHOOK_TYPE']})")
    channels.append("local notification")
    return ", ".join(channels)


def _schedule(now: datetime) -> str:
    entries = scheduler.read_entries()
    if not entries:
        return "not installed (run 'brew-automator schedule install')"
    times = ", ".join(
        f"{scheduler.WEEKDAYS[wd][:3]} {hour:02d}:{minute:02d}" for wd, hour, minute in entries
    )
    loaded = "loaded" if scheduler.is_loaded() else "NOT loaded - reinstall to fix"
    line = f"{times} ({loaded})"
    upcoming = scheduler.next_run(entries, now)
    if upcoming:
        line += f"\n  Next run:       {upcoming.strftime('%a %Y-%m-%d %H:%M')}"
    return line


def show_status(now: datetime = None):
    """Entry point for `brew-automator status`."""
    now = now or datetime.now()

    last = history.last_run()
    if last:
        last_line = history.format_entry(last).replace("\n    ", "\n                  ")
    else:
        last_line = "never (no history yet)"

    ignored = ignorelist.load_ignored()
    excluded = ignored["formulae"] + ignored["casks"]

    print(f"Last run:         {last_line}")
    print(f"Schedule:         {_schedule(now)}")
    print(f"Notifications:    {_channels()}")
    print(f"Excluded:         {', '.join(excluded) if excluded else 'none'}")
