"""Bounded ingestion and private, generated-key file storage."""
import hashlib
import os
import re
import stat
import zipfile
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

    def path(self, key):
        if not re.fullmatch(r"[0-9a-f]{32}", key or ""):
            raise HTTPException(status_code=404, detail="File not found")
        path = self.root / key
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise HTTPException(status_code=404, detail="File not found")
        return path

    def put(self, data):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        key = uuid4().hex
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
        return key, hashlib.sha256(data).hexdigest()

    def verified(self, key, expected_hash, expected_size):
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
        self.path(key).unlink(missing_ok=True)
