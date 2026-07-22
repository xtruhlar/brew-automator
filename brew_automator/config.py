"""Load and interactively create the SMTP configuration.

The config file lives outside the repository (in the user's home
directory), so credentials never end up in version control.
"""

import getpass
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "brew-automator"
CONFIG_FILE = CONFIG_DIR / "config.env"

REQUIRED_KEYS = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"]


def config_exists() -> bool:
    """Return True if a config file has already been created."""
    return CONFIG_FILE.exists()


def load_config() -> dict:
    """Read config.env into a dict, validating that all required keys are present."""
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

    missing = [k for k in REQUIRED_KEYS if k not in config]
    if missing:
        raise ValueError(f"Config at {CONFIG_FILE} is missing keys: {', '.join(missing)}")

    return config


def run_init():
    """Prompt the user for SMTP credentials and write them to CONFIG_FILE (chmod 600)."""
    print(f"Let's set up your SMTP credentials. They will be stored locally in {CONFIG_FILE}\n")

    smtp_host = input("SMTP host (e.g. smtp.domain.com): ").strip()
    smtp_port = input("SMTP port (e.g. 465 for SSL, 587 for STARTTLS): ").strip()
    smtp_user = input("SMTP user (the sending mailbox): ").strip()
    smtp_password = getpass.getpass("SMTP password (hidden): ").strip()
    mail_to = input("Address to send reports to: ").strip()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    contents = (
        f"SMTP_HOST={smtp_host}\n"
        f"SMTP_PORT={smtp_port}\n"
        f"SMTP_USER={smtp_user}\n"
        f"SMTP_PASSWORD={smtp_password}\n"
        f"MAIL_TO={mail_to}\n"
    )
    # Create with 0600 from the start (instead of chmod after write_text) so the
    # password is never briefly readable under the umask's default permissions.
    fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(contents)

    print(f"\nSaved to {CONFIG_FILE} (chmod 600).")
