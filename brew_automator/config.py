"""Load and interactively create the notification configuration (SMTP and/or webhook).

The config file lives outside the repository (in the user's home
directory), so credentials never end up in version control.
"""

import getpass
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "brew-automator"
CONFIG_FILE = CONFIG_DIR / "config.env"

SMTP_KEYS = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"]
# Kept for backwards compatibility; SMTP is now one of several optional channels.
REQUIRED_KEYS = SMTP_KEYS

WEBHOOK_TYPES = ["ntfy", "slack", "discord", "json"]


def config_exists() -> bool:
    """Return True if a config file has already been created."""
    return CONFIG_FILE.exists()


def smtp_enabled(config: dict) -> bool:
    return all(config.get(k) for k in SMTP_KEYS)


def webhook_enabled(config: dict) -> bool:
    return bool(config.get("WEBHOOK_URL"))


def infer_webhook_type(url: str) -> str:
    """Guess the webhook flavour from its URL; unknown URLs get a generic JSON POST."""
    if "hooks.slack.com" in url:
        return "slack"
    if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        return "discord"
    if "ntfy" in url:
        return "ntfy"
    return "json"


def load_config() -> dict:
    """Read config.env into a dict and validate it.

    At least one channel must be configured: SMTP (all of SMTP_KEYS) and/or a
    webhook (WEBHOOK_URL, optional WEBHOOK_TYPE - inferred from the URL when
    missing). A partially filled-in SMTP block is an error, since it means
    setup was attempted and something is actually broken.
    """
    if not config_exists():
        raise FileNotFoundError(
            f"Config not found at {CONFIG_FILE}. Run 'brew-automator init' first."
        )

    config = {}
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        config[key.strip()] = value.strip().strip('"').strip("'")

    present_smtp = [k for k in SMTP_KEYS if k in config]
    if present_smtp or not webhook_enabled(config):
        missing = [k for k in SMTP_KEYS if k not in config]
        if missing:
            raise ValueError(f"Config at {CONFIG_FILE} is missing keys: {', '.join(missing)}")

    if webhook_enabled(config):
        webhook_type = config.get("WEBHOOK_TYPE") or infer_webhook_type(config["WEBHOOK_URL"])
        if webhook_type not in WEBHOOK_TYPES:
            raise ValueError(
                f"Config at {CONFIG_FILE} has unknown WEBHOOK_TYPE '{webhook_type}' "
                f"(expected one of: {', '.join(WEBHOOK_TYPES)})"
            )
        config["WEBHOOK_TYPE"] = webhook_type

    return config


def _ask_yes_no(question: str, default: bool) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    answer = input(question + suffix).strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def run_init():
    """Prompt for SMTP and/or webhook settings and write them to CONFIG_FILE (chmod 600)."""
    print(f"Let's set up where reports are sent. Settings are stored locally in {CONFIG_FILE}\n")

    lines = []
    if _ask_yes_no("Send reports by email (SMTP)?", default=True):
        smtp_host = input("SMTP host (e.g. smtp.domain.com): ").strip()
        smtp_port = input("SMTP port (e.g. 465 for SSL, 587 for STARTTLS): ").strip()
        smtp_user = input("SMTP user (the sending mailbox): ").strip()
        smtp_password = getpass.getpass("SMTP password (hidden): ").strip()
        mail_to = input("Address to send reports to: ").strip()
        lines += [
            f"SMTP_HOST={smtp_host}",
            f"SMTP_PORT={smtp_port}",
            f"SMTP_USER={smtp_user}",
            f"SMTP_PASSWORD={smtp_password}",
            f"MAIL_TO={mail_to}",
        ]
        print()

    if _ask_yes_no("Send notifications to a webhook (ntfy, Slack, Discord, ...)?", default=False):
        url = input("Webhook URL (e.g. https://ntfy.sh/my-secret-topic): ").strip()
        guessed = infer_webhook_type(url)
        webhook_type = (
            input(f"Webhook type ({'/'.join(WEBHOOK_TYPES)}) [{guessed}]: ").strip().lower() or guessed
        )
        if webhook_type not in WEBHOOK_TYPES:
            print(f"Unknown type '{webhook_type}', using '{guessed}'.")
            webhook_type = guessed
        lines += [f"WEBHOOK_URL={url}", f"WEBHOOK_TYPE={webhook_type}"]
        print()

    if not lines:
        print("Nothing configured - 'brew-automator run' will only show a local notification.")
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Create with 0600 from the start (instead of chmod after write_text) so the
    # password is never briefly readable under the umask's default permissions.
    fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Saved to {CONFIG_FILE} (chmod 600).")
