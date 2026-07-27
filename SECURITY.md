# Security Policy

## Supported Versions

`brew-automator` follows a single rolling release — only the latest version on the
[Releases page](https://github.com/xtruhlar/brew-automator/releases) is supported.
Please upgrade (`brew upgrade brew-automator`) before reporting an issue to confirm
it isn't already fixed.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's private vulnerability reporting:
[github.com/xtruhlar/brew-automator/security/advisories/new](https://github.com/xtruhlar/brew-automator/security/advisories/new)

This lets you report a vulnerability privately so it can be fixed before public
disclosure. I'll do my best to respond within a few days and to ship a fix promptly
once a report is confirmed.

## Scope

Relevant reports include (but aren't limited to):
- Credential handling issues in `config.env` (SMTP credentials)
- Command injection via `subprocess` calls to `brew`, `osascript`, or `launchctl`
- Anything that could let a local, unprivileged process read or tamper with
  `~/.config/brew-automator/` contents in an unexpected way

`brew-automator` is a local, single-user CLI tool with no network-facing service
component, so most reports will be about local file/permission handling or the
generated `launchd` plist rather than remote attack surface.
