"""Chair-managed invitation links and explicit authenticated acceptance."""
from fastapi import APIRouter, Depends, Query, Request

from app.api.conference_routes import _chair
from app.auth import get_current_user_id, limit_requests
from app.dependencies import get_conference_store
from app.models.invitation import CreateInvitation, InvitationToken
from app.services import invitations
from app.storage.database import transaction

router = APIRouter(prefix='/api/v1', tags=['conference invitations'])


@router.get('/conferences/{conf_id}/invitations')
def list_invitations(conf_id: str, limit: int = Query(25, ge=1, le=50), before: str | None = Query(None, max_length=100),
                     store=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    _chair(store, conf_id, actor)
    return invitations.page(store, conf_id, limit, before)


@router.post('/conferences/{conf_id}/invitations', status_code=201)
def create_invitation(conf_id: str, body: CreateInvitation, request: Request,
                      store=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    _chair(store, conf_id, actor)
    invitations.require_invitations(store)
    limit_requests(request, 'invitation-create', 30, 3600, user_id=actor)
    with transaction(store):
        _chair(store, conf_id, actor)
        return invitations.issue(store, conf_id, actor, body)


@router.delete('/conferences/{conf_id}/invitations/{invitation_id}')
def revoke_invitation(conf_id: str, invitation_id: str,
                      store=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store):
        _chair(store, conf_id, actor)
        return invitations.revoke(store, conf_id, invitation_id, actor)


@router.post('/invitations/inspect')
def inspect_invitation(body: InvitationToken, request: Request,
                       store=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    invitations.require_invitations(store)
    limit_requests(request, 'invitation-inspect', 120, 3600, user_id=actor)
    with transaction(store):
        row, role = invitations.lookup(store, body.token, actor)
        return invitations.recipient_view(store, row, role)


@router.post('/invitations/accept')
def accept_invitation(body: InvitationToken, request: Request,
                      store=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    invitations.require_invitations(store)
    limit_requests(request, 'invitation-accept', 30, 3600, user_id=actor)
    with transaction(store):
        return invitations.accept(store, body.token, actor)
