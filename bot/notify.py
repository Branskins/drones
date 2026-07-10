"""Email alerting via Gmail SMTP (app password in SMTP_APP_PASSWORD)."""

import os
import smtplib
from email.message import EmailMessage

DEFAULT_RECIPIENT = 'andresjelizondo.btc@gmail.com'


def configured() -> bool:
    return bool(os.environ.get('SMTP_APP_PASSWORD'))


def send(subject: str, body: str) -> bool:
    """Send an alert email. Returns False (without raising) when unconfigured
    or delivery fails — alerting must never crash the trading cycle."""
    if not configured():
        return False
    recipient = os.environ.get('ALERT_EMAIL', DEFAULT_RECIPIENT)
    sender = os.environ.get('SMTP_SENDER', recipient)
    msg = EmailMessage()
    msg['Subject'] = f'[drones-bot] {subject}'
    msg['From'] = sender
    msg['To'] = recipient
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as smtp:
            smtp.login(sender, os.environ['SMTP_APP_PASSWORD'])
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f'email delivery failed: {exc}')
        return False
