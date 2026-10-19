"""Persistence for submissions, discussion threads, and review assignments, backed by SQLite.

Follows the same patterns as user_store and conference_store. New tables are
created on first use (CREATE TABLE IF NOT EXISTS).
"""

from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models.submission import (
    DiscussionThread,
    ReviewAssignment,
    ReviewVerdict,
    Submission,
    SubmissionStatus,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORE_DIR = BASE_DIR / "data"
DB_FILENAME = "submissions.db"
DB_PATH_ENV = "SUBMISSION_DB_PATH"


def default_db_path() -> Path:
    """Return the default database path unless SUBMISSION_DB_PATH is set."""
    from .database import configured_path
    return configured_path(DEFAULT_STORE_DIR / DB_FILENAME, DB_PATH_ENV)


class SubmissionNotFound(LookupError):
    def __init__(self, submission_id: str) -> None:
        super().__init__(f"Submission '{submission_id}' was not found.")
        self.submission_id = submission_id


class DiscussionNotFound(LookupError):
    def __init__(self, thread_id: str) -> None:
        super().__init__(f"Discussion thread '{thread_id}' was not found.")
        self.thread_id = thread_id


class AssignmentNotFound(LookupError):
    def __init__(self, assignment_id: str) -> None:
        super().__init__(f"Review assignment '{assignment_id}' was not found.")
        self.assignment_id = assignment_id


SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    submission_id TEXT PRIMARY KEY,
    conference_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    reviewer_id TEXT,
    verdict TEXT,
    compliance_score INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discussion_threads (
    thread_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    messages TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS review_assignments (
    assignment_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    assigned_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    assigned_at TEXT NOT NULL
);
"""

_disposed: bool = False


def _default_db_path() -> Path:
    """Return the default database path unless SUBMISSION_DB_PATH is set."""
    override = __import__("os").environ.get(DB_PATH_ENV, "").strip()
    if override:
        return __import__("pathlib").Path(override).expanduser()
    return DEFAULT_STORE_DIR / DB_FILENAME


class SubmissionStore:
    """SQLite‑backed store for Submission, DiscussionThread, and ReviewAssignment."""

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
            conn = sqlite3.connect(self.db_path, isolation_level=None)
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

    def security(self, submission_id):
        from .database import require_security_schema
        require_security_schema(self._connect())
        return self._connect().execute(
            "SELECT * FROM submission_security WHERE submission_id=?", (submission_id,)
        ).fetchone()

    def secure(self, submission_id, submitter_id, storage_key, sha256, size_bytes):
        self._connect().execute(
            "INSERT INTO submission_security VALUES (?,?,?,?,?)",
            (submission_id, submitter_id, storage_key, sha256, size_bytes),
        )

    def audit(self, actor_id, action, target_id, *, details=None, visibility="participants", revision_id=None):
        self._connect().execute(
            "INSERT INTO security_events(actor_id,action,target_id,created_at) VALUES (?,?,?,?)",
            (actor_id, action, target_id, datetime.now(timezone.utc).isoformat()),
        )
        from app.services.workflow import actor_role, available
        if available(self):
            paper = self._connect().execute("SELECT submission_id FROM submissions WHERE submission_id=?", (target_id,)).fetchone()
            if paper is None:
                paper = self._connect().execute("SELECT submission_id FROM issues WHERE issue_id=?", (target_id,)).fetchone()
            if paper:
                import json
                if action == "reviewer.verdict_recorded":
                    visibility = "chairs"
                self._connect().execute(
                    "INSERT INTO paper_events(submission_id,actor_id,actor_role,action,visibility,revision_id,details_json,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (paper[0], actor_id, actor_role(self._connect(), paper[0], actor_id), action, visibility,
                     revision_id, json.dumps(details or {}), datetime.now(timezone.utc).isoformat()),
                )

    # ---------- Submissions ----------

    def create(
        self,
        conference_id: str,
        template_id: str,
        filename: str,
        reviewer_id: Optional[str] = None,
    ) -> Submission:
        submission_id = f"sub-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        self._connect().execute(
            """
            INSERT INTO submissions
                (submission_id, conference_id, template_id, filename, status,
                 reviewer_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                submission_id,
                conference_id,
                template_id,
                filename,
                SubmissionStatus.DRAFT.value,
                reviewer_id,
                now,
                now,
            ),
        )
        from app.services.intake import allocate_number
        allocate_number(self, submission_id, conference_id)
        return self.get(submission_id)

    def get(self, submission_id: str) -> Submission:
        row = self._connect().execute(
            "SELECT submission_id, conference_id, template_id, filename, status, "
            "reviewer_id, verdict, compliance_score, created_at, updated_at "
            "FROM submissions WHERE submission_id = ?",
            (submission_id,),
        ).fetchone()
        if row is None:
            raise SubmissionNotFound(submission_id)
        from app.services.intake import enrich
        return enrich(self, Submission(
            submission_id=row["submission_id"],
            conference_id=row["conference_id"],
            template_id=row["template_id"],
            filename=row["filename"],
            status=SubmissionStatus(row["status"]),
            reviewer_id=row["reviewer_id"],
            verdict=(
                ReviewVerdict(row["verdict"]) if row["verdict"] else None
            ),
            compliance_score=row["compliance_score"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ))

    def list_by_conference(self, conference_id: str, query: str | None = None) -> list[Submission]:
        """List submissions for a conference, optionally filtered by a query string
        that matches against the filename (case-insensitive).
        """
        if query:
            like = f"%{query}%"
            rows = self._connect().execute(
                """
                SELECT submission_id, conference_id, template_id, filename, status,
                reviewer_id, verdict, compliance_score, created_at, updated_at
                FROM submissions WHERE conference_id = ? AND LOWER(filename) LIKE LOWER(?)
                ORDER BY created_at DESC
                """,
                (conference_id, like),
            ).fetchall()
        else:
            rows = self._connect().execute(
                """
                SELECT submission_id, conference_id, template_id, filename, status,
                reviewer_id, verdict, compliance_score, created_at, updated_at
                FROM submissions WHERE conference_id = ? ORDER BY created_at DESC
                """,
                (conference_id,),
            ).fetchall()
        subs: list[Submission] = []
        for r in rows:
            subs.append(
                Submission(
                    submission_id=r["submission_id"],
                    conference_id=r["conference_id"],
                    template_id=r["template_id"],
                    filename=r["filename"],
                    status=SubmissionStatus(r["status"]),
                    reviewer_id=r["reviewer_id"],
                    verdict=(
                        ReviewVerdict(r["verdict"]) if r["verdict"] else None
                    ),
                    compliance_score=r["compliance_score"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
            )
        from app.services.intake import enrich
        return [enrich(self, paper) for paper in subs]

    def update_status(
        self, submission_id: str, status: SubmissionStatus
    ) -> Submission:
        now = datetime.now(timezone.utc).isoformat()
        self._connect().execute(
            "UPDATE submissions SET status = ?, updated_at = ? WHERE submission_id = ?",
            (status.value, now, submission_id),
        )
        return self.get(submission_id)

    def update_verdict(
        self,
        submission_id: str,
        verdict: Optional[ReviewVerdict],
        score: Optional[int] = None,
    ) -> Submission:
        now = datetime.now(timezone.utc).isoformat()
        if verdict is not None:
            self._connect().execute(
                """UPDATE submissions
                   SET verdict = ?, compliance_score = ?, updated_at = ?
                   WHERE submission_id = ?""",
                (verdict.value, score, now, submission_id),
            )
        else:
            self._connect().execute(
                """UPDATE submissions
                   SET verdict = NULL, compliance_score = ?, updated_at = ?
                   WHERE submission_id = ?""",
                (score, now, submission_id),
            )
        return self.get(submission_id)

    # ---------- Discussion Threads ----------

    def create_thread(
        self,
        submission_id: str,
        author_id: str,
        title: str,
    ) -> DiscussionThread:
        thread_id = f"thread-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        messages_json = "[]"
        self._connect().execute(
            """
            INSERT INTO discussion_threads
                (thread_id, submission_id, author_id, title, created_at, messages)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (thread_id, submission_id, author_id, title, now, messages_json),
        )
        return DiscussionThread(
            thread_id=thread_id,
            submission_id=submission_id,
            author_id=author_id,
            title=title,
        )

    def get_thread(self, thread_id: str) -> DiscussionThread:
        row = self._connect().execute(
            "SELECT thread_id, submission_id, author_id, title, created_at, messages "
            "FROM discussion_threads WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        if row is None:
            raise DiscussionNotFound(thread_id)
        messages = __import__("json").loads(row["messages"])
        return DiscussionThread(
            thread_id=row["thread_id"],
            submission_id=row["submission_id"],
            author_id=row["author_id"],
            title=row["title"],
            messages=messages,
        )

    def add_message(self, thread_id: str, author_id: str, text: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        # Load existing, append, save back
        thread = self.get_thread(thread_id)
        thread.messages.append({"author": author_id, "text": text, "timestamp": now})
        # Write back the full list
        self._connect().execute(
            "UPDATE discussion_threads SET messages = ? WHERE thread_id = ?",
            (__import__("json").dumps(thread.messages), thread_id),
        )

    # ---------- Review Assignments ----------

    def assign_reviewer(
        self,
        submission_id: str,
        reviewer_id: str,
        assigned_by: str,
    ) -> ReviewAssignment:
        assignment_id = f"assign-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        self._connect().execute(
            """
            INSERT INTO review_assignments
                (assignment_id, submission_id, reviewer_id, assigned_by, status, assigned_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (assignment_id, submission_id, reviewer_id, assigned_by, "pending", now),
        )
        self._connect().execute(
            "UPDATE submissions SET reviewer_id = ?, updated_at = ? WHERE submission_id = ?",
            (reviewer_id, now, submission_id),
        )
        return ReviewAssignment(
            assignment_id=assignment_id,
            submission_id=submission_id,
            reviewer_id=reviewer_id,
            assigned_by=assigned_by,
            status="pending",
            assigned_at=now,
        )

    def get_assignment(self, assignment_id: str) -> ReviewAssignment:
        row = self._connect().execute(
            "SELECT assignment_id, submission_id, reviewer_id, assigned_by, status, assigned_at "
            "FROM review_assignments WHERE assignment_id = ?",
            (assignment_id,),
        ).fetchone()
        if row is None:
            raise AssignmentNotFound(assignment_id)
        return ReviewAssignment(
            assignment_id=row["assignment_id"],
            submission_id=row["submission_id"],
            reviewer_id=row["reviewer_id"],
            assigned_by=row["assigned_by"],
            status=row["status"],
            assigned_at=row["assigned_at"],
        )

    def list_assignments(self, submission_id: str) -> list[ReviewAssignment]:
        rows = self._connect().execute(
            "SELECT assignment_id, submission_id, reviewer_id, assigned_by, status, assigned_at "
            "FROM review_assignments WHERE submission_id = ? ORDER BY assigned_at",
            (submission_id,),
        ).fetchall()
        return [
            ReviewAssignment(
                assignment_id=r["assignment_id"],
                submission_id=r["submission_id"],
                reviewer_id=r["reviewer_id"],
                assigned_by=r["assigned_by"],
                status=r["status"],
                assigned_at=r["assigned_at"],
            )
            for r in rows
        ]

    def get_thread_for_submission(self, submission_id: str) -> DiscussionThread:
        """Get the discussion thread for a submission, creating one if it doesn't exist."""
        # First try to find existing thread
        row = self._connect().execute(
            "SELECT thread_id, submission_id, author_id, title, created_at, messages "
            "FROM discussion_threads WHERE submission_id = ?",
            (submission_id,),
        ).fetchone()

        if row is not None:
            messages = __import__("json").loads(row["messages"])
            return DiscussionThread(
                thread_id=row["thread_id"],
                submission_id=row["submission_id"],
                author_id=row["author_id"],
                title=row["title"],
                messages=messages,
            )

        # If no thread exists, create a default one
        thread_id = f"thread-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        messages_json = "[]"
        self._connect().execute(
            """
            INSERT INTO discussion_threads
                (thread_id, submission_id, author_id, title, created_at, messages)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (thread_id, submission_id, "system", "Default discussion thread", now, messages_json),
        )
        return DiscussionThread(
            thread_id=thread_id,
            submission_id=submission_id,
            author_id="system",
            title="Default discussion thread",
            messages=[],
        )


_store: Optional[SubmissionStore] = None


def get_submission_store() -> SubmissionStore:
    global _store
    if _store is None:
        _store = SubmissionStore()
    return _store


def reset_submission_store(location: Path | str | None = None) -> SubmissionStore:
    """Swap the store implementation; used by tests."""
    global _store
    _store = SubmissionStore(location)
    return _store


__all__ = [
    "SubmissionStore",
    "SubmissionNotFound",
    "get_submission_store",
    "reset_submission_store",
    "default_db_path",
    "DEFAULT_STORE_DIR",
    "DB_FILENAME",
    "DB_PATH_ENV",
]
