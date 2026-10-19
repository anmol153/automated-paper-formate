"""Bounded PDF snapshots for the authenticated browser viewer."""
import hashlib
import re

import fitz
from fastapi import HTTPException

from app.parsing.errors import ParseError
from app.security.files import PrivateFiles, validate_document

MAX_PREVIEW_BYTES = 25 * 1024 * 1024


def pdf_snapshot(root, revision):
    if revision["size_bytes"] > MAX_PREVIEW_BYTES:
        raise HTTPException(status_code=413, detail="PDF preview is limited to 25 MB. Download the original file instead.")
    files = PrivateFiles(root)
    path = files.verified(revision["storage_key"], revision["sha256"], revision["size_bytes"])
    with path.open("rb") as source:
        data = source.read(MAX_PREVIEW_BYTES + 1)
    # Validate the bytes actually returned, not only the file before reading it.
    if len(data) != revision["size_bytes"] or hashlib.sha256(data).hexdigest() != revision["sha256"]:
        raise HTTPException(status_code=409, detail="Stored file failed its integrity check")
    try:
        if validate_document(data, revision["filename"]) != "pdf":
            raise HTTPException(status_code=415, detail="Inline preview supports PDF files. Download this source document instead.")
        with fitz.open(stream=data, filetype="pdf") as document:
            page_count = document.page_count
            # Inspect MuPDF's parsed objects too: actions can be nested inline
            # rather than stored as a separate xref with a top-level S key.
            for xref in range(1, document.xref_length()):
                if re.search(r"/(?:JavaScript|Launch|JS)(?=[\s<>\[\]()/]|$)", document.xref_object(xref)):
                    raise ParseError("Interactive PDF actions are not supported in the preview. Download the original instead.")
        if page_count < 1:
            raise ParseError("PDF has no pages")
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return data, page_count
