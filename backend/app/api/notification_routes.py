"""Recipient and paper authorization apply to notifications and their counts."""
import base64
import binascii
import json
from datetime import datetime

from app.auth import get_current_user_id
from app.dependencies import (
    get_conference_store,
    get_notification_store,
    get_submission_store,
)
from app.models.notification import Notification
from app.security.notifications import visible
from app.storage.issue_store import get_issue_store
from app.storage.notification_store import NotificationNotFound, NotificationStore
from app.storage.database import transaction
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api/v1", tags=["notifications"])


def decode_cursor(value, user_id, unread_only):
    if value is None:
        return None
    try:
        payload = json.loads(base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True))
        version, recipient, unread, created, identifier = payload
        if (not isinstance(payload, list) or type(version) is not int or version != 1
                or recipient != user_id or type(unread) is not bool or unread != unread_only
                or not isinstance(created, str) or not 1 <= len(created) <= 100
                or not isinstance(identifier, str) or not 1 <= len(identifier) <= 100
                or datetime.fromisoformat(created).tzinfo is None):
            raise ValueError
        return created, identifier
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="Invalid notification cursor") from None


@router.get("/notifications/feed")
def notification_feed(
    limit: int = Query(25, ge=1, le=50), before: str | None = Query(None, max_length=512),
    unread_only: bool = False, user_id: str = Depends(get_current_user_id),
    notifications=Depends(get_notification_store), conferences=Depends(get_conference_store),
    submissions=Depends(get_submission_store), issues=Depends(get_issue_store),
):
    """Page only currently visible notifications; hidden rows never consume a slot."""
    cursor = decode_cursor(before, user_id, unread_only)
    items = []
    source = notifications.iter_by_user(user_id, unread_only, cursor)
    try:
        for item in source:
            projected = visible(item, user_id, conferences, submissions, issues)
            if projected is not None:
                items.append(projected)
                if len(items) > limit:
                    break
    finally:
        source.close()
    more = len(items) > limit
    items = items[:limit]
    next_cursor = None
    if more:
        last = items[-1]
        payload = [1, user_id, unread_only, last.created_at, last.notification_id]
        next_cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    return {"items": items, "next_cursor": next_cursor}


def visible_notifications(
    user_id: str = Depends(get_current_user_id),
    notifications=Depends(get_notification_store), conferences=Depends(get_conference_store),
    submissions=Depends(get_submission_store), issues=Depends(get_issue_store),
):
    return [projected for item in notifications.list_by_user(user_id)
            if (projected := visible(item, user_id, conferences, submissions, issues)) is not None]


@router.get("/notifications", response_model=list[Notification])
async def list_notifications(unread_only: bool = False, items=Depends(visible_notifications)):
    return [item for item in items if not unread_only or not item.read]


@router.get("/notifications/unread", response_model=list[Notification])
async def list_unread_notifications(items=Depends(visible_notifications)):
    return [item for item in items if not item.read]


@router.get("/notifications/count-unread")
def count_unread_notifications(user_id: str = Depends(get_current_user_id),
                               notifications=Depends(get_notification_store), conferences=Depends(get_conference_store),
                               submissions=Depends(get_submission_store), issues=Depends(get_issue_store)):
    return {"count": sum(visible(item, user_id, conferences, submissions, issues) is not None
                         for item in notifications.iter_by_user(user_id, unread_only=True))}


@router.patch("/notifications/read-all")
def mark_all_notifications_read(user_id: str = Depends(get_current_user_id),
                                notifications: NotificationStore = Depends(get_notification_store),
                                conferences=Depends(get_conference_store), submissions=Depends(get_submission_store),
                                issues=Depends(get_issue_store)):
    with transaction(notifications, conferences, submissions, issues):
        items = visible_notifications(user_id, notifications, conferences, submissions, issues)
        for item in items:
            if not item.read:
                notifications.mark_read(item.notification_id, user_id)
        return {"marked": sum(not item.read for item in items)}


@router.patch("/notifications/{notification_id}", response_model=Notification)
def mark_notification_read(notification_id: str, user_id: str = Depends(get_current_user_id),
                           notifications: NotificationStore = Depends(get_notification_store),
                           conferences=Depends(get_conference_store), submissions=Depends(get_submission_store),
                           issues=Depends(get_issue_store)):
    with transaction(notifications, conferences, submissions, issues):
        items = visible_notifications(user_id, notifications, conferences, submissions, issues)
        item = next((item for item in items if item.notification_id == notification_id), None)
        if item is None:
            raise HTTPException(status_code=404, detail="Notification not found")
        try:
            notifications.mark_read(notification_id, user_id)
        except NotificationNotFound as exc:
            raise HTTPException(status_code=404, detail="Notification not found") from exc
        return item.model_copy(update={"read": True})
