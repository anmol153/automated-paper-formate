"""Conference management models.

Defines the Conference, ConferenceRole, and ConferenceMember entities used for
organising submissions, assigning roles, and controlling access within the
Paper‑Format platform.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ConferenceRole(str, Enum):
    """Role a user can have inside a conference."""

    OWNER = "owner"
    REVIEWER = "reviewer"
    AUTHOR = "author"


class ConferenceMember(BaseModel):
    """Membership of a user inside a conference with a specific role."""

    user_id: str = Field(..., description="The user's unique identifier")
    role: ConferenceRole = Field(
        ..., description="The role the user has in this conference"
    )
    joined_at: str = Field(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        description="When the membership was created",
    )


class Conference(BaseModel):
    """A conference (organisation) that owns templates, submissions, and members."""

    conference_id: str = Field(
        ..., description="Unique identifier for the conference"
    )
    name: str = Field(..., description="Human‑readable conference name")
    description: str = Field(
        "", description="Optional description of the conference"
    )
    start_date: Optional[str] = Field(
        None, description="ISO‑8601 start date of the submission window"
    )
    end_date: Optional[str] = Field(
        None, description="ISO‑8601 end date of the submission window"
    )
    owners: List[str] = Field(
        default_factory=list,
        description="User IDs that have owner role in this conference",
    )
    members: List[ConferenceMember] = Field(
        default_factory=list,
        description="All members of the conference with their roles",
    )
