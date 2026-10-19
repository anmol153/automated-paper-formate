"""Issue tracking model for compliance findings.

An Issue represents a specific formatting/compliance finding that needs to be
addressed. Issues can be created from CheckResult failures, assigned to users,
and tracked through resolution.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class IssueStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"


class IssueSeverity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"
    ADVISORY = "advisory"


class Issue(BaseModel):
    """A tracked issue from a compliance check result."""

    revision_id: Optional[str] = None
    check_run_id: Optional[str] = None
    issue_id: str = Field(..., description="Unique issue identifier")
    submission_id: str = Field(..., description="Submission this issue belongs to")
    check_result_id: str = Field(..., description="Original CheckResult.id that created this issue")
    category: str = Field(..., description="Category from CheckResult (file, page, typography, etc.)")
    title: str = Field(..., description="Human-readable issue title")
    description: str = Field(..., description="Detailed description of the issue")
    severity: IssueSeverity = Field(..., description="Issue severity level")
    expected: Optional[str] = Field(None, description="What was expected")
    actual: Optional[str] = Field(None, description="What was actually found")
    advice: Optional[str] = Field(None, description="Remediation advice")
    evidence: Optional[str] = Field(None, description="Supporting evidence")
    status: IssueStatus = Field(default=IssueStatus.OPEN, description="Current issue status")
    assignee_id: Optional[str] = Field(None, description="User assigned to fix this issue")
    created_at: str = Field(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        description="When the issue was created",
    )
    updated_at: str = Field(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        description="When the issue was last updated",
    )
    resolved_at: Optional[str] = Field(None, description="When the issue was resolved")
    resolved_by: Optional[str] = Field(None, description="User who resolved the issue")

    class Config:
        from_attributes = True


class IssueComment(BaseModel):
    """A comment on an issue."""

    comment_id: str = Field(..., description="Unique comment identifier")
    issue_id: str = Field(..., description="Issue this comment belongs to")
    author_id: str = Field(..., description="User who wrote the comment")
    text: str = Field(..., description="Comment text")
    created_at: str = Field(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        description="When the comment was created",
    )

    class Config:
        from_attributes = True
