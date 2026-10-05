"""Google Drive folder ingest.

Lets a submitter point the portal at a Drive folder instead of uploading files
one by one. Everything degrades gracefully: if no credentials are configured,
``auth_mode()`` reports ``not-configured`` and the API returns a clear 503
telling the operator what to set up, rather than a stack trace.

Auth follows the same two-mode approach as the existing Docs client: a service
account JSON is preferred (it is the only mode that can read private folders
shared with it), with an API key as a fallback for public links.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Iterator, Optional

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings
from app.google.docs_client import DocumentFetchError, GoogleAuthError, _load_credentials, auth_mode

logger = logging.getLogger(__name__)

FOLDER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{10,}$")
_FOLDER_URL_RE = re.compile(r"/folders/([a-zA-Z0-9_-]{10,})")
_DOC_URL_RE = re.compile(r"/document/d/(?:e/)?([a-zA-Z0-9_-]{10,})")

DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive.readonly",)

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
FOLDER_MIME = "application/vnd.google-apps.folder"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"

# Export targets keyed by the extension the submission pipeline expects.
EXPORT_TARGETS = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}

DOWNLOADABLE_EXTENSIONS = ("pdf", "tex", "latex", "docx")


class DriveNotConfigured(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Google Drive access is not configured on this server. To enable folder import, "
            "place a service-account JSON at backend/credentials/service_account.json (with the "
            "Drive read-only scope) and share the folder with that service account's email, or "
            "set GOOGLE_API_KEY for public folders. Authors can still upload files directly."
        )


def extract_folder_id(source: str) -> str:
    """Pull a Drive folder id out of a share link or accept a bare id."""
    text = (source or "").strip().strip("\"'")
    if not text:
        raise ValueError("The Google Drive link is empty.")
    for pattern in (_FOLDER_URL_RE, _DOC_URL_RE):
        match = pattern.search(text)
        if match:
            return match.group(1)
    query = dict(re.findall(r"[?&]([^&=]+)=([^&=]+)", text))
    for key in ("id", "folderid", "folder"):
        value = query.get(key.lower())
        if value and FOLDER_ID_RE.match(value):
            return value
    if FOLDER_ID_RE.match(text):
        return text
    raise ValueError(
        f"'{text[:100]}' is not a Google Drive folder link. Expected a link like "
        "https://drive.google.com/drive/folders/<id>."
    )


@lru_cache(maxsize=4)
def _drive_service():
    credentials, mode = _load_credentials()
    if credentials is None:
        raise DriveNotConfigured()
    if mode == "service-account":
        if not getattr(credentials, "valid", False):
            credentials.refresh(GoogleAuthRequest())
        return build("drive", "v3", credentials=credentials, cache_discovery=False)
    return build("drive", "v3", developerKey=str(credentials), cache_discovery=False)


class DriveFile:
    def __init__(self, item: dict) -> None:
        self.id: str = item.get("id", "")
        self.name: str = item.get("name", "")
        self.mime: str = item.get("mimeType", "")
        self.size: int = int(item.get("size") or 0)
        self.modified: str = item.get("modifiedTime", "")
        self.is_folder: bool = self.mime == FOLDER_MIME
        self.is_google_doc: bool = self.mime == GOOGLE_DOC_MIME
        self.is_shortcut: bool = self.mime == SHORTCUT_MIME

    def extension(self) -> str:
        if self.is_google_doc:
            return "gdoc"
        if "." in self.name:
            return self.name.rsplit(".", 1)[-1].casefold()
        return ""

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "mimeType": self.mime,
            "size": self.size,
            "modifiedTime": self.modified,
            "extension": self.extension(),
            "kind": (
                "folder" if self.is_folder
                else "google-doc" if self.is_google_doc
                else "shortcut" if self.is_shortcut
                else "file"
            ),
        }


def _drive_error(exc: HttpError, context: str) -> DocumentFetchError:
    status = exc.resp.status if exc.resp is not None else 500
    if status == 404:
        return DocumentFetchError(
            f"{context} was not found. Check the link and that the folder is shared with the "
            "configured Google account.", 404
        )
    if status in (401, 403):
        return DocumentFetchError(
            f"No permission to read {context}. Share it with the service account email "
            "(Viewer access) or set link sharing to 'Anyone with the link'.",
            403,
        )
    logger.warning("Drive API error for %s: %s", context, exc)
    return DocumentFetchError(f"Google Drive API error ({status}).", 502)


def list_folder(folder_id: str, recursive: bool = True, max_files: int = 200) -> list[DriveFile]:
    """List files in a Drive folder, descending one level into subfolders."""
    service = _drive_service()
    collected: list[DriveFile] = []
    seen: set[str] = set()

    def walk(current: str, depth: int) -> None:
        if len(collected) >= max_files:
            return
        page_token = None
        while True:
            response = (
                service.files()
                .list(
                    q=f"'{current}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)",
                    pageSize=100,
                    pageToken=page_token,
                )
                .execute()
            )
            for item in response.get("files", []):
                if item.get("id") in seen:
                    continue
                seen.add(item.get("id"))
                drive_file = DriveFile(item)
                collected.append(drive_file)
                if drive_file.is_folder and recursive and depth < 3 and len(collected) < max_files:
                    walk(drive_file.id, depth + 1)
            page_token = response.get("nextPageToken")
            if not page_token or len(collected) >= max_files:
                break

    walk(folder_id, 0)
    return collected[:max_files]


def download(file: DriveFile, target_extension: str | None = None) -> tuple[str, bytes]:
    """Fetch a file's bytes. Google Docs are exported to PDF unless asked otherwise."""
    service = _drive_service()

    if file.is_google_doc or file.mime.startswith("application/vnd.google-apps."):
        extension = (target_extension or "pdf").casefold().lstrip(".")
        mime = EXPORT_TARGETS.get(extension, EXPORT_TARGETS["pdf"])
        try:
            data = service.files().export(fileId=file.id, mimeType=mime).execute()
        except HttpError as exc:
            raise _drive_error(exc, f"Google Doc '{file.name}'") from exc
        return f"{file.name}.{extension}", data

    if file.is_folder or file.is_shortcut:
        raise ValueError(f"'{file.name}' is not a downloadable file.")

    try:
        data = service.files().get_media(fileId=file.id).execute()
    except HttpError as exc:
        raise _drive_error(exc, f"'{file.name}'") from exc
    return file.name, data


def select_papers(files: list[DriveFile], accepted: tuple[str, ...] = DOWNLOADABLE_EXTENSIONS) -> list[DriveFile]:
    """Filter a Drive listing down to files the submission pipeline can parse."""
    accepted_set = {a.casefold().lstrip(".") for a in accepted}
    return [
        f for f in files
        if not f.is_folder
        and not f.is_shortcut
        and (f.is_google_doc or f.extension() in accepted_set)
    ]


__all__ = [
    "DriveFile",
    "DriveNotConfigured",
    "auth_mode",
    "download",
    "extract_folder_id",
    "list_folder",
    "select_papers",
    "DOWNLOADABLE_EXTENSIONS",
    "EXPORT_TARGETS",
]
