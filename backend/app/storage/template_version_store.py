"""Version‑aware persistence for templates tied to a conference.

This store builds on top of the existing ``TemplateStore`` and adds:
* a ``conference_id`` foreign key so every template version knows which
  conference it belongs to,
* immutable versioning – each ``save`` creates a new row with a new
  ``template_id`` (UUID suffix) and does not mutate the previous version,
* simple lookup helpers for the *active* (latest) version of a template
  belonging to a given conference.

The public surface mirrors ``TemplateStore`` so the downstream rule engine
and API routes can stay familiar.
"""

from __future__ import annotations

import os
import sqlite3
from .postgres_compat import connect as connect_database
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.models.rules import RuleSet
from app.storage.conference_store import ConferenceStore

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORE_DIR = BACKEND_DIR / "data"
DB_FILENAME = "template_versions.db"
DB_PATH_ENV = "TEMPLATE_VERSION_DB_PATH"


class TemplateVersionNotFound(LookupError):
    def __init__(self, conference_id: str, version: str) -> None:
        super().__init__(
            f"Template version '{version}' not found in conference '{conference_id}'."
        )
        self.conference_id = conference_id
        self.version = version


SCHEMA = """
CREATE TABLE IF NOT EXISTS template_versions (
    template_id      TEXT PRIMARY KEY,
    conference_id    TEXT NOT NULL,
    name             TEXT NOT NULL,
    rules_json       TEXT NOT NULL,
    version          TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    UNIQUE (conference_id, version)
);

CREATE INDEX IF NOT EXISTS idx_versions_conference
    ON template_versions (conference_id, created_at DESC);
"""


class TemplateVersionStore:
    """Immutable versioned template store on SQLite.

    Each call to ``save`` for a given conference creates a fresh
    ``template_id`` and stores the rule set snapshot.  Older versions remain
    intact – the rule engine must specify which ``template_id`` to use.

    ``TemplateStore``‑compatible methods are provided so that callers that only
    need the latest version can treat this as a drop‑in replacement, while
    callers that need historic versions use the explicit ``get_version`` path.
    """

    def __init__(self, conference_store: ConferenceStore, location: Path | str | None = None) -> None:
        self.conference_store = conference_store
        if location is None:
            self.db_path = self._default_db_path()
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
        # Initialise the SQLite schema
        with self._connect() as conn:
            conn.executescript(SCHEMA)
    # ------------------------------------------------------------------ #
    # connection handling
    # ------------------------------------------------------------------ #

    def _default_db_path(self) -> Path:
        from .database import configured_path
        return configured_path(DEFAULT_STORE_DIR / DB_FILENAME, DB_PATH_ENV)

    @property
    def _resolved_db_path(self) -> Path:
        return self.db_path

    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            resolved = self._resolved_db_path
            resolved.parent.mkdir(parents=True, exist_ok=True)
            conn = connect_database(
                resolved,
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
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ------------------------------------------------------------------ #
    # Core writes – immutable save (creates a new version)
    # ------------------------------------------------------------------ #

    def save(self, rules: RuleSet, conference_id: str, name: str | None = None) -> RuleSet:
        """Create a **new** immutable version of the given rule set for *conference_id*.

        The returned ``RuleSet`` will have its ``template_id`` set to a fresh
        UUID‑based identifier.  All previous versions for the same conference
        are left untouched.
        """
        # Ensure the conference exists
        self.conference_store.get(conference_id)

        # Generate a fresh template_id; base is derived from the name, suffixed
        # with a short UUID hex to guarantee uniqueness.
        base = name or rules.name
        slug = self._slugify(base)
        new_template_id = f"{slug}-{uuid.uuid4().hex[:6]}"

        snapshot = rules.model_copy(deep=True)
        snapshot.template_id = new_template_id

        # Store the snapshot in the versioned table
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        self._connect().execute(
            """
            INSERT INTO template_versions
                (template_id, conference_id, name, rules_json, version, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                new_template_id,
                conference_id,
                name or rules.name,
                snapshot.model_dump_json(),
                new_template_id,
                now,
            ),
        )

        return snapshot

    # ------------------------------------------------------------------ #
    # Reads – fetch a specific version
    # ------------------------------------------------------------------ #

    def get_version(
        self, conference_id: str, template_id: str
    ) -> RuleSet:
        """Return the RuleSet for the given *template_id* belonging to *conference_id*.

        Raises ``TemplateVersionNotFound`` if the version does not exist.
        """
        row = self._connect().execute(
            "SELECT template_id, rules_json FROM template_versions "
            "WHERE conference_id = ? AND template_id = ?",
            (conference_id, template_id),
        ).fetchone()
        if row is None:
            raise TemplateVersionNotFound(conference_id, template_id)
        return RuleSet.model_validate_json(row["rules_json"]).model_copy(
            update={"template_id": row["template_id"]}
        )

    def list_versions(
        self, conference_id: str
    ) -> list[tuple[str, str, str]]:  # (template_id, version, created_at)
        """List all template versions for a conference, newest first."""
        rows = self._connect().execute(
            """
            SELECT template_id, version, created_at
            FROM template_versions
            WHERE conference_id = ?
            ORDER BY created_at DESC
            """,
            (conference_id,),
        ).fetchall()
        return [
            (row["template_id"], row["version"], row["created_at"])
            for row in rows
        ]

    def list_template_ids(self, conference_id: str) -> list[str]:
        """Return just the template_id values (newest first)."""
        rows = self.list_versions(conference_id)
        return [r[0] for r in rows]

    # ------------------------------------------------------------------ #
    # Read – latest (active) version for a conference
    # ------------------------------------------------------------------ #

    def get_latest(self, conference_id: str) -> RuleSet:
        """Return the most recently created RuleSet for *conference_id*.

        Raises ``TemplateVersionNotFound`` if no version exists.
        """
        row = self._connect().execute(
            """
            SELECT template_id, rules_json
            FROM template_versions
            WHERE conference_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (conference_id,),
        ).fetchone()
        if row is None:
            raise TemplateVersionNotFound(conference_id, "")
        return RuleSet.model_validate_json(row["rules_json"]).model_copy(
            update={"template_id": row["template_id"]}
        )

    def get_latest_template_id(self, conference_id: str) -> str:
        """Return the template_id of the latest version, or raise not found."""
        rows = self._connect().execute(
            """
            SELECT template_id
            FROM template_versions
            WHERE conference_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (conference_id,),
        ).fetchone()
        if rows is None:
            raise TemplateVersionNotFound(conference_id, "")
        return rows["template_id"]

    # ------------------------------------------------------------------ #
    # Helper: slugify a string (same algorithm as TemplateStore)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _slugify(value: str) -> str:
        cleaned = "".join(c if c.isalnum() or c in "-_" else "-" for c in value.strip().casefold())
        cleaned = "-".join(part for part in cleaned.split("-") if part)
        return cleaned[:60] or "template"
