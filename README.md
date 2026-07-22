# brew-automator

A CLI tool for automated Homebrew maintenance (`update`, `outdated`, `upgrade`, `cleanup`, `doctor`, `missing`) that sends an email report via SMTP after every run (subject line differs depending on whether everything is OK or a problem was found), plus a local macOS notification.

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

## Running manually

```
brew-automator run
```

(or `./bin/brew-automator run` if running from the repo instead of a Homebrew install)

The report is written to `~/.config/brew-automator/report.txt`, and the run log to `~/.config/brew-automator/logs/brew-maintenance.log`.

## Scheduled runs (launchd)

Create `~/Library/LaunchAgents/com.brewautomator.maintenance.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.brewautomator.maintenance</string>

    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/brew-automator</string>
        <string>run</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>

    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Weekday</key>
            <integer>0</integer>
            <key>Hour</key>
            <integer>20</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>3</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
    </array>

    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/.config/brew-automator/logs/launchd.out.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/.config/brew-automator/logs/launchd.err.log</string>
</dict>
</plist>
```

`Weekday`: 0 = Sunday, 1 = Monday, ... 6 = Saturday. Adjust the schedule and replace `YOUR_USERNAME` to taste.

The `EnvironmentVariables`/`PATH` entry matters: launchd runs jobs with a minimal `PATH` that doesn't include Homebrew's bin directories, which otherwise breaks `brew` discovery and makes `brew doctor` report bogus PATH warnings.

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

- State file to deduplicate repeated warnings
