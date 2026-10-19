"""Existing conference workflow with explicit paper-level authorization."""
import logging
import os
from pathlib import Path

from app.api.template_routes import get_template_version_store
from app.auth import get_current_user_id, limit_requests
from app.config import BACKEND_DIR, get_settings
from app.dependencies import (
    get_conference_store,
    get_notification_store,
    get_submission_store,
)
from app.models.conference import ConferenceRole
from app.models.notification import NotificationType
from app.models.intake import PaperMetadata, BibliographicAuthor
from pydantic import ValidationError
from app.models.submission import (
    DiscussionThread,
    ReviewAssignment,
    ReviewVerdict,
    Submission,
    SubmissionStatus,
)
from app.parsing.errors import ParseError
from app.security.files import (
    PrivateFiles,
    read_upload,
    safe_display_name,
)
from app.security.notifications import notify
from app.security.permissions import (
    can_read,
    is_assigned_reviewer,
    require_chair,
    require_read,
    submission_view,
    thread_view,
)
from app.storage.conference_store import ConferenceNotFound, ConferenceStore
from app.storage.database import transaction
from app.storage import revisions
from app.services.formatting import evaluate_document, validation_status
from app.services import intake, workflow, reviews
from app.storage.issue_store import IssueStore, get_issue_store
from app.storage.notification_store import NotificationStore
from app.storage.submission_store import SubmissionNotFound, SubmissionStore
from app.storage.template_version_store import (
    TemplateVersionNotFound,
    TemplateVersionStore,
)
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
SUBMISSION_FILE_DIR = Path(os.environ.get("SUBMISSION_FILE_DIR", str(get_settings().submission_file_dir or BACKEND_DIR / "data" / "submissions")))
router = APIRouter(prefix="/api/v1", tags=["submissions"])


def _load(submission_id, user_id, conferences, submissions):
    try:
        paper = submissions.get(submission_id)
    except SubmissionNotFound as exc:
        raise HTTPException(status_code=404, detail="Submission not found") from exc
    require_read(paper, user_id, conferences, submissions)
    return paper


def _member(conf_id, user_id, conferences):
    try:
        conferences.get(conf_id)
    except ConferenceNotFound as exc:
        raise HTTPException(status_code=404, detail="Conference not found") from exc
    if not conferences.user_has_role(conf_id, user_id, ConferenceRole.AUTHOR):
        raise HTTPException(status_code=403, detail="Conference membership required")


@router.post("/conferences/{conf_id}/submissions", status_code=201, response_model=Submission)
async def create_submission(
    conf_id: str, request: Request, file: UploadFile = File(...),
    submit_for_review: bool = Form(True),
    metadata_json: str | None = Form(None, max_length=50000),
    conference_store: ConferenceStore = Depends(get_conference_store),
    submission_store: SubmissionStore = Depends(get_submission_store),
    template_version_store: TemplateVersionStore = Depends(get_template_version_store),
    issue_store: IssueStore = Depends(get_issue_store),
    notification_store: NotificationStore = Depends(get_notification_store),
    current_user_id: str = Depends(get_current_user_id),
):
    _member(conf_id, current_user_id, conference_store)
    revisions.require_revisions(submission_store)
    intake.require_window(submission_store, conf_id)
    details = None
    if metadata_json is not None:
        intake.require_intake(submission_store)
        try:
            details = PaperMetadata.model_validate_json(metadata_json)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="Invalid paper metadata: check title, abstract, author list and track fields") from exc
        intake.validate_track(submission_store, conf_id, details.track_id)
    limit_requests(request, "conference-upload", 20, 3600, user_id=current_user_id)
    try:
        rules = template_version_store.get_latest(conf_id)
    except TemplateVersionNotFound as exc:
        raise HTTPException(status_code=404, detail="Conference has no template") from exc
    filename = safe_display_name(file.filename)
    try:
        data = await read_upload(file)
        assessment = await run_in_threadpool(evaluate_document, rules, data, filename)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if details is None and intake.available(submission_store):
        extracted = assessment.metadata
        title = extracted.title if extracted and len(extracted.title) <= 500 else ""
        authors = extracted.authors if extracted and len(extracted.authors) <= 50 and all(0 < len(a.strip()) <= 200 for a in extracted.authors) else []
        details = PaperMetadata(title=title, authors=[BibliographicAuthor(name=a) for a in authors])
    private_files = PrivateFiles(SUBMISSION_FILE_DIR)
    key, sha256 = private_files.put(data)
    try:
        with transaction(submission_store, issue_store, conference_store, template_version_store, notification_store):
            _member(conf_id, current_user_id, conference_store)
            intake.require_window(submission_store, conf_id)
            if details is not None:
                intake.validate_track(submission_store, conf_id, details.track_id)
            submission = submission_store.create(conf_id, rules.template_id, filename)
            submission_store.secure(submission.submission_id, current_user_id, key, sha256, len(data))
            submission_store.update_verdict(submission.submission_id, None, score=assessment.score)
            submission_store.update_status(submission.submission_id, SubmissionStatus.SUBMITTED)
            if not submit_for_review or (details is not None and intake.missing_fields(intake.configuration(submission_store, conf_id)["settings"], details)) or (workflow.available(submission_store) and (
                validation_status(assessment) == "unable_to_validate" or
                (workflow.policy(submission_store, conf_id) == "block_errors" and validation_status(assessment) == "failed")
            )):
                submission_store.update_status(submission.submission_id, SubmissionStatus.DRAFT)
            revision = revisions.append_revision(
                submission_store, submission_store.get(submission.submission_id), current_user_id,
                filename, key, sha256, len(data), rules, assessment,
            )
            revisions.append_check(submission_store, revision, current_user_id, assessment, issue_store=issue_store)
            if details is not None:
                intake.append_metadata(submission_store, submission, details, current_user_id, revision["revision_id"],
                                       source="declared" if metadata_json is not None else "extracted", expected_version=0)
            submission_store.audit(current_user_id, "submission.created", submission.submission_id, revision_id=revision["revision_id"])
            notify(notification_store, submission_store, conference_store, submission, current_user_id, NotificationType.SUBMISSION_UPDATE, "New conference paper")
    except BaseException:
        private_files.discard(key)
        raise
    return submission_view(submission_store.get(submission.submission_id), current_user_id, conference_store, submission_store)


@router.get("/conferences/{conf_id}/submissions", response_model=list[Submission])
async def list_submissions(
    conf_id: str, q: str | None = None, track_id: str | None = None,
    conference_store: ConferenceStore = Depends(get_conference_store),
    submission_store: SubmissionStore = Depends(get_submission_store),
    current_user_id: str = Depends(get_current_user_id),
):
    _member(conf_id, current_user_id, conference_store)
    return [submission_view(paper, current_user_id, conference_store, submission_store)
            for paper in submission_store.list_by_conference(conf_id)
            if can_read(paper, current_user_id, conference_store, submission_store)
            and (not track_id or paper.track_id == track_id)
            and (not q or q.casefold() in f"{paper.filename} {paper.title} #{paper.paper_number or ''}".casefold())]


@router.get("/submissions/{submission_id}/file")
async def download_submission_file(
    submission_id: str,
    submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    current_user_id: str = Depends(get_current_user_id),
):
    paper = _load(submission_id, current_user_id, conference_store, submission_store)
    security = submission_store.security(submission_id)
    if security and security["storage_key"]:
        path = PrivateFiles(SUBMISSION_FILE_DIR).verified(security["storage_key"], security["sha256"], security["size_bytes"])
    else:
        # Legacy records are chair-only, and their original filenames are never trusted.
        safe_display_name(paper.filename)
        root = SUBMISSION_FILE_DIR.resolve()
        path = root / submission_id / paper.filename
        if not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
    submission_store.audit(current_user_id, "submission.downloaded", submission_id)
    return FileResponse(path, filename=paper.filename, media_type="application/octet-stream",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/submissions/{submission_id}", response_model=Submission)
async def get_submission(
    submission_id: str, submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    current_user_id: str = Depends(get_current_user_id),
):
    return submission_view(_load(submission_id, current_user_id, conference_store, submission_store), current_user_id, conference_store, submission_store)


@router.patch("/submissions/{submission_id}", response_model=Submission)
async def update_submission_status(
    submission_id: str, status: SubmissionStatus = Body(...),
    submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    current_user_id: str = Depends(get_current_user_id),
):
    with transaction(submission_store, conference_store):
        paper = _load(submission_id, current_user_id, conference_store, submission_store)
        require_chair(paper, current_user_id, conference_store, submission_store)
        if workflow.available(submission_store):
            updated = workflow.transition(submission_store, conference_store, paper, current_user_id, status.value)
        else:
            raise HTTPException(status_code=409, detail="Activate Phase 3 to change submission status safely")
    return updated


@router.post("/submissions/{submission_id}/review", status_code=201, response_model=ReviewAssignment)
async def assign_reviewer(
    submission_id: str, reviewer_id: str = Body(...),
    submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    notification_store: NotificationStore = Depends(get_notification_store),
    current_user_id: str = Depends(get_current_user_id),
):
    with transaction(submission_store, conference_store, notification_store):
        paper = _load(submission_id, current_user_id, conference_store, submission_store)
        require_chair(paper, current_user_id, conference_store, submission_store)
        intake.require_review_phase(submission_store, paper.conference_id)
        if not conference_store.user_has_role(paper.conference_id, reviewer_id, ConferenceRole.REVIEWER):
            raise HTTPException(status_code=400, detail="Reviewer is not eligible")
        security = submission_store.security(submission_id)
        if not security or not security["submitter_id"]:
            raise HTTPException(status_code=409, detail="Reconcile legacy ownership before assigning reviewers")
        if security["submitter_id"] == reviewer_id or submission_store._connect().execute(
            "SELECT 1 FROM submission_collaborators WHERE submission_id=? AND user_id=?", (submission_id, reviewer_id),
        ).fetchone():
            raise HTTPException(status_code=409, detail="An author cannot review their own submission")
        if any(a.reviewer_id == reviewer_id and a.status in {"pending", "accepted", "completed"} for a in submission_store.list_assignments(submission_id)):
            raise HTTPException(status_code=409, detail="Reviewer is already assigned")
        user = submission_store._connect().execute("SELECT is_active FROM users WHERE user_id=?", (reviewer_id,)).fetchone()
        if not user or not user[0]:
            raise HTTPException(status_code=400, detail="Reviewer account is unavailable")
        if workflow.available(submission_store):
            if paper.status.value not in {"submitted", "under_review"}:
                raise HTTPException(status_code=409, detail="Paper must be submitted before assigning reviewers")
            ready = workflow.eligibility(submission_store, paper)
            if not ready["eligible"]:
                raise HTTPException(status_code=409, detail=ready["reason"])
        if reviews.available(submission_store):
            if reviews.conflicted(submission_store, submission_id, reviewer_id):
                raise HTTPException(status_code=409, detail="Reviewer has an active conflict of interest")
            reviews.ensure_configured(submission_store, paper.conference_id, current_user_id)
        assignment = submission_store.assign_reviewer(submission_id, reviewer_id, current_user_id)
        if workflow.available(submission_store) and paper.status != SubmissionStatus.UNDER_REVIEW:
            workflow.transition(submission_store, conference_store, paper, current_user_id, "under_review")
        elif not workflow.available(submission_store):
            submission_store.update_status(submission_id, SubmissionStatus.UNDER_REVIEW)
        submission_store.audit(current_user_id, "reviewer.assigned", submission_id)
        notification_store.create(reviewer_id, NotificationType.REVIEW_ASSIGNMENT, "New review assignment", "A paper is ready for your review", related_id=submission_id)
    return assignment


@router.post("/submissions/{submission_id}/check-compliance")
async def run_compliance_check(
    submission_id: str, request: Request, revision_id: str | None = Body(None, embed=True),
    submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    notification_store: NotificationStore = Depends(get_notification_store),
    current_user_id: str = Depends(get_current_user_id),
):
    from app.api.revision_routes import perform_check
    return await perform_check(submission_id, revision_id, request, current_user_id, conference_store, submission_store, notification_store)


@router.post("/submissions/{submission_id}/verdict", response_model=Submission)
async def set_reviewer_verdict(
    submission_id: str, verdict: ReviewVerdict = Body(...), score: int = Body(..., ge=0, le=100),
    submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    current_user_id: str = Depends(get_current_user_id),
):
    with transaction(submission_store, conference_store):
        paper = _load(submission_id, current_user_id, conference_store, submission_store)
        if not is_assigned_reviewer(paper, current_user_id, conference_store, submission_store):
            raise HTTPException(status_code=403, detail="An active reviewer assignment is required")
        if reviews.available(submission_store) and submission_store._connect().execute("SELECT 1 FROM formal_reviews WHERE submission_id=?",(submission_id,)).fetchone():
            raise HTTPException(status_code=409, detail="This paper uses formal reviews; use the revision-bound review form")
        # Compatibility endpoint; formal review records and academic scores arrive in phase 4.
        submission_store._connect().execute(
            "INSERT INTO legacy_review_feedback VALUES (?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now')) "
            "ON CONFLICT(submission_id,reviewer_id) DO UPDATE SET verdict=excluded.verdict, score=excluded.score, updated_at=excluded.updated_at",
            (submission_id, current_user_id, verdict.value, score),
        )
        updated = submission_store.update_verdict(submission_id, verdict, paper.compliance_score)
        submission_store.audit(current_user_id, "reviewer.verdict_recorded", submission_id)
    return submission_view(updated, current_user_id, conference_store, submission_store)


@router.post("/submissions/{submission_id}/discussion", status_code=201, response_model=DiscussionThread)
async def add_discussion_message(
    submission_id: str, text: str = Body(..., min_length=1, max_length=20000),
    author_id: str | None = Body(None),
    submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    notification_store: NotificationStore = Depends(get_notification_store),
    current_user_id: str = Depends(get_current_user_id),
):
    if author_id is not None and author_id != current_user_id:
        raise HTTPException(status_code=403, detail="Cannot post as another user")
    with transaction(submission_store, conference_store, notification_store):
        paper = _load(submission_id, current_user_id, conference_store, submission_store)
        thread = submission_store.get_thread_for_submission(submission_id)
        submission_store.add_message(thread.thread_id, current_user_id, text)
        submission_store.audit(current_user_id, "discussion.comment_added", submission_id)
        notify(notification_store, submission_store, conference_store, paper, current_user_id, NotificationType.DISCUSSION_MENTION, "New discussion message")
    # Do not broadcast private paper information to conference-wide notifications.
    return thread_view(submission_store.get_thread(thread.thread_id), paper, current_user_id, conference_store, submission_store)


@router.get("/submissions/{submission_id}/discussion", response_model=DiscussionThread)
async def get_discussion_thread(
    submission_id: str, submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    current_user_id: str = Depends(get_current_user_id),
):
    paper = _load(submission_id, current_user_id, conference_store, submission_store)
    row = submission_store._connect().execute("SELECT thread_id FROM discussion_threads WHERE submission_id=?", (submission_id,)).fetchone()
    if row is None:
        return DiscussionThread(thread_id="", submission_id=submission_id, author_id="", title="Conversation", messages=[])
    return thread_view(submission_store.get_thread(row[0]), paper, current_user_id, conference_store, submission_store)
