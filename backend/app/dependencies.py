from __future__ import annotations

from fastapi import Depends, HTTPException, status

from .auth import get_current_user_id
from .models.conference import Conference, ConferenceRole
from .models.user import UserPublic
from .storage import get_submission_store as get_submission_store
from .storage import get_user_store
from .storage.conference_store import ConferenceNotFound, ConferenceStore
from .storage.notification_store import get_notification_store as get_notification_store



async def get_current_user(user_id: str = Depends(get_current_user_id)) -> UserPublic:
    return UserPublic.model_validate(get_user_store().get(user_id).model_dump())


def get_conference_store() -> ConferenceStore:
    """FastAPI dependency that returns a ConferenceStore instance."""
    return ConferenceStore()


def require_role(
    conf_id: str, required_role: str
) :
    """
    Dependency factory to check if the current user has the required role in the given conference.

    Usage in a route:

        @app.get("/conferences/{conf_id}/submit")
        async def submit(
            conf_id: str,
            current_user: UserPublic = Depends(get_current_user),
            _: None = Depends(require_role(conf_id, "owner")),
        ):
            ...

    The dependency raises ``HTTPException(403)`` if the user does not hold the
    required role, and ``HTTPException(401)`` if the user is not authenticated.
    """

    async def role_checker(
        current_user: UserPublic = Depends(get_current_user),
        conference_store: ConferenceStore = Depends(get_conference_store),
    ) -> UserPublic:
        # Check membership and role
        has_role = conference_store.user_has_role(
            conf_id, current_user.user_id, ConferenceRole(required_role)
        )
        if not has_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have '{required_role}' role in conference '{conf_id}'",
            )
        return current_user

    return role_checker


# Helper to inject the conference object itself
async def get_current_conference(
    conf_id: str,
    conference_store: ConferenceStore = Depends(get_conference_store),
    current_user: UserPublic = Depends(get_current_user),
) -> Conference:
    """Return the Conference object if the current user is a member."""
    try:
        conference = conference_store.get(conf_id)
    except ConferenceNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conference '{conf_id}' not found",
        )

    # Check membership (any role is sufficient to view the conference)
    if not conference_store.user_has_role(
        conf_id, current_user.user_id, ConferenceRole.AUTHOR
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User is not a member of conference '{conf_id}'",
        )

    return conference

