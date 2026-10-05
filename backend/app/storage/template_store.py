"""Persistence for conference-manager rule templates, backed by SQLite.

A rule set is a deeply nested configuration document that the manager edits and
reads back mostly as a whole, so it is stored as a JSON document in a single
column. The columns beside it (``name``, ``created_at``, ``updated_at``) exist
for listing, searching and ordering, not for querying into the rules themselves.

Why SQLite rather than a JSON file per template: a file-per-template store has
no shared index, so listing loads and parses every rule set; there is no
transaction, so two concurrent writers can interleave; and there is no place to
hang audit columns. SQLite gives all three for free and needs no server.

The public surface is unchanged from the old file-backed store -- ``list``,
``get``, ``exists``, ``create``, ``save``, ``delete`` plus ``TemplateNotFound``
-- so the API layer and the rule engine are untouched.

Connections are per-thread: ``sqlite3`` objects may not be shared between
threads, and the sync endpoints run in FastAPI's threadpool. WAL mode plus a
busy timeout means readers do not block the writer, and concurrent writers wait
rather than raising "database is locked".
"""

from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models.rules import RuleSet

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORE_DIR = BACKEND_DIR / "data"
DB_FILENAME = "templates.db"
DB_PATH_ENV = "TEMPLATE_DB_PATH"

SCHEMA = """
CREATE TABLE IF NOT EXISTS templates (
    template_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    rules_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_templates_name ON templates (name);
"""


class TemplateNotFound(LookupError):
    def __init__(self, template_id: str) -> None:
        super().__init__(f"Template '{template_id}' was not found.")
        self.template_id = template_id


def _slugify(value: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_" else "-" for c in value.strip().casefold())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:60] or "template"


def _now() -> str:
    # Microsecond precision on purpose: at second resolution two edits made in
    # quick succession tie, and the tiebreak below would fall back to creation
    # order, so a freshly saved template would sort as older than the one it
    # replaced.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def default_db_path() -> Path:
    """Where the database lives unless the operator says otherwise.

    ``TEMPLATE_DB_PATH`` points the store at a mounted volume, which is what
    makes the data survive a redeploy on a platform with an ephemeral
    filesystem.
    """
    override = os.environ.get(DB_PATH_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return DEFAULT_STORE_DIR / DB_FILENAME


class TemplateStore:
    """Rule-set persistence on SQLite.

    The database is created and migrated on first use, so a fresh checkout works
    with no setup step.

    ``location`` may be a directory (the database is created inside it) or a
    file path ending in ``.db``/``.sqlite``. Tests pass a directory; the
    ``TEMPLATE_DB_PATH`` override passes a file.
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
                # Autocommit: each statement is its own atomic transaction, so
                # a failed write cannot leave a half-updated rule set.
                isolation_level=None,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            # Wait for a competing writer instead of failing the request.
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

    def list(self) -> list[RuleSet]:
        """All templates, most recently updated first.

        ``rowid`` is the creation order, used only to break exact timestamp
        ties.
        """
        rows = self._connect().execute(
            "SELECT rules_json FROM templates ORDER BY updated_at DESC, rowid DESC"
        ).fetchall()
        templates: list[RuleSet] = []
        for row in rows:
            try:
                templates.append(RuleSet.model_validate_json(row["rules_json"]))
            except Exception:
                # A row that no longer validates (rules changed shape across
                # versions) must not break the whole list endpoint.
                continue
        return templates

    def get(self, template_id: str) -> RuleSet:
        row = self._connect().execute(
            "SELECT rules_json FROM templates WHERE template_id = ?", (template_id,)
        ).fetchone()
        if row is None:
            raise TemplateNotFound(template_id)
        return RuleSet.model_validate_json(row["rules_json"])

    def exists(self, template_id: str) -> bool:
        row = self._connect().execute(
            "SELECT 1 FROM templates WHERE template_id = ?", (template_id,)
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------ #
    # writes
    # ------------------------------------------------------------------ #

    def create(self, rules: RuleSet) -> RuleSet:
        base = _slugify(rules.name)
        rules.template_id = f"{base}-{uuid.uuid4().hex[:6]}"
        now = _now()
        self._connect().execute(
            "INSERT INTO templates "
            "(template_id, name, rules_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (rules.template_id, rules.name, rules.model_dump_json(), now, now),
        )
        return rules

    def save(self, rules: RuleSet) -> RuleSet:
        if not rules.template_id:
            return self.create(rules)
        if not self.exists(rules.template_id):
            raise TemplateNotFound(rules.template_id)
        self._connect().execute(
            "UPDATE templates SET name = ?, rules_json = ?, updated_at = ? "
            "WHERE template_id = ?",
            (rules.name, rules.model_dump_json(), _now(), rules.template_id),
        )
        return rules

    def delete(self, template_id: str) -> None:
        cursor = self._connect().execute(
            "DELETE FROM templates WHERE template_id = ?", (template_id,)
        )
        if cursor.rowcount == 0:
            raise TemplateNotFound(template_id)


_store: Optional[TemplateStore] = None


def get_store() -> TemplateStore:
    global _store
    if _store is None:
        _store = TemplateStore()
    return _store


def reset_store(location: Path | str | None = None) -> TemplateStore:
    """Swap the store implementation; used by tests."""
    global _store
    _store = TemplateStore(location)
    return _store


__all__ = [
    "TemplateStore",
    "TemplateNotFound",
    "get_store",
    "reset_store",
    "default_db_path",
    "DEFAULT_STORE_DIR",
    "DB_FILENAME",
    "DB_PATH_ENV",
]
