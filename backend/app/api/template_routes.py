"""Immutable conference templates with scoped reads and chair-only writes."""
from app.auth import get_current_user_id
from app.dependencies import get_conference_store
from app.models.rules import RuleSet
from app.security.permissions import is_chair
from app.storage.conference_store import (
    ConferenceMemberNotFound,
    ConferenceNotFound,
    ConferenceStore,
)
from app.storage.database import transaction
from app.storage.template_version_store import (
    TemplateVersionNotFound,
    TemplateVersionStore,
)
from app.utils.diff_engine import diff_rulesets, summary_diff
from fastapi import APIRouter, Body, Depends, HTTPException

router = APIRouter(prefix="/api/v1/conferences", tags=["templates"])


def get_template_version_store(conference_store: ConferenceStore = Depends(get_conference_store)):
    return TemplateVersionStore(conference_store)


def _member(conferences, conf_id, user_id):
    try:
        conferences.get(conf_id)
        conferences.get_member(conf_id, user_id)
    except (ConferenceMemberNotFound, ConferenceNotFound) as exc:
        raise HTTPException(status_code=404, detail="Conference not found") from exc


def _version(versions, conf_id, template_id):
    try:
        return versions.get_version(conf_id, template_id)
    except TemplateVersionNotFound as exc:
        raise HTTPException(status_code=404, detail="Template version not found") from exc


@router.post("/{conf_id}/templates", status_code=201, response_model=RuleSet)
async def create_template_version(
    conf_id: str, rules: RuleSet,
    conference_store: ConferenceStore = Depends(get_conference_store),
    template_version_store: TemplateVersionStore = Depends(get_template_version_store),
    current_user_id: str = Depends(get_current_user_id),
):
    with transaction(conference_store, template_version_store):
        _member(conference_store, conf_id, current_user_id)
        if not is_chair(conference_store, conf_id, current_user_id):
            raise HTTPException(status_code=403, detail="Only chairs can create conference templates")
        saved = template_version_store.save(rules, conf_id, rules.name)
        template_version_store._connect().execute(
            "INSERT INTO security_events(actor_id,action,target_id,created_at) VALUES (?, 'template.version_created', ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
            (current_user_id, saved.template_id),
        )
    return saved


@router.get("/{conf_id}/templates", response_model=list[tuple[str, str, str]])
async def list_template_versions(
    conf_id: str, conference_store: ConferenceStore = Depends(get_conference_store),
    template_version_store: TemplateVersionStore = Depends(get_template_version_store),
    current_user_id: str = Depends(get_current_user_id),
):
    _member(conference_store, conf_id, current_user_id)
    return template_version_store.list_versions(conf_id)


@router.get("/{conf_id}/templates/latest", response_model=RuleSet)
async def get_latest_template_version(
    conf_id: str, conference_store: ConferenceStore = Depends(get_conference_store),
    template_version_store: TemplateVersionStore = Depends(get_template_version_store),
    current_user_id: str = Depends(get_current_user_id),
):
    _member(conference_store, conf_id, current_user_id)
    try:
        return template_version_store.get_latest(conf_id)
    except TemplateVersionNotFound as exc:
        raise HTTPException(status_code=404, detail="Template version not found") from exc


@router.get("/{conf_id}/templates/{template_id}", response_model=RuleSet)
async def get_template_version(
    conf_id: str, template_id: str, conference_store: ConferenceStore = Depends(get_conference_store),
    template_version_store: TemplateVersionStore = Depends(get_template_version_store),
    current_user_id: str = Depends(get_current_user_id),
):
    _member(conference_store, conf_id, current_user_id)
    return _version(template_version_store, conf_id, template_id)


@router.post("/{conf_id}/templates/diff")
async def diff_template_versions(
    conf_id: str, old_template_id: str = Body(...), new_template_id: str = Body(...),
    conference_store: ConferenceStore = Depends(get_conference_store),
    template_version_store: TemplateVersionStore = Depends(get_template_version_store),
    current_user_id: str = Depends(get_current_user_id),
):
    _member(conference_store, conf_id, current_user_id)
    diff = diff_rulesets(_version(template_version_store, conf_id, old_template_id),
                         _version(template_version_store, conf_id, new_template_id))
    return {"old_template_id": old_template_id, "new_template_id": new_template_id,
            "summary": summary_diff(diff), "diff": diff}
            