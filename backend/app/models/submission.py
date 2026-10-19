"""Submission model tied to a conference and its active template version.

A Submission represents a paper upload attempt under a specific conference
and template version. It tracks the state of compliance checking, reviewer
assignment, and discussion threads.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.conference import Conference, ConferenceRole
from app.models.rules import RuleSet
from app.models.intake import BibliographicAuthor


class SubmissionStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    CHANGES_REQUESTED = "changes_requested"
    WITHDRAWN = "withdrawn"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ReviewVerdict(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    REVIEW = "review"


class Submission(BaseModel):
    """A paper submission tied to a conference and its active template version."""

    submission_id: str = Field(
        ..., description="Unique identifier for the submission"
    )
    conference_id: str = Field(..., description="Owning conference")
    template_id: str = Field(
        ..., description="Active template version in use"
    )
    filename: str = Field(..., description="Original uploaded filename")
    paper_number: int | None = None
    title: str = ""
    abstract: str = ""
    authors: list[BibliographicAuthor] = Field(default_factory=list)
    track_id: str | None = None
    metadata_version: int = 0
    status: SubmissionStatus = Field(
        default=SubmissionStatus.DRAFT, description="Current submission state"
    )
    reviewer_id: Optional[str] = Field(
        None, description="User assigned as reviewer (optional)"
    )
    verdict: Optional[ReviewVerdict] = Field(
        None, description="Final verdict after review"
    )
    compliance_score: Optional[int] = Field(
        None, description="Score 0-100 from template compliance check"
    )
    created_at: str = Field(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        description="When the submission was created",
    )
    updated_at: str = Field(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        description="When the submission was last updated",
    )

    class Config:
        """Pydantic v2 configuration."""

        from_attributes = True


class DiscussionThread(BaseModel):
    """A discussion thread associated with a submission."""

    thread_id: str = Field(..., description="Unique thread identifier")
    submission_id: str = Field(..., description="Linked submission")
    author_id: str = Field(..., description="User who started the thread")
    title: str = Field(..., description="Thread title")
    created_at: str = Field(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        description="When the thread was created",
    )
    messages: List[dict] = Field(
        default_factory=list, description="Thread messages (author, text, timestamp)"
    )

    class Config:
        from_attributes = True


class ReviewAssignment(BaseModel):
    """Assignment of a reviewer to a submission."""

    assignment_id: str = Field(..., description="Unique assignment identifier")
    submission_id: str = Field(..., description="Target submission")
    reviewer_id: str = Field(..., description="User assigned as reviewer")
    assigned_by: str = Field(..., description="User who made the assignment")
    assigned_at: str = Field(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        description="When the assignment was made",
    )
    status: str = Field(default="pending", description="Reviewer assignment status")

    class Config:
        from_attributes = True
