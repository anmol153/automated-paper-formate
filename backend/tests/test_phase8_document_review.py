"""Authorized PDF previews, immutable page anchors, and resource boundaries."""
from time import time
from uuid import uuid4

import fitz
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import auth
from app.security.files import PrivateFiles
from app.services import document_preview
from app.storage import revisions

from .test_phase1_security import password_hash, world  # noqa: F401
from .test_phase2_revisions import create_paper


def pdf(pages=2):
    with fitz.open() as document:
        for index in range(pages):
            document.new_page().insert_text((72, 72), f"Research paper page {index + 1}")
        return document.tobytes()


def paper(w):
    data = pdf()
    response = w.client("author").post(f"/api/v1/conferences/{w.conf.conference_id}/submissions",
        files={"file": ("research.pdf", data)})
    assert response.status_code == 201, response.text
    base = "/api/v1/submissions/" + response.json()["submission_id"]
    first = w.client("author").get(base + "/revisions").json()["revisions"][0]
    return base, first, data


def preview(base, revision):
    return base + "/revisions/" + revision["revision_id"] + "/preview"


def test_preview_permissions_and_safe_response(world):
    w = world
    base, first, data = paper(w)
    url = preview(base, first)
    with TestClient(w.app) as anonymous:
        assert anonymous.get(url).status_code == 401
    for actor in ["other", "unassigned", "outsider", "reviewer"]:
        assert w.client(actor).get(url).status_code == 404
    assert w.client("chair").post(base + "/review", json="reviewer").status_code == 201
    for actor in ["chair", "author", "reviewer"]:
        result = w.client(actor).get(url)
        assert result.status_code == 200, result.text
        assert result.content == data
        assert result.headers["content-type"] == "application/pdf"
        assert result.headers["x-paper-page-count"] == "2"
        assert result.headers["content-disposition"].startswith("inline;")
        assert result.headers["cache-control"] == "private, no-store"
        assert result.headers["x-content-type-options"] == "nosniff"
    assignment = w.client("chair").get(base + "/workflow").json()["assignments"][0]
    assert w.client("chair").delete(base + "/assignments/" + assignment["assignment_id"]).status_code == 204
    assert w.client("reviewer").get(url).status_code == 404


def test_historical_previews_and_page_comments_remain_on_original_revision(world):
    w = world
    base, first, original = paper(w)
    author = w.client("author")
    comment = author.post(base + "/conversation", json={"body": "Please clarify page two", "revision_id": first["revision_id"], "page_number": 2})
    assert comment.status_code == 201
    changed = pdf(3)
    result = author.post(base + "/revisions", files={"file": ("revised.pdf", changed)},
        data={"parent_revision_id": first["revision_id"], "request_key": uuid4().hex})
    assert result.status_code == 201, result.text
    second = result.json()
    assert author.get(preview(base, first)).content == original
    assert author.get(preview(base, second)).content == changed
    assert author.get(preview(base, second)).headers["x-paper-page-count"] == "3"
    thread = next(row for row in author.get(base + "/conversation").json() if row["thread_id"] == comment.json()["thread_id"])
    assert (thread["revision_id"], thread["page_number"]) == (first["revision_id"], 2)
    assert author.post(base + "/conversation", json={"body": "Out of bounds", "revision_id": first["revision_id"], "page_number": 3}).status_code == 422
    assert author.post(base + "/conversation", json={"body": "New page", "revision_id": second["revision_id"], "page_number": 3}).status_code == 201
    assert author.post(base + "/conversation", json={"body": "Missing revision", "page_number": 1}).status_code == 422


def test_confidential_page_threads_stay_hidden_from_author_and_reviewer(world):
    w = world
    base, first, _ = paper(w)
    chair = w.client("chair")
    assert chair.post(base + "/review", json="reviewer").status_code == 201
    payload = {"body": "Private chair discussion", "visibility": "chairs", "revision_id": first["revision_id"], "page_number": 1}
    private = chair.post(base + "/conversation", json=payload)
    assert private.status_code == 201
    assert private.json()["thread_id"] in {row["thread_id"] for row in chair.get(base + "/conversation").json()}
    for actor in ["author", "reviewer"]:
        client = w.client(actor)
        assert private.json()["thread_id"] not in {row["thread_id"] for row in client.get(base + "/conversation").json()}
        assert client.post(base + "/conversation", json=payload).status_code == 403
        assert client.post(base + "/conversation/" + private.json()["thread_id"] + "/comments", json={"body": "Intrusion"}).status_code == 404


def test_preview_rejects_non_pdf_and_cross_submission_revision(world):
    base, first, _ = paper(world)
    source_base, source = create_paper(world)
    author = world.client("author")
    assert author.get(preview(source_base, source)).status_code == 415
    assert author.get(preview(base, source)).status_code == 404
    assert author.get(preview(source_base, first)).status_code == 404


def test_preview_integrity_size_and_rate_boundaries(world, monkeypatch):
    w = world
    base, first, original = paper(w)
    author = w.client("author")
    url = preview(base, first)
    row = revisions.get_revision(w.submissions, first["submission_id"], first["revision_id"])
    path = PrivateFiles(w.tmp_path / "private").path(row["storage_key"])
    path.write_bytes(b"x" * len(original))
    result = author.get(url)
    assert result.status_code == 409
    assert b"%PDF" not in result.content
    path.write_bytes(original)
    monkeypatch.setattr(document_preview, "MAX_PREVIEW_BYTES", len(original) - 1)
    assert author.get(url).status_code == 413
    monkeypatch.setattr(document_preview, "MAX_PREVIEW_BYTES", 25 * 1024 * 1024)
    bucket = auth.digest("revision-pdf-preview:author")
    w.users._connect().execute("UPDATE request_limits SET attempts=60,resets_at=? WHERE bucket=?", (int(time()) + 60, bucket))
    assert author.get(url).status_code == 429


def test_preview_rechecks_access_after_expensive_validation(world, monkeypatch):
    w = world
    base, first, _ = paper(w)
    assert w.client("chair").post(base + "/review", json="reviewer").status_code == 201
    original = document_preview.pdf_snapshot
    def revoked(root, revision):
        value = original(root, revision)
        w.submissions._connect().execute("UPDATE review_assignments SET status='revoked' WHERE submission_id=? AND reviewer_id='reviewer'", (first["submission_id"],))
        return value
    monkeypatch.setattr(document_preview, "pdf_snapshot", revoked)
    response = w.client("reviewer").get(preview(base, first))
    assert response.status_code == 404
    assert b"%PDF" not in response.content
    assert w.submissions._connect().execute("SELECT count(*) FROM security_events WHERE actor_id='reviewer' AND action='revision.previewed'").fetchone()[0] == 0


@pytest.mark.parametrize("action_type", ["xref", "inline", "escaped_name"])
def test_preview_revalidates_active_pdf_actions_even_for_retained_files(tmp_path, action_type):
    with fitz.open(stream=pdf(), filetype="pdf") as document:
        if action_type == "xref":
            action = document.get_new_xref()
            document.update_object(action, "<< /S /JavaScript /JS (app.alert('unsafe')) >>")
            document.xref_set_key(document.pdf_catalog(), "OpenAction", f"{action} 0 R")
        else:
            name = "Java#53cript" if action_type == "escaped_name" else "JavaScript"
            document.xref_set_key(document.pdf_catalog(), "OpenAction", f"<< /S /{name} /JS (app.alert('unsafe')) >>")
        malicious = document.tobytes()
    files = PrivateFiles(tmp_path)
    key, digest = files.put(malicious)
    with pytest.raises(HTTPException) as error:
        document_preview.pdf_snapshot(tmp_path, {"filename": "retained.pdf", "storage_key": key, "sha256": digest, "size_bytes": len(malicious)})
    assert error.value.status_code == 422
    assert "PDF" in error.value.detail
