"""Persistence for compliance reports, backed by SQLite.

Each report is keyed by the original paper filename (unique). Resubmitting the
same filename overwrites the previous report (UPSERT). The full report document
is stored as a JSON blob; summary columns (title, authors, score, verdict, etc.)
are extracted for fast listing without parsing the JSON.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.models.report import ComplianceReport, PaperAssessment, SubmissionReport

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORE_DIR = BACKEND_DIR / "data"
DB_FILENAME = "reports.db"
DB_PATH_ENV = "REPORT_DB_PATH"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    filename      TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    report_json   TEXT NOT NULL,
    paper_title   TEXT DEFAULT '',
    authors_json  TEXT DEFAULT '[]',
    format        TEXT DEFAULT '',
    score         INTEGER DEFAULT 0,
    verdict       TEXT DEFAULT '',
    template_name TEXT DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_updated ON reports (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_score ON reports (score DESC);
"""


class ReportNotFound(LookupError):
    def __init__(self, filename: str) -> None:
        super().__init__(f"Report for '{filename}' was not found.")
        self.filename = filename


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def default_db_path() -> Path:
    override = os.environ.get(DB_PATH_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return DEFAULT_STORE_DIR / DB_FILENAME


class ReportStore:
    """Report persistence on SQLite.

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

    def list(self) -> list[dict[str, Any]]:
        """All reports, most recently updated first."""
        rows = self._connect().execute(
            "SELECT filename, kind, paper_title, authors_json, format, score, verdict, template_name, updated_at "
            "FROM reports ORDER BY updated_at DESC, rowid DESC"
        ).fetchall()
        summaries: list[dict[str, Any]] = []
        for row in rows:
            authors = json.loads(row["authors_json"]) if row["authors_json"] else []
            summaries.append({
                "filename": row["filename"],
                "kind": row["kind"],
                "paper_title": row["paper_title"],
                "authors": authors,
                "format": row["format"],
                "score": row["score"],
                "verdict": row["verdict"],
                "template_name": row["template_name"],
                "updated_at": row["updated_at"],
            })
        return summaries

    def get(self, filename: str) -> dict[str, Any]:
        """Return the full stored report (native shape)."""
        row = self._connect().execute(
            "SELECT report_json FROM reports WHERE filename = ?", (filename,)
        ).fetchone()
        if row is None:
            raise ReportNotFound(filename)
        return json.loads(row["report_json"])

    def get_raw(self, filename: str) -> str:
        """Return the raw JSON string for the report."""
        row = self._connect().execute(
            "SELECT report_json FROM reports WHERE filename = ?", (filename,)
        ).fetchone()
        if row is None:
            raise ReportNotFound(filename)
        return row["report_json"]

    def exists(self, filename: str) -> bool:
        row = self._connect().execute(
            "SELECT 1 FROM reports WHERE filename = ?", (filename,)
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------ #
    # writes
    # ------------------------------------------------------------------ #

    def _extract_summary(self, report: dict[str, Any], kind: str) -> dict[str, Any]:
        """Extract summary columns from a report dict."""
        if kind == "submission":
            papers = report.get("papers", [])
            if papers:
                paper = papers[0]
                metadata = paper.get("metadata") or {}
                return {
                    "paper_title": metadata.get("title", "") or "",
                    "authors": metadata.get("authors", []) or [],
                    "format": paper.get("format", "") or "",
                    "score": paper.get("score", 0),
                    "verdict": paper.get("verdict", "needs_review") or "needs_review",
                    "template_name": report.get("template_name", "") or "",
                }
        else:  # comparison
            meta = report.get("metadata") or {}
            return {
                "paper_title": meta.get("title", "") or "",
                "authors": meta.get("authors", []) or [],
                "format": report.get("meta", {}).get("format", "") or "",
                "score": report.get("score", 0),
                "verdict": "accepted" if report.get("score", 0) == 100 else "needs_review",
                "template_name": report.get("meta", {}).get("template_title", "") or "",
            }
        return {
            "paper_title": "",
            "authors": [],
            "format": "",
            "score": 0,
            "verdict": "needs_review",
            "template_name": "",
        }

    def save(
        self,
        filename: str,
        report: dict[str, Any],
        kind: str,
    ) -> None:
        """Save or overwrite a report keyed by filename."""
        if not filename:
            raise ValueError("filename must not be empty")
        summary = self._extract_summary(report, kind)
        now = _now()
        if self.exists(filename):
            self._connect().execute(
                "UPDATE reports SET "
                "kind = ?, report_json = ?, paper_title = ?, authors_json = ?, "
                "format = ?, score = ?, verdict = ?, template_name = ?, updated_at = ? "
                "WHERE filename = ?",
                (
                    kind,
                    json.dumps(report),
                    summary["paper_title"],
                    json.dumps(summary["authors"]),
                    summary["format"],
                    summary["score"],
                    summary["verdict"],
                    summary["template_name"],
                    now,
                    filename,
                ),
            )
        else:
            self._connect().execute(
                "INSERT INTO reports "
                "(filename, kind, report_json, paper_title, authors_json, format, score, verdict, template_name, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    filename,
                    kind,
                    json.dumps(report),
                    summary["paper_title"],
                    json.dumps(summary["authors"]),
                    summary["format"],
                    summary["score"],
                    summary["verdict"],
                    summary["template_name"],
                    now,
                    now,
                ),
            )

    def delete(self, filename: str) -> None:
        cursor = self._connect().execute(
            "DELETE FROM reports WHERE filename = ?", (filename,)
        )
        if cursor.rowcount == 0:
            raise ReportNotFound(filename)


_store: Optional[ReportStore] = None


def get_report_store() -> ReportStore:
    global _store
    if _store is None:
        _store = ReportStore()
    return _store


def reset_report_store(location: Path | str | None = None) -> ReportStore:
    """Swap the store implementation; used by tests."""
    global _store
    _store = ReportStore(location)
    return _store


__all__ = [
    "ReportStore",
    "ReportNotFound",
    "get_report_store",
    "reset_report_store",
    "default_db_path",
    "DEFAULT_STORE_DIR",
    "DB_FILENAME",
    "DB_PATH_ENV",
]