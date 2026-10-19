"""Persistence for user accounts, backed by SQLite.

Each user is stored with fields: user_id, email, hashed_password, full_name, is_active, created_at, updated_at.
The table has a unique constraint on email.

Connections are per-thread: sqlite3 objects may not be shared between
threads, and the sync endpoints run in FastAPI's threadpool. WAL mode plus a
busy timeout means readers do not block the writer, and concurrent writers wait
rather than raising "database is locked".
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models.user import UserInDB, UserPublic

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORE_DIR = BACKEND_DIR / "data"
DB_FILENAME = "users.db"
DB_PATH_ENV = "USER_DB_PATH"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    email        TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name    TEXT NOT NULL,
    is_active    INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def default_db_path() -> Path:
    """Where the database lives unless the operator says otherwise.

    ``USER_DB_PATH`` points the store at a mounted volume, which is what
    makes the data survive a redeploy on a platform with an ephemeral
    filesystem.
    """
    from .database import configured_path
    return configured_path(DEFAULT_STORE_DIR / DB_FILENAME, DB_PATH_ENV)


class UserNotFound(LookupError):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"User '{user_id}' was not found.")
        self.user_id = user_id


class UserStore:
    """User persistence on SQLite.

    The database is created and migrated on first use, so a fresh checkout works
    with no setup step.
    """

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

    # ------------------------------------------------------------------ #
    # connection handling
    # ------------------------------------------------------------------ #

    def _connect(self) -> sqlite3.Connection:
        """Return this thread's connection, opening it on first use."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self.db_path,
                isolation_level=None,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def close(self) -> None:
        """Close this thread's connection, if open."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ------------------------------------------------------------------ #
    # reads
    # ------------------------------------------------------------------ #

    def get(self, user_id: str) -> UserInDB:
        """Get a user by user_id."""
        row = self._connect().execute(
            "SELECT user_id, email, hashed_password, full_name, is_active, created_at, updated_at "
            "FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise UserNotFound(user_id)
        return UserInDB(
            user_id=row["user_id"],
            email=row["email"],
            hashed_password=row["hashed_password"],
            full_name=row["full_name"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_by_email(self, email: str) -> Optional[UserInDB]:
        """Get a user by email, or None if not found."""
        row = self._connect().execute(
            "SELECT user_id, email, hashed_password, full_name, is_active, created_at, updated_at "
            "FROM users WHERE email = ?", (email,)
        ).fetchone()
        if row is None:
            return None
        return UserInDB(
            user_id=row["user_id"],
            email=row["email"],
            hashed_password=row["hashed_password"],
            full_name=row["full_name"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def exists(self, user_id: str) -> bool:
        row = self._connect().execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row is not None

    def exists_by_email(self, email: str) -> bool:
        row = self._connect().execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------ #
    # writes
    # ------------------------------------------------------------------ #

    def create(self, user: UserInDB) -> UserInDB:
        """Create a new user. The user_id must be unique."""
        if self.exists(user.user_id):
            # In practice, we should generate a unique user_id, but we assume the caller does.
            raise ValueError(f"User with user_id '{user.user_id}' already exists.")
        now = _now()
        self._connect().execute(
            "INSERT INTO users "
            "(user_id, email, hashed_password, full_name, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user.user_id,
                user.email,
                user.hashed_password,
                user.full_name,
                int(user.is_active),
                now,
                now,
            ),
        )
        return user

    def update(self, user: UserInDB) -> UserInDB:
        """Update an existing user. The user_id must exist."""
        if not self.exists(user.user_id):
            raise UserNotFound(user.user_id)
        now = _now()
        self._connect().execute(
            "UPDATE users SET "
            "email = ?, hashed_password = ?, full_name = ?, is_active = ?, updated_at = ? "
            "WHERE user_id = ?",
            (
                user.email,
                user.hashed_password,
                user.full_name,
                int(user.is_active),
                now,
                user.user_id,
            ),
        )
        return user

    def delete(self, user_id: str) -> None:
        cursor = self._connect().execute(
            "DELETE FROM users WHERE user_id = ?", (user_id,)
        )
        if cursor.rowcount == 0:
            raise UserNotFound(user_id)


_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _store
    if _store is None:
        _store = UserStore()
    return _store


def reset_user_store(location: Path | str | None = None) -> UserStore:
    """Swap the store implementation; used by tests."""
    global _store
    _store = UserStore(location)
    return _store


__all__ = [
    "UserStore",
    "UserNotFound",
    "get_user_store",
    "reset_user_store",
    "default_db_path",
    "DEFAULT_STORE_DIR",
    "DB_FILENAME",
    "DB_PATH_ENV",
]