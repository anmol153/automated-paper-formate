from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Paper Format Compliance API"
    app_version: str = "1.0.0"
    debug: bool = False

    google_api_key: str | None = None
    google_service_account_file: Path = BACKEND_DIR / "credentials" / "service_account.json"
    google_scopes: tuple[str, ...] = (
        "https://www.googleapis.com/auth/documents.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    )

    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")


@lru_cache
def get_settings() -> Settings:
    return Settings()
