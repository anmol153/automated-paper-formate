"""Conference management with atomic ownership and membership changes."""
from app.auth import get_current_user_id
from app.dependencies import get_conference_store
from app.models.conference import Conference, ConferenceMember, ConferenceRole
from app.security.permissions import is_chair
from app.storage.conference_store import (
    ConferenceMemberNotFound,
    ConferenceNotFound,
    ConferenceStore,
)
from app.storage.database import MigrationRequired, transaction
from fastapi import APIRouter, Body, Depends, HTTPException

router = APIRouter(prefix="/api/v1/conferences", tags=["conferences"])


def _chair(conferences, conf_id, user_id):
    if not is_chair(conferences, conf_id, user_id):
        raise HTTPException(status_code=403, detail="Conference chair permission required")


def _audit(store, actor, action, target):
    store._connect().execute("INSERT INTO security_events(actor_id,action,target_id,created_at) VALUES (?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))", (actor, action, target))


def _chair_view(store, conference):
    members = store.list_members(conference.conference_id)
    return conference.model_copy(update={
        "members": members,
        "owners": [member.user_id for member in members if member.role == ConferenceRole.OWNER],
    })


def _retain_chair(store, conf_id, user_id):
    if is_chair(store, conf_id, user_id):
        owners = sum(member.role == ConferenceRole.OWNER for member in store.list_members(conf_id))
        if owners <= 1:
            raise HTTPException(status_code=409, detail="Conference must retain at least one chair")


@router.post("", status_code=201, response_model=Conference, include_in_schema=False)
@router.post("/", status_code=201, response_model=Conference)
async def create_conference(
    name: str = Body(..., min_length=1, max_length=200), description: str = Body("", max_length=20000),
    conference_store: ConferenceStore = Depends(get_conference_store),
    current_user_id: str = Depends(get_current_user_id),
):
    if not name.strip():
        raise HTTPException(status_code=422, detail="Conference name must not be empty")
    with transaction(conference_store):
        if not conference_store._connect().execute("SELECT 1 FROM users WHERE user_id=?", (current_user_id,)).fetchone():
            raise MigrationRequired("Conference writes require a unified WORKFLOW_DB_PATH; see PHASE1.md")
        conf = conference_store.create(name=name, description=description)
        conference_store.add_member(conf.conference_id, current_user_id, ConferenceRole.OWNER)
        _audit(conference_store, current_user_id, "conference.created", conf.conference_id)
    return _chair_view(conference_store, conference_store.get(conf.conference_id))


@router.get("", response_model=list[Conference], include_in_schema=False)
@router.get("/", response_model=list[Conference])
async def list_conferences(q: str | None = None, conference_store: ConferenceStore = Depends(get_conference_store)):
    return [conference.model_copy(update={"members": [], "owners": []}) for conference in conference_store.list_conferences(query=q)]


@router.get("/{conf_id}", response_model=Conference)
async def get_conference(conf_id: str, conference_store: ConferenceStore = Depends(get_conference_store),
                         current_user_id: str = Depends(get_current_user_id)):
    try:
        conference = conference_store.get(conf_id)
        conference_store.get_member(conf_id, current_user_id)
    except (ConferenceNotFound, ConferenceMemberNotFound) as exc:
        raise HTTPException(status_code=404, detail="Conference not found") from exc
    return _chair_view(conference_store, conference) if is_chair(conference_store, conf_id, current_user_id) else conference.model_copy(update={"members": [], "owners": []})


@router.patch("/{conf_id}", response_model=Conference)
async def update_conference(
    conf_id: str, description: str | None = Body(None, max_length=20000), name: str | None = Body(None, max_length=200),
    conference_store: ConferenceStore = Depends(get_conference_store), current_user_id: str = Depends(get_current_user_id),
):
    if name is not None and not name.strip():
        raise HTTPException(status_code=422, detail="Conference name must not be empty")
    with transaction(conference_store):
        _chair(conference_store, conf_id, current_user_id)
        result = conference_store.update(conf_id, name=name, description=description)
        _audit(conference_store, current_user_id, "conference.updated", conf_id)
    return _chair_view(conference_store, result)


@router.post("/{conf_id}/members", status_code=201, response_model=ConferenceMember)
async def add_conference_member(
    conf_id: str, user_id: str = Body(...), role: ConferenceRole = Body(ConferenceRole.AUTHOR),
    conference_store: ConferenceStore = Depends(get_conference_store), current_user_id: str = Depends(get_current_user_id),
):
    with transaction(conference_store):
        _chair(conference_store, conf_id, current_user_id)
        user = conference_store._connect().execute("SELECT is_active FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user or not user[0]:
            raise HTTPException(status_code=400, detail="Participant account is unavailable")
        if role != ConferenceRole.OWNER:
            _retain_chair(conference_store, conf_id, user_id)
        member = conference_store.add_member(conf_id, user_id, role)
        _audit(conference_store, current_user_id, "conference.member_updated", conf_id)
    return member


@router.delete("/{conf_id}/members/{user_id}", status_code=204)
async def remove_conference_member(
    conf_id: str, user_id: str, conference_store: ConferenceStore = Depends(get_conference_store),
    current_user_id: str = Depends(get_current_user_id),
):
    with transaction(conference_store):
        _chair(conference_store, conf_id, current_user_id)
        _retain_chair(conference_store, conf_id, user_id)
        conference_store.remove_member(conf_id, user_id)
        _audit(conference_store, current_user_id, "conference.member_removed", conf_id)
