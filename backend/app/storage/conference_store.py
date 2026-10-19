"""Persistence for conference membership and metadata, backed by SQLite.

Provides CRUD operations for conferences and members, following the same
patterns established by user_store and template_store.

The database schema is created on first use (CREATE TABLE IF NOT EXISTS), so a
fresh checkout works with no setup step beyond running the server.
"""

from __future__ import annotations

import os
import sqlite3
from .postgres_compat import connect as connect_database
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models.conference import Conference, ConferenceMember, ConferenceRole

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORE_DIR = BASE_DIR / "data"
DB_FILENAME = "conferences.db"
DB_PATH_ENV = "CONFERENCE_DB_PATH"


class ConferenceNotFound(LookupError):
    def __init__(self, conference_id: str) -> None:
        super().__init__(f"Conference '{conference_id}' was not found.")
        self.conference_id = conference_id


class ConferenceMemberNotFound(LookupError):
    def __init__(self, user_id: str, conference_id: str) -> None:
        super().__init__(
            f"Member '{user_id}' was not found in conference '{conference_id}'."
        )
        self.user_id = user_id
        self.conference_id = conference_id


SCHEMA = """
CREATE TABLE IF NOT EXISTS conferences (
    conference_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    start_date  TEXT,
    end_date    TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conference_members (
    user_id       TEXT NOT NULL,
    conference_id TEXT NOT NULL,
    role          TEXT NOT NULL,
    joined_at     TEXT NOT NULL,
    PRIMARY KEY (user_id, conference_id)
);

CREATE INDEX IF NOT EXISTS idx_members_conference
    ON conference_members (conference_id, role);
"""


def _default_db_path() -> Path:
    """Return the default database path: ``data/conferences.db`` unless
    ``CONFERENCE_DB_PATH`` is set in the environment.
    """
    from .database import configured_path
    return configured_path(DEFAULT_STORE_DIR / DB_FILENAME, DB_PATH_ENV)


class ConferenceStore:
    """SQLite‑backed store for Conference and ConferenceMember persistence.

    Connections are per‑thread (sqlite3 rule) and WAL mode plus busy timeouts
    prevent the "database is locked" errors seen with concurrent access.
    """

    def __init__(self, location: Path | str | None = None) -> None:
        if location is None:
            self.db_path = _default_db_path()
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
            conn = connect_database(
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
    # Conference reads
    # ------------------------------------------------------------------ #

    def list_conferences(self, query: str | None = None) -> list[Conference]:
        """All conferences, most recently updated first.

        If *query* is provided, only conferences whose name or description
        contains the query string (case‑insensitive) are returned.
        """
        if query:
            like = f"%{query}%"
            rows = self._connect().execute(
                """
                SELECT conference_id, name, description, start_date, end_date,
                       created_at, updated_at FROM conferences
                WHERE LOWER(name) LIKE LOWER(?) OR LOWER(description) LIKE LOWER(?)
                ORDER BY updated_at DESC, created_at DESC, conference_id DESC
                """,
                (like, like),
            ).fetchall()
        else:
            rows = self._connect().execute(
                "SELECT conference_id, name, description, start_date, end_date, "
                "created_at, updated_at FROM conferences "
                "ORDER BY updated_at DESC, created_at DESC, conference_id DESC"
            ).fetchall()
        conferences: list[Conference] = []
        for row in rows:
            conferences.append(
                Conference(
                    conference_id=row["conference_id"],
                    name=row["name"],
                    description=row["description"] or "",
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                )
            )
        return conferences

    def get(self, conference_id: str) -> Conference:
        row = self._connect().execute(
            "SELECT conference_id, name, description, start_date, end_date, "
            "created_at, updated_at FROM conferences WHERE conference_id = ?",
            (conference_id,),
        ).fetchone()
        if row is None:
            raise ConferenceNotFound(conference_id)
        return Conference(
            conference_id=row["conference_id"],
            name=row["name"],
            description=row["description"] or "",
            start_date=row["start_date"],
            end_date=row["end_date"],
        )

    def exists(self, conference_id: str) -> bool:
        row = self._connect().execute(
            "SELECT 1 FROM conferences WHERE conference_id = ?", (conference_id,)
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------ #
    # Membership reads
    # ------------------------------------------------------------------ #

    def list_members(self, conference_id: str) -> list[ConferenceMember]:
        """All members of a conference."""
        rows = self._connect().execute(
            "SELECT user_id, role, joined_at FROM conference_members "
            "WHERE conference_id = ? ORDER BY joined_at",
            (conference_id,),
        ).fetchall()
        members: list[ConferenceMember] = []
        for row in rows:
            members.append(
                ConferenceMember(
                    user_id=row["user_id"],
                    role=ConferenceRole(row["role"]),
                    joined_at=row["joined_at"],
                )
            )
        return members

    def get_member(self, conference_id: str, user_id: str) -> ConferenceMember:
        row = self._connect().execute(
            "SELECT user_id, role, joined_at FROM conference_members "
            "WHERE conference_id = ? AND user_id = ?",
            (conference_id, user_id),
        ).fetchone()
        if row is None:
            raise ConferenceMemberNotFound(user_id, conference_id)
        return ConferenceMember(
            user_id=row["user_id"],
            role=ConferenceRole(row["role"]),
            joined_at=row["joined_at"],
        )

    # ------------------------------------------------------------------ #
    # Writes – Conference
    # ------------------------------------------------------------------ #

    def create(self, name: str, description: str = "") -> Conference:
        conference_id = f"conf-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        self._connect().execute(
            "INSERT INTO conferences "
            "(conference_id, name, description, start_date, end_date, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                conference_id,
                name,
                description,
                None,  # start_date
                None,  # end_date
                now,
                now,
            ),
        )
        # Add the creator as an owner (user_id passed from API, role set via separate endpoint)
        # No-op – ownership is assigned in the API layer after conference creation.
        return Conference(
            conference_id=conference_id,
            name=name,
            description=description,
        )

    # ------------------------------------------------------------------ #
    # Writes – Membership
    # ------------------------------------------------------------------ #

    def update(self, conference_id: str, *, name: str | None = None,
               description: str | None = None) -> Conference:
        current = self.get(conference_id)
        self._connect().execute(
            "UPDATE conferences SET name = ?, description = ?, updated_at = ? "
            "WHERE conference_id = ?",
            (current.name if name is None else name,
             current.description if description is None else description,
             datetime.now(timezone.utc).isoformat(), conference_id),
        )
        return self.get(conference_id)

    def add_member(
        self,
        conference_id: str,
        user_id: str,
        role: ConferenceRole,
    ) -> ConferenceMember:
        """Add or update a member's role in a conference."""
        now = datetime.now(timezone.utc).isoformat()
        self._connect().execute(
            """
            INSERT INTO conference_members (user_id, conference_id, role, joined_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, conference_id)
            DO UPDATE SET role = excluded.role, joined_at = excluded.joined_at
            """,
            (user_id, conference_id, role.value, now),
        )
        return ConferenceMember(
            user_id=user_id,
            role=role,
            joined_at=now,
        )

    def remove_member(self, conference_id: str, user_id: str) -> None:
        self._connect().execute(
            "DELETE FROM conference_members WHERE user_id = ? AND conference_id = ?",
            (user_id, conference_id),
        )

    # ------------------------------------------------------------------ #
    # Utility: check if a user has a required role in a conference
    # ------------------------------------------------------------------ #

    def user_has_role(
        self, conference_id: str, user_id: str, required_role: ConferenceRole
    ) -> bool:
        """Return True if *user_id* holds *required_role* (or higher) in the conference."""
        row = self._connect().execute(
            """
            SELECT role FROM conference_members
            WHERE conference_id = ? AND user_id = ?
            """,
            (conference_id, user_id),
        ).fetchone()
        if row is None:
            return False
        user_role = ConferenceRole(row["role"])
        # Define a simple hierarchy: owner > reviewer > author
        hierarchy = {
            ConferenceRole.OWNER: 3,
            ConferenceRole.REVIEWER: 2,
            ConferenceRole.AUTHOR: 1,
        }
        return hierarchy.get(user_role, 0) >= hierarchy.get(required_role, 0)
