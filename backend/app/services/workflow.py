"""Submission transitions and formatting gates, separate from academic recommendations."""
from fastapi import HTTPException

from app.security.permissions import can_edit, is_chair
from app.storage import revisions
from app.storage.database import MigrationRequired
from app.services import intake

TERMINAL = {"accepted", "rejected", "withdrawn"}
TRANSITIONS = {
    "draft": {"submitted", "withdrawn"},
    "submitted": {"under_review", "rejected", "withdrawn"},
    "under_review": {"changes_requested", "accepted", "rejected", "withdrawn"},
    "changes_requested": {"submitted", "withdrawn"},
    "accepted": set(), "rejected": set(), "withdrawn": set(),
}


def available(store):
    return bool(store._connect().execute("SELECT 1 FROM schema_migrations WHERE version=4").fetchone())


def require_workflow(store):
    if not available(store):
        raise MigrationRequired("Collaboration requires the explicit Phase 3 copy upgrade; see PHASE3.md")


def policy(store, conference_id):
    if not available(store):
        return "allow_issues"
    row = store._connect().execute("SELECT formatting_gate FROM conference_workflow WHERE conference_id=?", (conference_id,)).fetchone()
    return row[0] if row else "allow_issues"


def eligibility(store, paper):
    current = revisions.latest(store, paper.submission_id)
    run = store._connect().execute(
        "SELECT status FROM revision_checks WHERE revision_id=? ORDER BY sequence DESC LIMIT 1",
        (current["revision_id"],),
    ).fetchone() if current else None
    status = run[0] if run else "not_checked"
    gate = policy(store, paper.conference_id)
    allowed = status in {"passed", "passed_with_warnings"} or (gate == "allow_issues" and status == "failed")
    reason = None if allowed else (
        "Correct the blocking formatting findings before submitting for review."
        if status == "failed" else "A completed formatting assessment is required before review."
    )
    metadata = intake.readiness(store, paper)
    if allowed and not metadata["eligible"]:
        allowed, reason = False, metadata["reason"]
    return {"revision_id": current["revision_id"] if current else None,
            "formatting_status": status, "formatting_gate": gate, "eligible": allowed, "reason": reason}


def manager(paper, actor, conferences, store):
    security = store.security(paper.submission_id)
    return is_chair(conferences, paper.conference_id, actor) or bool(security and security["submitter_id"] == actor)


def actor_role(conn, paper_id, actor):
    if actor is None:
        return "system"
    row = conn.execute(
        "SELECT m.role FROM conference_members m JOIN submissions s ON s.conference_id=m.conference_id "
        "WHERE s.submission_id=? AND m.user_id=?", (paper_id, actor),
    ).fetchone()
    if row and row[0] == "owner":
        return "chair"
    if conn.execute("SELECT 1 FROM submission_security WHERE submission_id=? AND submitter_id=?", (paper_id, actor)).fetchone() or conn.execute(
        "SELECT 1 FROM submission_collaborators WHERE submission_id=? AND user_id=?", (paper_id, actor),
    ).fetchone():
        return "author"
    return "reviewer" if row and row[0] == "reviewer" else "participant"


def identity(actor, role, viewer, chair):
    return "Reviewer" if role == "reviewer" and actor != viewer and not chair else actor


def transition(store, conferences, paper, actor, target, *, expected_status=None, expected_revision_id=None, reason=""):
    """Call inside the shared write transaction. Re-read all eligibility there."""
    require_workflow(store)
    chair = is_chair(conferences, paper.conference_id, actor)
    if target in {"under_review", "changes_requested", "accepted", "rejected"} and not chair:
        raise HTTPException(status_code=403, detail="Conference chair permission required")
    if target in {"under_review", "changes_requested", "accepted", "rejected"}:
        intake.require_review_phase(store, paper.conference_id)
        from app.services.reviews import decision_guard
        decision_guard(store,conferences,paper,actor,target)
    if target == "submitted" and not can_edit(paper, actor, conferences, store):
        raise HTTPException(status_code=403, detail="Paper editing permission required")
    if target == "submitted":
        intake.require_window(store, paper.conference_id, requested_revision=paper.status.value == "changes_requested")
    if target == "withdrawn" and not manager(paper, actor, conferences, store):
        raise HTTPException(status_code=403, detail="Only the submitting author or chair may withdraw a paper")
    if expected_status is not None and paper.status.value != expected_status:
        raise HTTPException(status_code=409, detail="Submission state changed; reload before acting")
    current = revisions.latest(store, paper.submission_id)
    if expected_revision_id is not None and (not current or current["revision_id"] != expected_revision_id):
        raise HTTPException(status_code=409, detail="A newer revision exists; reload before acting")
    if target not in TRANSITIONS[paper.status.value]:
        raise HTTPException(status_code=409, detail="This submission status transition is not permitted")
    if target in {"submitted", "under_review"}:
        ready = eligibility(store, paper)
        if not ready["eligible"]:
            raise HTTPException(status_code=409, detail=ready["reason"])
    if target in {"changes_requested", "accepted", "rejected"} and not reason.strip():
        raise HTTPException(status_code=422, detail="A reason is required for this action")
    if target == "submitted" and paper.status.value == "changes_requested":
        request = store._connect().execute("SELECT requested_revision_id FROM submission_workflow WHERE submission_id=?", (paper.submission_id,)).fetchone()
        if not current or (request and request[0] == current["revision_id"]):
            raise HTTPException(status_code=409, detail="Upload a revised paper before resubmitting")
    if target == "under_review":
        active = store._connect().execute(
            "SELECT 1 FROM review_assignments a JOIN conference_members m ON m.user_id=a.reviewer_id "
            "JOIN users u ON u.user_id=m.user_id WHERE a.submission_id=? AND m.conference_id=? "
            "AND m.role IN ('reviewer','owner') AND u.is_active=1 AND a.status IN ('pending','accepted','completed') LIMIT 1",
            (paper.submission_id, paper.conference_id),
        ).fetchone()
        if not active:
            raise HTTPException(status_code=409, detail="Assign an eligible reviewer before starting review")
    store._connect().execute(
        "INSERT INTO submission_workflow(submission_id,requested_revision_id,decision_reason) VALUES (?,?,?) "
        "ON CONFLICT(submission_id) DO UPDATE SET "
        "requested_revision_id=CASE WHEN ?='changes_requested' THEN excluded.requested_revision_id ELSE requested_revision_id END, "
        "decision_reason=CASE WHEN ? IN ('accepted','rejected') THEN excluded.decision_reason ELSE decision_reason END",
        (paper.submission_id, current["revision_id"] if current and target == "changes_requested" else None,
         reason if target in {"accepted", "rejected"} else "", target, target),
    )
    from app.models.submission import SubmissionStatus
    result = store.update_status(paper.submission_id, SubmissionStatus(target))
    if target in {"accepted","rejected"}:
        from app.services.reviews import record_decision
        record_decision(store,paper,actor,target,current["revision_id"] if current else None,reason.strip())
    store.audit(actor, "submission.status_changed", paper.submission_id,
                details={"from": paper.status.value, "to": target, "reason": reason.strip()},
                revision_id=current["revision_id"] if current else None)
    return result


def actions(store, conferences, paper, actor):
    from app.services.reviews import can_chair
    chair = can_chair(store,conferences,paper,actor)
    result = []
    for target in sorted(TRANSITIONS[paper.status.value]):
        if target in {"under_review", "changes_requested", "accepted", "rejected"} and chair:
            result.append(target)
        elif target == "submitted" and can_edit(paper, actor, conferences, store):
            result.append(target)
        elif target == "withdrawn" and manager(paper, actor, conferences, store):
            result.append(target)
    return result
