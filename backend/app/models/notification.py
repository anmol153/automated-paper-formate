"""Notification model for workflow events (review assignments, issues, etc.)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NotificationType(str, Enum):
    REVIEW_ASSIGNMENT = "review_assignment"
    ISSUE_ASSIGNED = "issue_assigned"
    ISSUE_STATUS = "issue_status"
    DISCUSSION_MENTION = "discussion_mention"
    SUBMISSION_VERDICT = "submission_verdict"
    MEMBER_ADDED = "member_added"
    SUBMISSION_UPDATE = "submission_update"


class Notification(BaseModel):
    """A notification for a user about a workflow event."""

    notification_id: str = Field(..., description="Unique notification identifier")
    user_id: str = Field(..., description="User this notification is for")
    type: NotificationType = Field(..., description="Type of notification")
    title: str = Field(..., description="Short notification title")
    body: str = Field(..., description="Longer notification body")
    related_id: Optional[str] = Field(None, description="ID of the related entity (submission, issue, etc.)")
    read: bool = Field(False, description="Whether the user has read this notification")
    created_at: str = Field(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        description="When the notification was created",
    )
    email: Optional[str] = Field(
        None,
        description="Optional user email for email snowflake notification delivery",
    )

    class Config:
        from_attributes = True


__all__ = ["Notification", "NotificationType"]
