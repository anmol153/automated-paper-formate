"""Configurable review forms and strict write contracts."""
import math
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Criterion(Payload):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=120)
    kind: Literal["score", "text"]
    required: bool = True
    visibility: Literal["authors", "chairs"] = "authors"
    minimum: float = Field(1, ge=-1000000, le=1000000, allow_inf_nan=False)
    maximum: float = Field(5, ge=-1000000, le=1000000, allow_inf_nan=False)

    @model_validator(mode="after")
    def bounds(self):
        if not self.label.strip() or (self.kind == "score" and self.minimum >= self.maximum):
            raise ValueError("Use a nonempty label and an increasing score range")
        return self


class ReviewForm(Payload):
    name: str = Field("Conference review", min_length=1, max_length=150)
    criteria: list[Criterion] = Field(min_length=1, max_length=20)
    recommendations: list[str] = Field(min_length=2, max_length=10)

    @model_validator(mode="after")
    def unique_fields(self):
        if len({c.id for c in self.criteria}) != len(self.criteria):
            raise ValueError("Criterion IDs must be unique")
        names = [r.strip() for r in self.recommendations]
        if any(not r or len(r)>60 for r in names) or len({r.casefold() for r in names}) != len(names):
            raise ValueError("Recommendations must be distinct, nonempty labels up to 60 characters")
        self.recommendations = names
        return self


class ReviewPolicy(Payload):
    deadline: datetime | None = None
    allow_edit_submitted: bool = True
    reviewer_identities: Literal["hidden", "visible"] = "hidden"
    reviewers_see_others: bool = False
    publish_recommendation: bool = True
    minimum_reviews: int = Field(0, ge=0, le=20)

    @field_validator("deadline")
    @classmethod
    def aware_deadline(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("Review deadlines must include a timezone")
        return value.astimezone(timezone.utc) if value else None


class ConfigureReviews(Payload):
    expected_version: int = Field(ge=0)
    form: ReviewForm
    policy: ReviewPolicy


class SaveReview(Payload):
    assignment_id: str = Field(min_length=1, max_length=100)
    revision_id: str = Field(min_length=1, max_length=100)
    form_id: str = Field(min_length=1, max_length=100)
    expected_version: int = Field(ge=0)
    submit: bool = False
    recommendation: str | None = Field(None, max_length=60)
    answers: dict[str, str | float] = Field(default_factory=dict, max_length=20)
    confidential_comments: str = Field("", max_length=20000)

    @field_validator("answers", mode="before")
    @classmethod
    def bounded_answers(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Answers must map criterion IDs to text or numbers")
        if any(isinstance(v, bool) or not isinstance(v, (int, float, str)) or
               (isinstance(v, float) and not math.isfinite(v)) or
               (isinstance(v, str) and len(v)>20000) for v in value.values()):
            raise ValueError("Answers must be finite scores or text up to 20000 characters")
        if sum(len(v) for v in value.values() if isinstance(v, str)) > 100000:
            raise ValueError("Review text exceeds the total character limit")
        return value


class ReleaseReviews(Payload):
    expected_revision_id: str = Field(min_length=1, max_length=100)


class DeclareConflict(Payload):
    reviewer_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=4000)


class ResolveConflict(Payload):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=4000)


def default_form():
    return ReviewForm(
        name="Research paper review",
        criteria=[Criterion(id=i, label=label, kind="score") for i,label in [
            ("overall_score", "Overall score"), ("originality", "Originality"),
            ("technical_quality", "Technical quality"), ("presentation", "Presentation"), ("relevance", "Relevance")]]
        + [Criterion(id=i,label=label,kind="text",required=required) for i,label,required in [
            ("strengths", "Strengths", True), ("weaknesses", "Weaknesses", True), ("required_changes", "Required changes", False)]],
        recommendations=["Strong Accept", "Accept", "Weak Accept", "Borderline", "Weak Reject", "Reject", "Major Revision"],
    )
