"""Conference intake configuration and declared bibliographic metadata."""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ConferenceSettings(Payload):
    abbreviation: str = Field("", max_length=40)
    research_scope: str = Field("", max_length=10000)
    website: HttpUrl | None = None
    lifecycle_status: Literal["setup", "open", "reviewing", "closed", "archived"] = "open"
    submissions_open_at: datetime | None = None
    submissions_close_at: datetime | None = None
    revisions_close_at: datetime | None = None
    require_track: bool = False
    require_title: bool = False
    require_abstract: bool = False
    require_authors: bool = False

    @field_validator("submissions_open_at", "submissions_close_at", "revisions_close_at")
    @classmethod
    def aware_date(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Deadlines must include a timezone")
        return value.astimezone(timezone.utc) if value else None

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.submissions_open_at and self.submissions_close_at and self.submissions_open_at >= self.submissions_close_at:
            raise ValueError("Submissions must close after they open")
        if self.revisions_close_at and self.submissions_close_at and self.revisions_close_at < self.submissions_close_at:
            raise ValueError("The revision deadline must not precede the submission deadline")
        return self


class ConfigureConference(Payload):
    expected_version: int = Field(ge=0)
    settings: ConferenceSettings


class TrackFields(Payload):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=4000)
    active: bool = True


class UpdateTrack(TrackFields):
    expected_version: int = Field(ge=1)


class BibliographicAuthor(Payload):
    name: str = Field(min_length=1, max_length=200)
    affiliation: str = Field("", max_length=500)


class PaperMetadata(Payload):
    title: str = Field("", max_length=500)
    abstract: str = Field("", max_length=12000)
    authors: list[BibliographicAuthor] = Field(default_factory=list, max_length=50)
    track_id: str | None = Field(None, min_length=1, max_length=100)


class SaveMetadata(PaperMetadata):
    expected_version: int = Field(ge=0)
    expected_revision_id: str = Field(min_length=1, max_length=100)
