"""Email delivery service for notifications.

This service is responsible for sending actual emails based on notifications
that have an email address in the snowflake pattern.

In production, this would be integrated with an email service like SendGrid,
Postmark, or SMTP. For development, we log to a file.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.notification import Notification, NotificationType

# Directory where email logs will be stored (relative to backend root)
EMAIL_LOG_DIR = Path(os.environ.get(
    "EMAIL_LOG_DIR", str(Path(__file__).resolve().parent.parent.parent / "data" / "email_logs")
))


def send_email(notification: Notification) -> bool:
    """Send an email based on the notification.

    Returns True if the email was sent (or logged), False on failure.

    This implementation logs the email to a file in the data directory.
    """
    try:
        if not notification.email:
            # No email address to send to
            return False

        EMAIL_LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Determine the log file for today
        today = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = EMAIL_LOG_DIR / f"email-{today}.log"

        # Compose a simple email log entry
        timestamp = datetime.utcnow().isoformat()
        log_entry = (
            f"[{timestamp}] To: {notification.email}\n"
            f"Type: {notification.type}\n"
            f"Title: {notification.title}\n"
            f"Body: {notification.body}\n"
            f"Related ID: {notification.related_id or 'N/A'}\n"
            f"Notification ID: {notification.notification_id}\n"
            f"---\n"
        )

        # Append to the log file
        with log_file.open("a", encoding="utf-8") as f:
            f.write(log_entry)

        return True
    except Exception:
        # In a real application, we might want to log this error elsewhere
        # For now, we fail silently to not break the notification creation
        return False


# Optional: a more sophisticated interface for different email backends
class EmailSender:
    """Abstract base class for email senders."""

    def send(self, notification: Notification) -> bool:
        """Send an email for the given notification.
        Returns True on success, False on failure.
        """
        raise NotImplementedError


class LogEmailSender(EmailSender):
    """Email sender that logs to a file (default implementation)."""

    def send(self, notification: Notification) -> bool:
        return send_email(notification)