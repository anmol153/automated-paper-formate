"""Object-level authorization. Conference membership alone never grants paper access."""
from fastapi import HTTPException

from app.models.conference import ConferenceRole
from app.storage.conference_store import ConferenceMemberNotFound
from app.storage.database import require_security_schema


def is_chair(conferences, conference_id, user_id):
    try:
        return conferences.get_member(conference_id, user_id).role == ConferenceRole.OWNER
    except ConferenceMemberNotFound:
        return False


def can_read(submission, user_id, conferences, submissions):
    require_security_schema(submissions._connect())
    try:
        member = conferences.get_member(submission.conference_id, user_id)
    except ConferenceMemberNotFound:
        return False
    if member.role == ConferenceRole.OWNER:
        return True
    security = submissions.security(submission.submission_id)
    # Ownership of legacy submissions is deliberately not inferred.
    if not security or security["submitter_id"] is None:
        return False
    if security["submitter_id"] == user_id:
        return True
    if submissions._connect().execute(
        "SELECT 1 FROM submission_collaborators WHERE submission_id=? AND user_id=?",
        (submission.submission_id, user_id),
    ).fetchone():
        return True
    return member.role == ConferenceRole.REVIEWER and bool(submissions._connect().execute(
        "SELECT 1 FROM review_assignments WHERE submission_id=? AND reviewer_id=? "
        "AND status IN ('pending','accepted','completed')", (submission.submission_id, user_id),
    ).fetchone())


def require_read(submission, user_id, conferences, submissions):
    if not can_read(submission, user_id, conferences, submissions):
        raise HTTPException(status_code=404, detail="Submission not found")


def require_chair(submission, user_id, conferences, submissions):
    require_read(submission, user_id, conferences, submissions)
    if not paper_chair(submission, user_id, conferences, submissions):
        raise HTTPException(status_code=403, detail="Conference chair permission required")


def paper_chair(submission, user_id, conferences, submissions):
    from app.services.reviews import can_chair
    return can_chair(submissions, conferences, submission, user_id)


def can_edit(submission, user_id, conferences, submissions):
    if not can_read(submission, user_id, conferences, submissions):
        return False
    if is_chair(conferences, submission.conference_id, user_id):
        return True
    security = submissions.security(submission.submission_id)
    if security and security["submitter_id"] == user_id:
        return True
    return bool(submissions._connect().execute(
        "SELECT 1 FROM submission_collaborators WHERE submission_id=? AND user_id=? AND can_edit=1",
        (submission.submission_id, user_id),
    ).fetchone())


def is_assigned_reviewer(submission, user_id, conferences, submissions):
    return can_read(submission, user_id, conferences, submissions) and bool(submissions._connect().execute(
        "SELECT 1 FROM review_assignments WHERE submission_id=? AND reviewer_id=? "
        "AND status IN ('pending','accepted')", (submission.submission_id, user_id),
    ).fetchone())


def submission_view(submission, user_id, conferences, submissions=None):
    """Reviewer identities and unreleased recommendations stay chair-only."""
    if (paper_chair(submission, user_id, conferences, submissions) if submissions else is_chair(conferences, submission.conference_id, user_id)):
        return submission
    return submission.model_copy(update={"reviewer_id": None, "verdict": None})


def thread_view(thread, submission, user_id, conferences, submissions):
    if paper_chair(submission, user_id, conferences, submissions):
        return thread
    reviewers = {a.reviewer_id for a in submissions.list_assignments(submission.submission_id)}
    def identity(author):
        return "Reviewer" if author in reviewers and author != user_id else author
    return thread.model_copy(update={
        "author_id": identity(thread.author_id),
        "messages": [{**message, "author": identity(message.get("author", ""))} for message in thread.messages],
    })
