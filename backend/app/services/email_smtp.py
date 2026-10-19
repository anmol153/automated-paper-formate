"""Optional SMTP email sender for notifications.

This module can be configured via environment variables to send actual emails
via SMTP instead of (or in addition to) the file-based logger.

Environment variables (all optional):
  SMTP_HOST      – SMTP server hostname (e.g. "smtp.sendgrid.net")
  SMTP_PORT      – SMTP server port (default 587)
  SMTP_USER      – Username for authentication
  SMTP_PASSWORD  – Password or API key for authentication
  SMTP_FROM      – Default "from" address for outgoing emails

If none of these are set, the sender falls back to the file-based logger
defined in ``backend/app/services/email.py`` so that existing behaviour is
preserved without any configuration.
"""

from __future__ import annotations

import os
import smtplib
import email.message
from datetime import datetime
from typing import Optional

from app.models.notification import Notification, NotificationType
from app.services.email import send_email as log_email


# ------------------------------------------------------------
# Configuration helpers
# ------------------------------------------------------------

def _get_env(var: str, default: str = "") -> str:
    """Read an environment variable, returning *default* when empty."""
    return os.environ.get(var, default)


def _is_configured() -> bool:
    """Return True when at least an SMTP host is set."""
    return bool(_get_env("SMTP_HOST"))


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def send(notification: Notification) -> bool:
    """Send a notification.

    If SMTP is configured, an actual email is dispatched via ``smtplib``.
    Otherwise the file-based logger from ``backend/app/services/email.py``
    is used so that no behaviour change occurs for unconfigured instances.
    """
    if _is_configured():
        return _send_via_smtp(notification)
    # Fall back to file logging
    return log_email(notification)


def _send_via_smtp(notification: Notification) -> bool:
    """Send a single notification via SMTP."""
    try:
        host = _get_env("SMTP_HOST")
        port = int(_get_env("SMTP_PORT", "587"))
        user = _get_env("SMTP_USER")
        password = _get_env("SMTP_PASSWORD")
        default_from = _get_env("SMTP_FROM", user or "no-reply@example.com")

        # Build a simple plain‑text email
        msg = email.message.EmailMessage()
        msg["Subject"] = notification.title
        msg["From"] = default_from
        msg["To"] = notification.email or ""
        msg.set_content(
            f"""
Notification Type: {notification.type}

Title: {notification.title}

Body: {notification.body}

Related ID: {notification.related_id or 'N/A'}

Sent at: {datetime.utcnow().isoformat()}

Notification ID: {notification.notification_id}
"""
        )

        if not user or not password:
            raise ValueError("SMTP_USER and SMTP_PASSWORD must be set when SMTP_HOST is provided.")

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

        return True
    except Exception:
        # If anything goes wrong, fall back to file logging so we don't lose the notification
        return log_email(notification)
