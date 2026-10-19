"""Bounded ingestion and private, generated-key file storage."""
import hashlib
import os
import re
import stat
import tempfile
import zipfile
from functools import lru_cache
from io import BytesIO
from pathlib import Path, PurePosixPath
from uuid import uuid4

import fitz
from fastapi import HTTPException

from app.config import get_settings
from app.parsing.errors import ParseError
from app.parsing.pipeline import sniff_format


async def read_upload(upload, *, remaining=None, allow_empty=False):
    limit = get_settings().max_upload_bytes
    if remaining is not None:
        limit = min(limit, remaining)
    data = bytearray()
    while chunk := await upload.read(min(65536, max(1, limit + 1 - len(data)))):
        data.extend(chunk)
        if len(data) > limit:
            raise HTTPException(status_code=413, detail="Upload exceeds the configured byte limit")
    if not data and not allow_empty:
        raise ParseError("The uploaded file is empty")
    return bytes(data)


def validate_document(data, filename):
    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Upload exceeds the configured byte limit")
    fmt = sniff_format(data, filename)
    if fmt == "docx":
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(e.file_size for e in entries) > settings.max_archive_bytes:
                    raise ParseError("Word archive expands beyond the configured limit")
                names = [entry.filename for entry in entries]
                if len(names) != len(set(names)):
                    raise ParseError("Word archive has duplicate entries")
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                    raise ParseError("Upload is not a Word document")
                for entry in entries:
                    path = PurePosixPath(entry.filename)
                    if path.is_absolute() or ".." in path.parts or "\\" in entry.filename or stat.S_ISLNK(entry.external_attr >> 16):
                        raise ParseError("Unsafe Word archive entry")
                    if entry.flag_bits & 1 or entry.file_size > max(1, entry.compress_size) * 200:
                        raise ParseError("Encrypted or excessively compressed Word archive")
                    if entry.filename.endswith((".xml", ".rels")):
                        xml = archive.read(entry)
                        if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                            raise ParseError("XML document type declarations are not allowed")
                    if entry.filename.lower().endswith("vbaproject.bin"):
                        raise ParseError("Macro-enabled Word documents are not accepted")
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
            raise ParseError("Invalid Word archive") from exc
    elif fmt == "pdf":
        try:
            with fitz.open(stream=data, filetype="pdf") as pdf:
                if pdf.is_encrypted:
                    raise ParseError("Encrypted PDF documents are not accepted")
                if pdf.page_count > settings.max_pdf_pages:
                    raise ParseError("PDF exceeds the processing page limit")
                if pdf.embfile_count():
                    raise ParseError("PDF attachments are not accepted")
                if pdf.xref_length() > 100000:
                    raise ParseError("PDF exceeds the object processing limit")
                # Reject active document actions before a browser viewer receives it.
                for xref in range(1, pdf.xref_length()):
                    if pdf.xref_get_key(xref, "S")[1] in {"/JavaScript", "/Launch"}:
                        raise ParseError("Active PDF actions are not accepted")
        except (RuntimeError, ValueError) as exc:
            raise ParseError("Invalid PDF document") from exc
    elif fmt != "latex":
        raise ParseError("Supported formats are PDF, Word (.docx), and LaTeX source")
    return fmt


def safe_display_name(filename):
    if not filename or filename in {".", ".."} or len(filename) > 240:
        raise HTTPException(status_code=400, detail="Invalid upload filename")
    if any(ord(char) < 32 for char in filename) or any(char in filename for char in '/\\\x00'):
        raise HTTPException(status_code=400, detail="Invalid upload filename")
    return filename


class PrivateFiles:
    def __init__(self, root):
        self.root = Path(root).resolve()

    @staticmethod
    def _object_settings():
        settings = get_settings()
        configured = (settings.s3_bucket, settings.s3_access_key_id, settings.s3_secret_access_key)
        if any(configured) and not all(configured):
            raise RuntimeError("Configure S3_BUCKET, S3_ACCESS_KEY_ID, and S3_SECRET_ACCESS_KEY together")
        if all(configured):
            return settings
        return None

    def _storage_backend(self):
        settings = self._object_settings()
        if settings:
            return "s3", settings
        # Vercel connects a Blob store by exposing BLOB_STORE_ID and a rotating
        # VERCEL_OIDC_TOKEN at runtime. A static read/write token is supported
        # by the SDK for local or non-Vercel deployments too.
        if any(os.environ.get(name) for name in (
            "BLOB_STORE_ID", "BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN",
        )):
            return "vercel_blob", None
        # A shared database can outlive any one Vercel/container instance, but
        # its local filesystem cannot. Fail closed instead of recording file
        # keys that will disappear on the next cold start.
        from app.storage.postgres_compat import enabled
        if enabled():
            raise RuntimeError("Configure private Vercel Blob or S3-compatible storage before using shared PostgreSQL")
        return "local", None

    @staticmethod
    @lru_cache(maxsize=1)
    def _client(endpoint, region, access_key, secret_key):
        import boto3
        return boto3.client("s3", endpoint_url=endpoint or None, region_name=region or None,
                            aws_access_key_id=access_key, aws_secret_access_key=secret_key)

    def _object_client(self, settings):
        return self._client(settings.s3_endpoint_url or "", settings.s3_region,
                            settings.s3_access_key_id, settings.s3_secret_access_key)

    @staticmethod
    def _blob_client():
        from vercel.blob import sync as blob
        return blob

    @staticmethod
    def _cache_path(key):
        cache = Path(tempfile.gettempdir()) / "paper-format-object-cache"
        cache.mkdir(mode=0o700, parents=True, exist_ok=True)
        return cache / key

    def path(self, key):
        if not re.fullmatch(r"[0-9a-f]{32}", key or ""):
            raise HTTPException(status_code=404, detail="File not found")
        path = self.root / key
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise HTTPException(status_code=404, detail="File not found")
        return path

    def put(self, data):
        key = uuid4().hex
        digest = hashlib.sha256(data).hexdigest()
        backend, settings = self._storage_backend()
        if backend == "s3":
            self._object_client(settings).put_object(
                Bucket=settings.s3_bucket, Key=f"paper-revisions/{key}", Body=data,
                ContentType="application/octet-stream", Metadata={"sha256": digest},
            )
            return key, digest
        if backend == "vercel_blob":
            self._blob_client().put_blob(
                f"paper-revisions/{key}", data, access="private",
                content_type="application/octet-stream",
            )
            return key, digest
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.path(key)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return key, digest

    def verified(self, key, expected_hash, expected_size):
        if not re.fullmatch(r"[0-9a-f]{32}", key or ""):
            raise HTTPException(status_code=404, detail="File not found")
        backend, settings = self._storage_backend()
        if backend in {"s3", "vercel_blob"}:
            if expected_size < 0 or expected_size > get_settings().max_upload_bytes:
                raise HTTPException(status_code=409, detail="Stored file size is invalid")
            try:
                if backend == "s3":
                    response = self._object_client(settings).get_object(
                        Bucket=settings.s3_bucket, Key=f"paper-revisions/{key}")
                    body = response["Body"]
                    try:
                        data = body.read(expected_size + 1)
                    finally:
                        body.close()
                else:
                    data = self._blob_client().get_blob(
                        f"paper-revisions/{key}", access="private").body
            except Exception as exc:
                if (isinstance(exc, FileNotFoundError)
                        or getattr(exc, "response", {}).get("Error", {}).get("Code") in {"NoSuchKey", "404", "NotFound"}):
                    raise HTTPException(status_code=404, detail="File not found") from exc
                raise
            if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected_hash:
                raise HTTPException(status_code=409, detail="Stored file failed its integrity check")
            path = self._cache_path(key)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, "wb") as file:
                file.write(data)
            return path
        path = self.path(key)
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as file:
                if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                    raise HTTPException(status_code=404, detail="File not found")
                digest = hashlib.file_digest(file, "sha256").hexdigest()
                if digest != expected_hash or os.fstat(file.fileno()).st_size != expected_size:
                    raise HTTPException(status_code=409, detail="Stored file failed its integrity check")
        except OSError as exc:
            raise HTTPException(status_code=404, detail="File not found") from exc
        return path

    def discard(self, key):
        if not re.fullmatch(r"[0-9a-f]{32}", key or ""):
            raise HTTPException(status_code=404, detail="File not found")
        backend, settings = self._storage_backend()
        if backend == "s3":
            self._object_client(settings).delete_object(
                Bucket=settings.s3_bucket, Key=f"paper-revisions/{key}")
            self._cache_path(key).unlink(missing_ok=True)
            return
        if backend == "vercel_blob":
            self._blob_client().delete_blob(f"paper-revisions/{key}")
            self._cache_path(key).unlink(missing_ok=True)
            return
        self.path(key).unlink(missing_ok=True)
