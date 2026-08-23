from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings

logger = logging.getLogger(__name__)


class GoogleAuthError(RuntimeError):
    pass


class DocumentFetchError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


@lru_cache(maxsize=4)
def _load_credentials() -> tuple[object | None, str | None]:
    settings = get_settings()
    sa_path: Path = settings.google_service_account_file
    if str(sa_path).strip() and sa_path.is_file():
        creds = ServiceAccountCredentials.from_service_account_file(
            str(sa_path), scopes=list(settings.google_scopes)
        )
        return creds, "service-account"
    api_key = (settings.google_api_key or "").strip()
    if api_key:
        return api_key, "api-key"
    return None, None


def auth_mode() -> str:
    _, mode = _load_credentials()
    return mode or "not-configured"


def fetch_document(doc_id: str) -> dict:
    credentials, mode = _load_credentials()
    if credentials is None:
        raise GoogleAuthError(
            "Google credentials are not configured. Provide a service account JSON "
            "(backend/credentials/service_account.json), set GOOGLE_API_KEY, or use demo mode."
        )
    try:
        if mode == "service-account":
            if not credentials.valid:
                credentials.refresh(GoogleAuthRequest())
            service = build("docs", "v1", credentials=credentials, cache_discovery=False)
        else:
            service = build("docs", "v1", developerKey=str(credentials), cache_discovery=False)
        return service.documents().get(documentId=doc_id).execute()
    except HttpError as exc:
        status = exc.resp.status if exc.resp is not None else 500
        if status == 404:
            raise DocumentFetchError(
                f"Document {doc_id} was not found. Check the URL and sharing settings.", 404
            ) from exc
        if status in (401, 403):
            raise DocumentFetchError(
                f"No permission to read document {doc_id}. Share it with the service account "
                "email or make it link-viewable.",
                403,
            ) from exc
        logger.warning("Google API error fetching %s: %s", doc_id, exc)
        raise DocumentFetchError(f"Google Docs API error ({status}).", 502) from exc
