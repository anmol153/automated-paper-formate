"""Conference management with atomic ownership and membership changes."""
from app.auth import get_current_user_id, limit_requests
from app.dependencies import get_conference_store
from app.models.conference import Conference, ConferenceMember, ConferenceRole
from app.security.permissions import is_chair
from app.storage.conference_store import (
    ConferenceMemberNotFound,
    ConferenceNotFound,
    ConferenceStore,
)
from app.storage.database import MigrationRequired, transaction
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/api/v1/conferences", tags=["conferences"])


@router.post("/{conf_id}/access-requests", status_code=201)
async def request_conference_access(conf_id: str, request: Request, role: str = Body("author", embed=True),
                                    conference_store: ConferenceStore = Depends(get_conference_store),
                                    current_user_id: str = Depends(get_current_user_id)):
    if role not in {"author", "reviewer"}:
        raise HTTPException(status_code=422, detail="Choose Author or Reviewer")
    if not conference_store.exists(conf_id):
        raise HTTPException(status_code=404, detail="Conference not found")
    try:
        conference_store.get_member(conf_id, current_user_id)
    except ConferenceMemberNotFound:
        pass
    else:
        raise HTTPException(status_code=409, detail="You are already a conference member")
    limit_requests(request, "conference-access-request", 5, 3600, user_id=current_user_id)
    with transaction(conference_store):
        row = conference_store._connect().execute(
            "SELECT * FROM conference_access_requests WHERE conference_id=? AND user_id=? AND status='pending'",
            (conf_id, current_user_id),
        ).fetchone()
        if row:
            return dict(row)
        request_id = "access-" + uuid.uuid4().hex
        created = datetime.now(timezone.utc).isoformat()
        conference_store._connect().execute(
            "INSERT INTO conference_access_requests(request_id,conference_id,user_id,requested_role,status,created_at) VALUES(?,?,?,?, 'pending',?)",
            (request_id, conf_id, current_user_id, role, created),
        )
        _audit(conference_store, current_user_id, "conference.access_requested", conf_id)
        return dict(conference_store._connect().execute(
            "SELECT * FROM conference_access_requests WHERE request_id=?", (request_id,)
        ).fetchone())


@router.get("/{conf_id}/access-requests")
async def list_access_requests(conf_id: str, conference_store: ConferenceStore = Depends(get_conference_store),
                               current_user_id: str = Depends(get_current_user_id)):
    _chair(conference_store, conf_id, current_user_id)
    return [dict(row) for row in conference_store._connect().execute(
        "SELECT r.request_id,r.conference_id,r.user_id,u.full_name,u.email,r.requested_role,r.status,r.created_at,r.decided_at "
        "FROM conference_access_requests r JOIN users u ON u.user_id=r.user_id WHERE r.conference_id=? "
        "ORDER BY CASE r.status WHEN 'pending' THEN 0 ELSE 1 END,r.created_at DESC", (conf_id,)
    ).fetchall()]


@router.get("/{conf_id}/access-requests/mine")
async def my_access_request(conf_id: str, conference_store: ConferenceStore = Depends(get_conference_store),
                            current_user_id: str = Depends(get_current_user_id)):
    if not conference_store.exists(conf_id):
        raise HTTPException(status_code=404, detail="Conference not found")
    row = conference_store._connect().execute(
        "SELECT request_id,requested_role,status,created_at,decided_at FROM conference_access_requests "
        "WHERE conference_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1", (conf_id, current_user_id)
    ).fetchone()
    return dict(row) if row else None


@router.patch("/{conf_id}/access-requests/{request_id}")
async def decide_access_request(conf_id: str, request_id: str, decision: str = Body(..., embed=True),
                                conference_store: ConferenceStore = Depends(get_conference_store),
                                current_user_id: str = Depends(get_current_user_id)):
    if decision not in {"approved", "declined"}:
        raise HTTPException(status_code=422, detail="Decision must be approved or declined")
    with transaction(conference_store):
        _chair(conference_store, conf_id, current_user_id)
        row = conference_store._connect().execute(
            "SELECT * FROM conference_access_requests WHERE request_id=? AND conference_id=?", (request_id, conf_id)
        ).fetchone()
        if not row or row["status"] != "pending":
            raise HTTPException(status_code=404, detail="Pending access request not found")
        if decision == "approved":
            conference_store.add_member(conf_id, row["user_id"], ConferenceRole(row["requested_role"]))
        now = datetime.now(timezone.utc).isoformat()
        conference_store._connect().execute(
            "UPDATE conference_access_requests SET status=?,decided_at=?,decided_by=? WHERE request_id=? AND status='pending'",
            (decision, now, current_user_id, request_id),
        )
        _audit(conference_store, current_user_id, f"conference.access_{decision}", conf_id)
    return {"request_id": request_id, "status": decision}


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
