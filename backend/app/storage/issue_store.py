"""Persistence for issues and issue comments, backed by SQLite."""

from __future__ import annotations

import os
import sqlite3
from .postgres_compat import connect as connect_database
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from app.models.issue import Issue, IssueComment, IssueStatus, IssueSeverity

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORE_DIR = BASE_DIR / "data"
DB_FILENAME = "issues.db"
DB_PATH_ENV = "ISSUE_DB_PATH"


class IssueNotFound(LookupError):
    def __init__(self, issue_id: str) -> None:
        super().__init__(f"Issue '{issue_id}' was not found.")
        self.issue_id = issue_id


class IssueCommentNotFound(LookupError):
    def __init__(self, comment_id: str) -> None:
        super().__init__(f"Issue comment '{comment_id}' was not found.")
        self.comment_id = comment_id


SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
    issue_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    check_result_id TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    expected TEXT,
    actual TEXT,
    advice TEXT,
    evidence TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    assignee_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by TEXT
);

CREATE TABLE IF NOT EXISTS issue_comments (
    comment_id TEXT PRIMARY KEY,
    issue_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issues_submission ON issues (submission_id);
CREATE INDEX IF NOT EXISTS idx_issues_status ON issues (status);
CREATE INDEX IF NOT EXISTS idx_issues_assignee ON issues (assignee_id);
CREATE INDEX IF NOT EXISTS idx_comments_issue ON issue_comments (issue_id);
"""


def default_db_path() -> Path:
    from .database import configured_path
    return configured_path(DEFAULT_STORE_DIR / DB_FILENAME, DB_PATH_ENV)


class IssueStore:
    """SQLite-backed store for Issues and IssueComments."""

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

    # ---------- Issues ----------

    def create_from_check_result(
        self,
        submission_id: str,
        check_result,
    ) -> Issue:
        """Create an Issue from a CheckResult (typically for failed/missing checks)."""
        issue_id = f"issue-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        # Map CheckResult severity to IssueSeverity
        severity_map = {
            "blocking": IssueSeverity.BLOCKING,
            "warning": IssueSeverity.WARNING,
            "advisory": IssueSeverity.ADVISORY,
        }
        issue_severity = severity_map.get(
            check_result.severity.value if hasattr(check_result.severity, 'value') else str(check_result.severity).lower(),
            IssueSeverity.WARNING
        )

        issue = Issue(
            issue_id=issue_id,
            submission_id=submission_id,
            check_result_id=check_result.id,
            category=check_result.category,
            title=check_result.name,
            description=f"{check_result.name}: {check_result.evidence or 'No evidence provided'}",
            severity=issue_severity,
            expected=str(check_result.expected) if check_result.expected is not None else None,
            actual=str(check_result.actual) if check_result.actual is not None else None,
            advice=check_result.advice,
            evidence=check_result.evidence,
        )

        self._connect().execute(
            """
            INSERT INTO issues
                (issue_id, submission_id, check_result_id, category, title, description,
                 severity, expected, actual, advice, evidence, status, assignee_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                issue_id,
                submission_id,
                check_result.id,
                check_result.category,
                check_result.name,
                issue.description,
                issue.severity.value,
                issue.expected,
                issue.actual,
                issue.advice,
                issue.evidence,
                IssueStatus.OPEN.value,
                None,
                now,
                now,
            ),
        )
        return issue

    def get(self, issue_id: str) -> Issue:
        row = self._connect().execute(
            "SELECT issue_id, submission_id, check_result_id, category, title, description, "
            "severity, expected, actual, advice, evidence, status, assignee_id, created_at, updated_at, "
            "resolved_at, resolved_by FROM issues WHERE issue_id = ?",
            (issue_id,),
        ).fetchone()
        if row is None:
            raise IssueNotFound(issue_id)
        return Issue(
            issue_id=row["issue_id"],
            submission_id=row["submission_id"],
            check_result_id=row["check_result_id"],
            category=row["category"],
            title=row["title"],
            description=row["description"],
            severity=IssueSeverity(row["severity"]),
            expected=row["expected"],
            actual=row["actual"],
            advice=row["advice"],
            evidence=row["evidence"],
            status=IssueStatus(row["status"]),
            assignee_id=row["assignee_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            resolved_at=row["resolved_at"],
            resolved_by=row["resolved_by"],
        )

    def list_by_submission(self, submission_id: str) -> List[Issue]:
        rows = self._connect().execute(
            "SELECT issue_id, submission_id, check_result_id, category, title, description, "
            "severity, expected, actual, advice, evidence, status, assignee_id, created_at, updated_at, "
            "resolved_at, resolved_by FROM issues WHERE submission_id = ? ORDER BY created_at",
            (submission_id,),
        ).fetchall()
        issues: List[Issue] = []
        for r in rows:
            issues.append(
                Issue(
                    issue_id=r["issue_id"],
                    submission_id=r["submission_id"],
                    check_result_id=r["check_result_id"],
                    category=r["category"],
                    title=r["title"],
                    description=r["description"],
                    severity=IssueSeverity(r["severity"]),
                    expected=r["expected"],
                    actual=r["actual"],
                    advice=r["advice"],
                    evidence=r["evidence"],
                    status=IssueStatus(r["status"]),
                    assignee_id=r["assignee_id"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    resolved_at=r["resolved_at"],
                    resolved_by=r["resolved_by"],
                )
            )
        return issues

    def update_status(
        self,
        issue_id: str,
        status: IssueStatus,
        resolved_by: Optional[str] = None,
    ) -> Issue:
        now = datetime.now(timezone.utc).isoformat()
        if status == IssueStatus.RESOLVED:
            self._connect().execute(
                "UPDATE issues SET status = ?, updated_at = ?, resolved_at = ?, resolved_by = ? WHERE issue_id = ?",
                (status.value, now, now, resolved_by, issue_id),
            )
        else:
            self._connect().execute(
                "UPDATE issues SET status = ?, updated_at = ? WHERE issue_id = ?",
                (status.value, now, issue_id),
            )
        return self.get(issue_id)

    def assign(self, issue_id: str, assignee_id: Optional[str]) -> Issue:
        now = datetime.now(timezone.utc).isoformat()
        self._connect().execute(
            "UPDATE issues SET assignee_id = ?, updated_at = ? WHERE issue_id = ?",
            (assignee_id, now, issue_id),
        )
        return self.get(issue_id)

    # ---------- Issue Comments ----------

    def add_comment(self, issue_id: str, author_id: str, text: str) -> IssueComment:
        comment_id = f"comment-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        self._connect().execute(
            "INSERT INTO issue_comments (comment_id, issue_id, author_id, text, created_at) VALUES (?, ?, ?, ?, ?)",
            (comment_id, issue_id, author_id, text, now),
        )
        return IssueComment(
            comment_id=comment_id,
            issue_id=issue_id,
            author_id=author_id,
            text=text,
            created_at=now,
        )

    def get_comments(self, issue_id: str) -> List[IssueComment]:
        rows = self._connect().execute(
            "SELECT comment_id, issue_id, author_id, text, created_at FROM issue_comments WHERE issue_id = ? ORDER BY created_at",
            (issue_id,),
        ).fetchall()
        return [
            IssueComment(
                comment_id=r["comment_id"],
                issue_id=r["issue_id"],
                author_id=r["author_id"],
                text=r["text"],
                created_at=r["created_at"],
            )
            for r in rows
        ]


_store: Optional[IssueStore] = None


def get_issue_store() -> IssueStore:
    global _store
    if _store is None:
        _store = IssueStore()
    return _store


def reset_issue_store(location: Path | str | None = None) -> IssueStore:
    global _store
    _store = IssueStore(location)
    return _store


__all__ = [
    "IssueStore",
    "IssueNotFound",
    "IssueCommentNotFound",
    "get_issue_store",
    "reset_issue_store",
    "default_db_path",
    "DEFAULT_STORE_DIR",
    "DB_FILENAME",
    "DB_PATH_ENV",
]
