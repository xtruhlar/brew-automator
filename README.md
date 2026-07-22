# brew-automator

A CLI tool for automated Homebrew maintenance (`update`, `outdated`, `upgrade`, `cleanup`, `doctor`, `missing`) that sends an email report via SMTP after every run (subject line differs depending on whether everything is OK or a problem was found), plus a local macOS notification.

## Installation / setup

No Homebrew formula yet (planned) — run it directly via `bin/brew-automator`.

Requires Python 3 (no external dependencies, standard library only).

```
./bin/brew-automator init
```

Interactively asks for your SMTP credentials (host, port, user, password, destination address) and stores them in `~/.config/brew-automator/config.env` (chmod 600). This file is never published or committed — it lives outside the repository.

## Running manually

```
./bin/brew-automator run
```

The report is written to `~/.config/brew-automator/report.txt`, and the run log to `~/.config/brew-automator/logs/brew-maintenance.log`.

## Scheduled runs (launchd)

Schedule: every **Sunday at 20:00** and every **Wednesday at 8:00** (`com.brewautomator.maintenance.plist`), running `bin/brew-automator run`.

**Load (activate) the schedule:**
```
launchctl load ~/Library/LaunchAgents/com.brewautomator.maintenance.plist
```

**Check that it's registered / running:**
```
launchctl list | grep com.brewautomator.maintenance
```

**Unload (deactivate) the schedule:**
```
launchctl unload ~/Library/LaunchAgents/com.brewautomator.maintenance.plist
```

**Trigger it manually via launchd right now (without waiting for the schedule):**
```
launchctl start com.brewautomator.maintenance
```

**Remove it entirely:**
```
launchctl unload ~/Library/LaunchAgents/com.brewautomator.maintenance.plist
rm ~/Library/LaunchAgents/com.brewautomator.maintenance.plist
```

## Logs

- `~/.config/brew-automator/logs/brew-maintenance.log` — per-run progress log (internal logging)
- `~/.config/brew-automator/logs/launchd.out.log` / `launchd.err.log` — launchd stdout/stderr (e.g. startup errors)
- `~/.config/brew-automator/report.txt` — the most recently generated report

## TODO

- Homebrew formula (custom tap) for `brew install`
- State file to deduplicate repeated warnings
