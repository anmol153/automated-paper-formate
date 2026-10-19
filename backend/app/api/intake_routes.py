"""Versioned conference intake configuration, tracks and bibliographic metadata."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.submission_routes import _load, _member
from app.auth import get_current_user_id
from app.dependencies import get_conference_store, get_submission_store
from app.models.intake import ConfigureConference, SaveMetadata, TrackFields, UpdateTrack
from app.security.permissions import is_chair, paper_chair
from app.services import intake, workflow
from app.storage import revisions
from app.storage.database import transaction

router = APIRouter(prefix="/api/v1", tags=["conference intake"])


def _chair(conferences, conf_id, actor):
    _member(conf_id, actor, conferences)
    if not is_chair(conferences, conf_id, actor):
        raise HTTPException(status_code=403, detail="Conference chair permission required")


def configuration_view(store, conferences, conf_id, actor):
    result = intake.configuration(store, conf_id)
    return {"enabled": intake.available(store), "version": result["version"],
            "settings": result["settings"].model_dump(mode="json"), "tracks": intake.tracks(store, conf_id),
            "can_configure": is_chair(conferences, conf_id, actor), "submission_window": intake.window(store, conf_id),
            "requested_revision_window": intake.window(store, conf_id, requested_revision=True)}


@router.get("/conferences/{conf_id}/settings")
async def get_settings(conf_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    _member(conf_id, actor, conferences)
    return configuration_view(store, conferences, conf_id, actor)


@router.put("/conferences/{conf_id}/settings")
async def configure(conf_id: str, body: ConfigureConference, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences):
        _chair(conferences, conf_id, actor)
        intake.configure(store, conf_id, body, actor)
        store.audit(actor, "conference.settings_changed", conf_id, details={"version": body.expected_version + 1})
    return configuration_view(store, conferences, conf_id, actor)


@router.get("/conferences/{conf_id}/tracks")
async def get_tracks(conf_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    _member(conf_id, actor, conferences)
    return intake.tracks(store, conf_id)


@router.post("/conferences/{conf_id}/tracks", status_code=201)
async def create_track(conf_id: str, body: TrackFields, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences):
        _chair(conferences, conf_id, actor)
        result = intake.save_track(store, conf_id, body)
        store.audit(actor, "conference.track_created", conf_id, details={"track_id": result["track_id"]})
    return result


@router.put("/conferences/{conf_id}/tracks/{track_id}")
async def update_track(conf_id: str, track_id: str, body: UpdateTrack, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences):
        _chair(conferences, conf_id, actor)
        result = intake.save_track(store, conf_id, body, track_id)
        store.audit(actor, "conference.track_updated", conf_id, details={"track_id": track_id, "version": result["version"]})
    return result


def can_edit_metadata(store, conferences, paper, actor):
    security = store.security(paper.submission_id)
    return bool(security and security["submitter_id"] == actor) or paper_chair(paper, actor, conferences, store) or bool(store._connect().execute(
        "SELECT 1 FROM submission_collaborators WHERE submission_id=? AND user_id=? AND can_edit=1", (paper.submission_id, actor),
    ).fetchone())


@router.get("/submissions/{submission_id}/metadata")
async def get_metadata(submission_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    paper = _load(submission_id, actor, conferences, store)
    gate = intake.window(store, paper.conference_id, requested_revision=paper.status.value == "changes_requested")
    enabled = intake.available(store)
    return {"enabled": enabled, "metadata": intake.metadata(store, submission_id), "paper_number": paper.paper_number,
            "tracks": intake.tracks(store, paper.conference_id), "edit_window": gate,
            "can_edit": enabled and paper.status.value in {"draft", "submitted", "changes_requested"} and gate["allowed"] and can_edit_metadata(store, conferences, paper, actor)}


@router.put("/submissions/{submission_id}/metadata")
async def save_metadata(submission_id: str, body: SaveMetadata, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences):
        paper = _load(submission_id, actor, conferences, store)
        intake.require_intake(store)
        if not can_edit_metadata(store, conferences, paper, actor):
            raise HTTPException(status_code=403, detail="Paper editing permission required")
        if paper.status.value in workflow.TERMINAL or paper.status.value == "under_review":
            raise HTTPException(status_code=409, detail="Request changes before editing metadata under review; finalized papers are locked")
        intake.require_window(store, paper.conference_id, requested_revision=paper.status.value == "changes_requested")
        current = revisions.latest(store, submission_id)
        if not current or current["revision_id"] != body.expected_revision_id:
            raise HTTPException(status_code=409, detail="The current paper revision changed or needs reconciliation; reload before saving")
        result = intake.append_metadata(store, paper, body, actor, current["revision_id"], expected_version=body.expected_version)
        store.audit(actor, "submission.metadata_changed", submission_id, revision_id=current["revision_id"], details={"version": result["version"]})
    return result


@router.get("/submissions/{submission_id}/metadata/history")
async def metadata_history(submission_id: str, before_version: int | None = Query(None, ge=1), limit: int = Query(20, ge=1, le=50),
                           store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    _load(submission_id, actor, conferences, store)
    intake.require_intake(store)
    rows = store._connect().execute(
        "SELECT * FROM submission_metadata_versions WHERE submission_id=? AND (? IS NULL OR version<?) ORDER BY version DESC LIMIT ?",
        (submission_id, before_version, before_version, limit),
    ).fetchall()
    return [intake.metadata_view(row) for row in rows]
