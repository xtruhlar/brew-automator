# brew-automator

[![CI](https://github.com/xtruhlar/brew-automator/actions/workflows/ci.yml/badge.svg)](https://github.com/xtruhlar/brew-automator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A CLI tool for automated Homebrew maintenance (`update`, `outdated`, `upgrade`, `cleanup`, `doctor`, `missing`) that sends an email report via SMTP after every run (subject line differs depending on whether everything is OK or a problem was found), plus a local macOS notification.

## Requirements

- macOS (uses `launchd` for scheduling)
- [terminal-notifier](https://github.com/julienXX/terminal-notifier) for notifications with a custom icon (installed automatically as a Homebrew dependency; falls back to plain `osascript` notifications if it's missing)
- Python 3.9+ (standard library only, no external dependencies)
- [Homebrew](https://brew.sh)
- An SMTP account to send reports from (any provider) — optional, see [Setup](#setup)

## Installation

```
brew tap xtruhlar/brew-automator
brew install brew-automator
```

Requires Python 3 (no external dependencies, standard library only).

Alternatively, run it directly from the repo without installing:

```
./bin/brew-automator init
```

## Setup

```
brew-automator init
```

Interactively asks for your SMTP credentials (host, port, user, password, destination address) and stores them in `~/.config/brew-automator/config.env` (chmod 600). This file is never published or committed — it lives outside the repository.

This step is optional. Without it, `brew-automator run` still runs the full maintenance routine and shows a macOS notification — it just skips the email step (and says so).

## Running manually

```
brew-automator run
```

(or `./bin/brew-automator run` if running from the repo instead of a Homebrew install)

The report is written to `~/.config/brew-automator/report.txt`, and the run log to `~/.config/brew-automator/logs/brew-maintenance.log`.

## Scheduled runs (launchd)

```
brew-automator schedule install
```

Interactively pick one or more weekdays and times, then it generates and loads a launchd
LaunchAgent (`~/Library/LaunchAgents/com.brewautomator.maintenance.plist`) that runs
`brew-automator run` on that schedule. Re-running `install` replaces the existing schedule.

```
brew-automator schedule status   # check whether it's installed and loaded
brew-automator schedule remove   # unload and delete it
```

Under the hood this handles the two gotchas that otherwise bite you with a hand-written
plist: pointing `ProgramArguments` at the actual installed binary, and setting `PATH` in
`EnvironmentVariables` (launchd's default `PATH` doesn't include Homebrew's bin
directories, which breaks `brew` discovery and makes `brew doctor` report bogus PATH
warnings).

You can still trigger a scheduled run manually without waiting for its time:
```
launchctl start com.brewautomator.maintenance
```

## Logs

- `~/.config/brew-automator/logs/brew-maintenance.log` — per-run progress log (internal logging)
- `~/.config/brew-automator/logs/launchd.out.log` / `launchd.err.log` — launchd stdout/stderr (e.g. startup errors)
- `~/.config/brew-automator/report.txt` — the most recently generated report
- `~/.config/brew-automator/state.json` — signature of the last reported warning (see below)

## Development

```
python3 -m unittest discover -s tests -v
```

Tests run in CI on every push/PR via GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)).

## Warning deduplication

Every run sends a `🍺 Homebrew OK` email when there's no problem, so you always know the
job actually ran. When `brew doctor` or `brew missing` reports a problem, the warning
content is hashed and compared against `state.json`. If it's the same problem as last
time, the `⚠️ Homebrew Warning` email is skipped (logged instead) so you don't get
re-alerted for something you're already aware of — a *new or changed* warning still
emails you.
