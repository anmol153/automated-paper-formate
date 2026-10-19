from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from passlib.context import CryptContext
from typing import Optional

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserBase(BaseModel):
    email: str = Field(..., example="john.doe@example.com")
    full_name: str = Field(..., example="John Doe")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=72, example="secret123")

    @field_validator("password")
    @classmethod
    def bcrypt_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class User(UserBase):
    user_id: str = Field(..., example="user_123")
    is_active: bool = True
    # Hashed password is stored, not the plain text
    hashed_password: str

    @classmethod
    def from_create(cls, user_id: str, user_create: UserCreate) -> "User":
        hashed_password = pwd_context.hash(user_create.password)
        return cls(
            user_id=user_id,
            email=user_create.email,
            full_name=user_create.full_name,
            hashed_password=hashed_password,
        )

    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.hashed_password)


class UserInDB(User):
    """Internal user model that includes hashed password (for storage)."""
    pass


class UserPublic(UserBase):
    """Public user model (no sensitive data)."""
    user_id: str
    is_active: bool


__all__ = [
    "UserBase",
    "UserCreate",
    "User",
    "UserInDB",
    "UserPublic",
    "pwd_context",
]