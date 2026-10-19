"""Revision records share the submission store's transaction and authorization scope."""
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.services.formatting import ENGINE_VERSION, validation_status
from app.storage.database import MigrationRequired, require_security_schema


def require_revisions(store):
    require_security_schema(store._connect())
    if not store._connect().execute("SELECT 1 FROM schema_migrations WHERE version=3").fetchone():
        raise MigrationRequired("Revision storage requires the explicit Phase 2 copy upgrade; see PHASE2.md")


def latest(store, submission_id):
    require_revisions(store)
    return store._connect().execute(
        "SELECT * FROM paper_revisions WHERE submission_id=? ORDER BY number DESC LIMIT 1", (submission_id,),
    ).fetchone()


def get_revision(store, submission_id, revision_id):
    require_revisions(store)
    row = store._connect().execute(
        "SELECT * FROM paper_revisions WHERE submission_id=? AND revision_id=?", (submission_id, revision_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Revision not found")
    return row


def view(store, row):
    result = {key: row[key] for key in (
        "revision_id", "submission_id", "number", "parent_revision_id", "sha256", "size_bytes",
        "filename", "uploaded_by", "uploaded_at", "template_id", "change_summary", "submission_status",
    )}
    result["metadata"] = json.loads(row["metadata_json"]) if row["metadata_json"] else None
    run = store._connect().execute(
        "SELECT run_id,status,created_at FROM revision_checks WHERE revision_id=? ORDER BY sequence DESC LIMIT 1",
        (row["revision_id"],),
    ).fetchone()
    result["latest_check"] = dict(run) if run else None
    return result


def append_revision(store, paper, user_id, filename, key, sha256, size, rules, assessment,
                    parent=None, change_summary="", request_key=None):
    """Caller must hold the shared write transaction and verify the current parent."""
    require_revisions(store)
    revision_id = "rev-" + uuid4().hex
    store._connect().execute(
        "INSERT INTO paper_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (revision_id, paper.submission_id, parent["number"] + 1 if parent else 1,
         parent["revision_id"] if parent else None, key, sha256, size, filename, user_id,
         datetime.now(timezone.utc).isoformat(), rules.template_id, rules.model_dump_json(),
         assessment.metadata.model_dump_json() if assessment and assessment.metadata else None,
         change_summary, paper.status.value, request_key),
    )
    # Compatibility fields point at the newest file; old revision rows/files never change.
    store._connect().execute(
        "UPDATE submission_security SET storage_key=?,sha256=?,size_bytes=? WHERE submission_id=?",
        (key, sha256, size, paper.submission_id),
    )
    store._connect().execute(
        "UPDATE submissions SET filename=?,template_id=?,updated_at=? WHERE submission_id=?",
        (filename, rules.template_id, datetime.now(timezone.utc).isoformat(), paper.submission_id),
    )
    return get_revision(store, paper.submission_id, revision_id)


def append_check(store, revision, user_id, assessment=None, error=None, issue_store=None):
    """Append a completed attempt; never replace earlier reports or resolve their issues."""
    run_id = "check-" + uuid4().hex
    conn = store._connect()
    seq = conn.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM revision_checks WHERE revision_id=?",
                       (revision["revision_id"],)).fetchone()[0]
    conn.execute(
        "INSERT INTO revision_checks VALUES (?,?,?,?,?,?,?,?,?)",
        (run_id, revision["revision_id"], seq, user_id, datetime.now(timezone.utc).isoformat(), ENGINE_VERSION,
         validation_status(assessment) if assessment else "unable_to_validate",
         assessment.model_dump_json() if assessment else None, error),
    )
    if assessment and issue_store:
        for result in assessment.results:
            if result.status in {"failed", "missing"}:
                issue = issue_store.create_from_check_result(revision["submission_id"], result)
                conn.execute("INSERT INTO issue_findings VALUES (?,?,?)", (issue.issue_id, run_id, result.id))
    current = latest(store, revision["submission_id"])
    if current["revision_id"] == revision["revision_id"]:
        conn.execute("UPDATE submissions SET compliance_score=? WHERE submission_id=?",
                     (assessment.score if assessment else None, revision["submission_id"]))
    return run_id


def check_view(store, row):
    result = dict(row)
    # Requester can be a chair; identity is unnecessary for the author-visible report.
    result.pop("requested_by")
    result["assessment"] = json.loads(result.pop("assessment_json")) if row["assessment_json"] else None
    result["issues"] = [dict(r) for r in store._connect().execute(
        "SELECT issue_id,rule_id FROM issue_findings WHERE run_id=?", (row["run_id"],))]
    return result
