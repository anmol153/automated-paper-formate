"""Immutable files and append-only formatting reports, scoped to a paper."""
import hashlib
import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from app.api import submission_routes as submissions_api
from app.auth import get_current_user_id, limit_requests
from app.dependencies import get_conference_store, get_notification_store, get_submission_store
from app.models.notification import NotificationType
from app.models.rules import RuleSet
from app.parsing.errors import ParseError
from app.security.files import PrivateFiles, read_upload, safe_display_name
from app.security.permissions import can_edit
from app.security.notifications import notify
from app.services.formatting import evaluate_document
from app.services import document_preview, intake, revision_diff, workflow
from app.storage import revisions
from app.storage.database import transaction
from app.storage.issue_store import get_issue_store

router = APIRouter(prefix="/api/v1/submissions/{submission_id}", tags=["revisions"])
logger = logging.getLogger(__name__)


def _comparison_check(store, revision_id, run_id):
    if run_id:
        row = store._connect().execute(
            "SELECT * FROM revision_checks WHERE revision_id=? AND run_id=?", (revision_id, run_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Saved check not found for this revision")
    else:
        row = store._connect().execute(
            "SELECT * FROM revision_checks WHERE revision_id=? ORDER BY sequence DESC LIMIT 1", (revision_id,),
        ).fetchone()
    return revisions.check_view(store, row) if row else None


@router.get("/revision-comparison")
async def compare_revisions(
    submission_id: str, request: Request,
    base_revision_id: str = Query(..., min_length=1, max_length=100),
    target_revision_id: str = Query(..., min_length=1, max_length=100),
    base_run_id: str | None = Query(None, min_length=1, max_length=100),
    target_run_id: str | None = Query(None, min_length=1, max_length=100),
    include_text: bool = False,
    store=Depends(get_submission_store), conferences=Depends(get_conference_store),
    user_id: str = Depends(get_current_user_id),
):
    submissions_api._load(submission_id, user_id, conferences, store)
    base = dict(revisions.get_revision(store, submission_id, base_revision_id))
    target = dict(revisions.get_revision(store, submission_id, target_revision_id))
    # Resolve exact immutable run IDs before parsing. Missing/failed latest runs
    # remain missing/failed; never fall back silently to an earlier success.
    before = _comparison_check(store, base_revision_id, base_run_id)
    after = _comparison_check(store, target_revision_id, target_run_id)
    def snapshot(revision, check):
        return {"revision_id": revision["revision_id"], "number": revision["number"],
                "filename": revision["filename"], "sha256": revision["sha256"],
                "check": {k: check[k] for k in ("run_id", "sequence", "created_at", "status", "engine_version")} if check else None}
    result = {"base": snapshot(base, before), "target": snapshot(target, after),
              "same_file": base["sha256"] == target["sha256"],
              "formatting": revision_diff.compare_findings(before, after, same_rules=revision_diff.same_rules(base, target)),
              "properties": revision_diff.compare_properties(before, after),
              "text": {"status": "not_requested", "hunks": []}}
    if include_text:
        limit_requests(request, "revision-text-comparison", 60, 3600, user_id=user_id)
        result["text"] = await run_in_threadpool(revision_diff.compare_text, submissions_api.SUBMISSION_FILE_DIR, base, target)
        # A membership/assignment can be revoked while extraction is running.
        submissions_api._load(submission_id, user_id, conferences, store)
    return result


def _edit(submission_id, user_id, conferences, store, *, uploading=False):
    paper = submissions_api._load(submission_id, user_id, conferences, store)
    if not can_edit(paper, user_id, conferences, store):
        raise HTTPException(status_code=403, detail="Paper editing permission required")
    if uploading and (paper.status.value in workflow.TERMINAL or (workflow.available(store) and paper.status.value == "under_review")):
        raise HTTPException(status_code=409, detail="Request changes before revising a paper under review; finalized papers are locked")
    if uploading:
        intake.require_window(store, paper.conference_id, requested_revision=paper.status.value == "changes_requested")
    return paper


@router.get("/revisions")
async def list_revisions(
    submission_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store),
    user_id: str = Depends(get_current_user_id),
):
    paper = submissions_api._load(submission_id, user_id, conferences, store)
    revisions.require_revisions(store)
    rows = store._connect().execute(
        "SELECT * FROM paper_revisions WHERE submission_id=? ORDER BY number DESC", (submission_id,),
    ).fetchall()
    editable = can_edit(paper, user_id, conferences, store)
    return {"revisions": [revisions.view(store, row) for row in rows],
            "current_revision_id": rows[0]["revision_id"] if rows else None,
            "can_upload_revision": bool(rows) and editable and intake.window(store, paper.conference_id, requested_revision=paper.status.value == "changes_requested")["allowed"] and paper.status.value not in (workflow.TERMINAL | ({"under_review"} if workflow.available(store) else set())),
            "can_recheck": bool(rows) and editable}


@router.get("/revisions/{revision_id}/file")
async def download_revision(
    submission_id: str, revision_id: str, store=Depends(get_submission_store),
    conferences=Depends(get_conference_store), user_id: str = Depends(get_current_user_id),
):
    submissions_api._load(submission_id, user_id, conferences, store)
    row = revisions.get_revision(store, submission_id, revision_id)
    path = await run_in_threadpool(PrivateFiles(submissions_api.SUBMISSION_FILE_DIR).verified,
                                  row["storage_key"], row["sha256"], row["size_bytes"])
    store.audit(user_id, "revision.downloaded", submission_id)
    return FileResponse(path, filename=row["filename"], media_type="application/octet-stream",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/revisions/{revision_id}/checks")
async def list_checks(
    submission_id: str, revision_id: str, store=Depends(get_submission_store),
    conferences=Depends(get_conference_store), user_id: str = Depends(get_current_user_id),
):
    submissions_api._load(submission_id, user_id, conferences, store)
    revisions.get_revision(store, submission_id, revision_id)
    return [revisions.check_view(store, row) for row in store._connect().execute(
        "SELECT * FROM revision_checks WHERE revision_id=? ORDER BY sequence DESC", (revision_id,),
    )]


@router.get("/revisions/{revision_id}/preview")
async def preview_revision(
    submission_id: str, revision_id: str, request: Request,
    store=Depends(get_submission_store), conferences=Depends(get_conference_store),
    user_id: str = Depends(get_current_user_id),
):
    submissions_api._load(submission_id, user_id, conferences, store)
    row = revisions.get_revision(store, submission_id, revision_id)
    limit_requests(request, "revision-pdf-preview", 60, 3600, user_id=user_id)
    data, page_count = await run_in_threadpool(document_preview.pdf_snapshot,
                                              submissions_api.SUBMISSION_FILE_DIR, dict(row))
    # Revoke access even if the assignment/membership changed during validation.
    submissions_api._load(submission_id, user_id, conferences, store)
    store.audit(user_id, "revision.previewed", submission_id, revision_id=revision_id)
    return Response(data, media_type="application/pdf", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "X-Paper-Page-Count": str(page_count),
        "Content-Disposition": "inline; filename*=UTF-8''" + quote(row["filename"], safe=""),
    })


def _replay(store, submission_id, request_key, filename, digest, parent_id, summary):
    row = store._connect().execute(
        "SELECT * FROM paper_revisions WHERE submission_id=? AND request_key=?", (submission_id, request_key),
    ).fetchone()
    if row and (row["sha256"] != digest or row["filename"] != filename
                or row["parent_revision_id"] != parent_id or row["change_summary"] != summary):
        raise HTTPException(status_code=409, detail="Upload request key was already used for different content")
    return row


@router.post("/revisions", status_code=201)
async def upload_revision(
    submission_id: str, request: Request, file: UploadFile = File(...),
    parent_revision_id: str = Form(..., min_length=1, max_length=100),
    request_key: str = Form(..., min_length=8, max_length=100),
    change_summary: str = Form("", max_length=4000),
    store=Depends(get_submission_store), conferences=Depends(get_conference_store),
    issues=Depends(get_issue_store), user_id: str = Depends(get_current_user_id),
    notifications=Depends(get_notification_store),
):
    _edit(submission_id, user_id, conferences, store, uploading=True)
    revisions.require_revisions(store)
    limit_requests(request, "conference-upload", 20, 3600, user_id=user_id)
    filename = safe_display_name(file.filename)
    data = await read_upload(file)
    digest = hashlib.sha256(data).hexdigest()
    replay = _replay(store, submission_id, request_key, filename, digest, parent_revision_id, change_summary)
    if replay:
        return revisions.view(store, replay)
    parent = revisions.latest(store, submission_id)
    if parent is None:
        raise HTTPException(status_code=409, detail="Legacy paper needs explicit revision reconciliation")
    if parent["revision_id"] != parent_revision_id:
        raise HTTPException(status_code=409, detail="A newer revision exists; reload before uploading")
    if parent["sha256"] == digest:
        raise HTTPException(status_code=409, detail="This file is identical to the current revision")
    rules = RuleSet.model_validate_json(parent["rules_json"])
    try:
        assessment = await run_in_threadpool(evaluate_document, rules, data, filename)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    files = PrivateFiles(submissions_api.SUBMISSION_FILE_DIR)
    key, sha256 = files.put(data)
    committed = False
    try:
        with transaction(store, conferences, issues, notifications):
            paper = _edit(submission_id, user_id, conferences, store, uploading=True)
            replay = _replay(store, submission_id, request_key, filename, digest, parent_revision_id, change_summary)
            if replay:
                return revisions.view(store, replay)
            current = revisions.latest(store, submission_id)
            if current["revision_id"] != parent_revision_id:
                raise HTTPException(status_code=409, detail="A newer revision exists; reload before uploading")
            row = revisions.append_revision(store, paper, user_id, filename, key, sha256, len(data),
                                            rules, assessment, parent, change_summary, request_key)
            revisions.append_check(store, row, user_id, assessment, issue_store=issues)
            # Previous reviewer feedback remains retained, but is no longer a verdict on this file.
            store._connect().execute("UPDATE submissions SET verdict=NULL WHERE submission_id=?", (submission_id,))
            store.audit(user_id, "revision.uploaded", submission_id, revision_id=row["revision_id"], details={"number": row["number"]})
            notify(notifications, store, conferences, paper, user_id, NotificationType.SUBMISSION_UPDATE, "New paper revision")
        committed = True
    finally:
        if not committed:
            files.discard(key)
    return revisions.view(store, row)


async def perform_check(submission_id, revision_id, request, user_id, conferences, store, notifications):
    _edit(submission_id, user_id, conferences, store)
    limit_requests(request, "conference-recheck", 20, 3600, user_id=user_id)
    row = revisions.get_revision(store, submission_id, revision_id) if revision_id else revisions.latest(store, submission_id)
    if row is None:
        raise HTTPException(status_code=409, detail="Legacy paper needs explicit revision reconciliation")
    rules = RuleSet.model_validate_json(row["rules_json"])
    assessment = None
    error = None
    try:
        files = PrivateFiles(submissions_api.SUBMISSION_FILE_DIR)
        path = await run_in_threadpool(files.verified, row["storage_key"], row["sha256"], row["size_bytes"])
        data = await run_in_threadpool(path.read_bytes)
        # Verify the bytes actually passed to the parser, too.
        if len(data) != row["size_bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise HTTPException(status_code=409, detail="Stored file failed its integrity check")
        assessment = await run_in_threadpool(evaluate_document, rules, data, row["filename"])
    except ParseError:
        error = "The saved document could not be parsed; previous reports remain available."
    except HTTPException as exc:
        error = str(exc.detail)
    except Exception:
        logger.exception("Revision formatting check failed")
        error = "Formatting validation failed; retry later. Previous reports remain available."
    with transaction(store, conferences, notifications):
        paper = _edit(submission_id, user_id, conferences, store)
        run_id = revisions.append_check(store, row, user_id, assessment, error)
        store.audit(user_id, "formatting.completed" if assessment else "formatting.failed", submission_id, revision_id=row["revision_id"])
        notify(notifications, store, conferences, paper, user_id, NotificationType.SUBMISSION_UPDATE, "Formatting check completed" if assessment else "Formatting check needs attention")
    result = store._connect().execute("SELECT * FROM revision_checks WHERE run_id=?", (run_id,)).fetchone()
    return revisions.check_view(store, result)
