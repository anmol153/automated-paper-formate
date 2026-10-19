import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_email(value):
    value = value.strip().lower()
    if len(value) > 320 or value.count('@') != 1 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("Enter a valid recipient email address")
    local, domain = value.rsplit('@', 1)
    if not local or len(local) > 64 or '..' in domain or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', domain):
        raise ValueError("Enter a valid recipient email address")
    return value


class CreateInvitation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3, max_length=320)
    role: Literal['author', 'reviewer'] = 'author'
    expires_in_days: int = Field(7, ge=1, le=30, strict=True)

    @field_validator('email')
    @classmethod
    def recipient(cls, value):
        return normalize_email(value)


class InvitationToken(BaseModel):
    model_config = ConfigDict(extra='forbid')
    token: str = Field(min_length=43, max_length=43, pattern=r'^[A-Za-z0-9_-]+$')
