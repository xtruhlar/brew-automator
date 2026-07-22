"""Send the maintenance report by email over SMTP."""

import smtplib
from email.message import EmailMessage


def send_report(config: dict, subject: str, body: str):
    """Send `body` as a plain-text email using the SMTP settings in `config`.

    Port 465 is treated as implicit TLS (SMTPS); any other port uses
    plaintext + STARTTLS, matching common SMTP provider conventions.
    """
    smtp_host = config["SMTP_HOST"]
    smtp_port = int(config["SMTP_PORT"])
    smtp_user = config["SMTP_USER"]
    smtp_password = config["SMTP_PASSWORD"]
    mail_to = config["MAIL_TO"]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = mail_to
    msg.set_content(body)

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls()
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
