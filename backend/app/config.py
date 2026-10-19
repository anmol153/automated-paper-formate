import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Paper Format Compliance API"
    app_version: str = "0.4.0"
    debug: bool = False
    # Set SECRET_KEY for stable sessions across restarts and server workers.
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48), min_length=32)

    workflow_db_path: Path | None = None
    submission_file_dir: Path | None = None
    cookie_secure: bool = True
    max_upload_bytes: int = Field(50 * 1024 * 1024, ge=1024)
    max_batch_bytes: int = Field(100 * 1024 * 1024, ge=1024)
    max_pdf_pages: int = Field(500, ge=1)
    max_archive_bytes: int = Field(100 * 1024 * 1024, ge=1024)

    google_import_user_ids: tuple[str, ...] = ()
    google_oauth_client_id: str = Field("", max_length=300)

    @field_validator("google_oauth_client_id")
    @classmethod
    def oauth_client_id(cls, value):
        import re
        value = value.strip()
        if value and not re.fullmatch(r"[A-Za-z0-9_-]+\.apps\.googleusercontent\.com", value):
            raise ValueError("Use a Google web OAuth client ID ending in .apps.googleusercontent.com")
        return value

    google_api_key: str | None = None
    google_service_account_file: Path = BACKEND_DIR / "credentials" / "service_account.json"
    google_scopes: tuple[str, ...] = (
        "https://www.googleapis.com/auth/documents.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    )

    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000")


@lru_cache
def get_settings() -> Settings:
    return Settings()
