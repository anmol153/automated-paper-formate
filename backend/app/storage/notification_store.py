"""Persistence for notifications (review assignments, discussion mentions, etc.).

Notifications are created by the workflow when an event occurs that a user
should be aware of: a reviewer is assigned, an issue is assigned, a discussion
message is posted, etc. They are read in the UI via the notification endpoint.
"""

from __future__ import annotations

import os
import sqlite3
from .postgres_compat import connect as connect_database
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.models.notification import Notification, NotificationType
from app.services.email_smtp import send as send_email

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORE_DIR = BASE_DIR / "data"
DB_FILENAME = "notifications.db"
DB_PATH_ENV = "NOTIFICATION_DB_PATH"


class NotificationNotFound(LookupError):
    def __init__(self, notification_id: str) -> None:
        super().__init__(f"Notification '{notification_id}' was not found.")
        self.notification_id = notification_id


SCHEMA = """
CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    related_id TEXT,
    read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    read_at TEXT,
    email TEXT
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications (user_id, read, created_at);
"""


def default_db_path() -> Path:
    from .database import configured_path
    return configured_path(DEFAULT_STORE_DIR / DB_FILENAME, DB_PATH_ENV)


class NotificationStore:
    """SQLite-backed store for Notifications."""

    def __init__(self, location: Path | str | None = None) -> None:
        if location is None:
            self.db_path = default_db_path()
        else:
            path = Path(location).expanduser()
            if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                self.db_path = path
            else:
                self.db_path = path / DB_FILENAME
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        from .database import initialize_if_empty
        initialize_if_empty(self.db_path)
        self.directory = self.db_path.parent
        self._local = threading.local()
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = connect_database(self.db_path, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def create(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        body: str,
        related_id: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Notification:
        notification_id = f"notif-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        self._connect().execute(
            "INSERT INTO notifications "
            "(notification_id, user_id, type, title, body, related_id, read, created_at, email) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (notification_id, user_id, notification_type.value, title, body, related_id, 0, now, email),
        )
        notification = Notification(
            notification_id=notification_id,
            user_id=user_id,
            type=notification_type,
            title=title,
            body=body,
            related_id=related_id,
            read=False,
            created_at=now,
            email=email,
        )
        # Attempt to send email if an email address is provided
        if email:
            try:
                send_email(notification)
            except Exception:
                # Don't fail notification creation if email sending fails
                pass
        return notification

    def list_by_user(self, user_id: str, unread_only: bool = False) -> List[Notification]:
        return list(self.iter_by_user(user_id, unread_only))

    def iter_by_user(self, user_id: str, unread_only: bool = False, before=None):
        """Stream a recipient's history in bounded chunks, with stable ordering."""
        query = (
            "SELECT notification_id, user_id, type, title, body, related_id, read, created_at "
            "FROM notifications WHERE user_id = ?"
        )
        params = [user_id]
        if unread_only:
            query += " AND read = 0"
        if before:
            query += " AND (created_at < ? OR (created_at = ? AND notification_id < ?))"
            params.extend([before[0], before[0], before[1]])
        query += " ORDER BY created_at DESC, notification_id DESC"
        cursor = self._connect().execute(query, params)
        try:
            while rows := cursor.fetchmany(100):
                for r in rows:
                    yield Notification(
                        notification_id=r["notification_id"],
                        user_id=r["user_id"],
                        type=NotificationType(r["type"]),
                        title=r["title"],
                        body=r["body"],
                        related_id=r["related_id"],
                        read=bool(r["read"]),
                        created_at=r["created_at"],
                    )
        finally:
            cursor.close()

    def mark_read(self, notification_id: str, user_id: str) -> Notification:
        now = datetime.now(timezone.utc).isoformat()
        self._connect().execute(
            "UPDATE notifications SET read = 1, read_at = COALESCE(read_at, ?) WHERE notification_id = ? AND user_id = ?",
            (now, notification_id, user_id),
        )
        row = self._connect().execute(
            "SELECT notification_id, user_id, type, title, body, related_id, read, created_at "
            "FROM notifications WHERE notification_id = ? AND user_id = ?",
            (notification_id, user_id),
        ).fetchone()
        if row is None:
            raise NotificationNotFound(notification_id)
        return Notification(
            notification_id=row["notification_id"],
            user_id=row["user_id"],
            type=NotificationType(row["type"]),
            title=row["title"],
            body=row["body"],
            related_id=row["related_id"],
            read=bool(row["read"]),
            created_at=row["created_at"],
        )

    def mark_all_read(self, user_id: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._connect().execute(
            "UPDATE notifications SET read = 1, read_at = ? WHERE user_id = ? AND read = 0",
            (now, user_id),
        )
        return cur.rowcount or 0

    def count_unread(self, user_id: str) -> int:
        row = self._connect().execute(
            "SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND read = 0",
            (user_id,),
        ).fetchone()
        return int(row["c"]) if row else 0


_store: Optional[NotificationStore] = None


def get_notification_store() -> NotificationStore:
    global _store
    if _store is None:
        _store = NotificationStore()
    return _store


def reset_notification_store(location: Path | str | None = None) -> NotificationStore:
    global _store
    _store = NotificationStore(location)
    return _store


__all__ = [
    "NotificationStore",
    "NotificationNotFound",
    "get_notification_store",
    "reset_notification_store",
    "default_db_path",
    "DEFAULT_STORE_DIR",
    "DB_FILENAME",
    "DB_PATH_ENV",
]
