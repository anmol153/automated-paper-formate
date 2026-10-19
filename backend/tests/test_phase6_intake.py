"""Conference intake, bibliographic versions, deadlines, isolation and copy upgrade."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.models.submission import SubmissionStatus
from app.services import intake
from app.storage.migrate import upgrade_target

from .test_phase1_security import PAPER, password_hash, world  # noqa: F401
from .test_phase2_revisions import create_paper, upload
from .test_phase3_collaboration import assign, move


def settings_url(w):
    return f"/api/v1/conferences/{w.conf.conference_id}/settings"


def configure(w, **changes):
    old = w.client("chair").get(settings_url(w)).json()
    result = w.client("chair").put(settings_url(w), json={"expected_version": old["version"], "settings": {**old["settings"], **changes}})
    assert result.status_code == 200, result.text
    return result.json()


def track(w, name="Systems"):
    result = w.client("chair").post(f"/api/v1/conferences/{w.conf.conference_id}/tracks", json={"name": name})
    assert result.status_code == 201, result.text
    return result.json()


def details(w, base, revision, **changes):
    old = w.client("author").get(base + "/metadata").json()["metadata"]
    payload = {key: old[key] for key in ("title", "abstract", "authors", "track_id")}
    payload.update(expected_version=old["version"], expected_revision_id=revision["revision_id"], **changes)
    return payload


def test_settings_are_versioned_private_and_timezone_normalized(world):
    w = world
    first = configure(w, abbreviation="AC", website="https://example.org", research_scope="Systems research",
                      submissions_open_at="2030-01-01T10:00:00+05:30", submissions_close_at="2030-01-10T10:00:00+05:30")
    assert first["version"] == 1 and first["settings"]["submissions_open_at"] == "2030-01-01T04:30:00Z"
    assert not first["submission_window"]["allowed"]
    payload = {"expected_version": 0, "settings": first["settings"]}
    assert w.client("chair").put(settings_url(w), json=payload).status_code == 409
    assert w.client("author").put(settings_url(w), json=payload).status_code == 403
    assert w.client("outsider").get(settings_url(w)).status_code == 403


@pytest.mark.parametrize("changes", [
    {"website": "javascript:alert(1)"}, {"submissions_close_at": "2030-01-01T10:00:00"},
    {"submissions_open_at": "2030-01-02T00:00:00Z", "submissions_close_at": "2030-01-01T00:00:00Z"},
    {"submissions_close_at": "2030-01-02T00:00:00Z", "revisions_close_at": "2030-01-01T00:00:00Z"},
])
def test_invalid_dates_and_website_are_rejected(world, changes):
    payload = {"expected_version": 0, "settings": changes}
    assert world.client("chair").put(settings_url(world), json=payload).status_code == 422


def test_opening_is_inclusive_and_closing_exclusive(world):
    w = world
    configure(w, submissions_open_at="2030-01-01T00:00:00Z", submissions_close_at="2030-01-02T00:00:00Z")
    assert intake.window(w.submissions, w.conf.conference_id, now=datetime(2030, 1, 1, tzinfo=timezone.utc))["allowed"]
    assert not intake.window(w.submissions, w.conf.conference_id, now=datetime(2030, 1, 2, tzinfo=timezone.utc))["allowed"]


def test_closed_initial_window_blocks_uploads_edits_and_submission_but_retains_files(world):
    w = world
    base, first = create_paper(w)
    w.submissions.update_status(base.rsplit("/", 1)[1], SubmissionStatus.DRAFT)
    configure(w, submissions_close_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    result = w.client("author").post(f"/api/v1/conferences/{w.conf.conference_id}/submissions", files={"file": ("paper.tex", PAPER)})
    assert result.status_code == 409
    assert upload(w.client("author"), base, first).status_code == 409
    assert move(w.client("author"), base, "submitted").status_code == 409
    payload = details(w, base, first, title="A late change")
    assert w.client("author").put(base + "/metadata", json=payload).status_code == 409
    assert w.client("author").get(base + f"/revisions/{first['revision_id']}/file").content == PAPER
    assert not w.client("author").get(base + "/revisions").json()["can_upload_revision"]


def test_deadline_is_rechecked_after_parsing_and_staged_file_is_cleaned(world, monkeypatch):
    from app.api import submission_routes
    w = world
    original = submission_routes.evaluate_document
    def close_during_parse(*args):
        result = original(*args)
        configure(w, submissions_close_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
        return result
    monkeypatch.setattr(submission_routes, "evaluate_document", close_during_parse)
    files = set((w.tmp_path / "private").iterdir())
    response = w.client("author").post(f"/api/v1/conferences/{w.conf.conference_id}/submissions", files={"file": ("paper.tex", PAPER)})
    assert response.status_code == 409 and set((w.tmp_path / "private").iterdir()) == files
    assert len(w.submissions.list_by_conference(w.conf.conference_id)) == 1


def test_requested_revisions_have_their_own_window(world):
    w = world
    base, first = create_paper(w)
    assign(w, base)
    assert move(w.client("chair"), base, "changes_requested", "Please revise").status_code == 200
    configure(w, lifecycle_status="reviewing", submissions_close_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
              revisions_close_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    assert w.client("author").put(base + "/metadata", json=details(w, base, first, title="Revised title")).status_code == 200
    revision = upload(w.client("author"), base, first)
    assert revision.status_code == 201, revision.text
    assert move(w.client("author"), base, "submitted").status_code == 200
    assert move(w.client("chair"), base, "under_review").status_code == 200
    assert move(w.client("chair"), base, "changes_requested", "Another revision").status_code == 200
    configure(w, revisions_close_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    assert upload(w.client("author"), base, revision.json(), PAPER + b"\n% later").status_code == 409


def test_tracks_are_scoped_versioned_and_archived_without_breaking_existing_papers(world):
    w = world
    item = track(w)
    url = f"/api/v1/conferences/{w.conf.conference_id}/tracks/{item['track_id']}"
    assert w.client("chair").post(url.rsplit("/", 1)[0], json={"name": "systems"}).status_code == 409
    base, first = create_paper(w)
    assert w.client("author").put(base + "/metadata", json=details(w, base, first, track_id=item["track_id"])).status_code == 200
    update = {"name": "Systems research", "description": "Archived intake", "active": False, "expected_version": 1}
    assert w.client("chair").put(url, json=update).status_code == 200
    assert w.client("chair").put(url, json=update).status_code == 409
    assert w.client("author").put(base + "/metadata", json=details(w, base, first, title="An existing paper")).status_code == 200
    another, rev = create_paper(w, PAPER + b"\n% another")
    assert w.client("author").put(another + "/metadata", json=details(w, another, rev, track_id=item["track_id"])).status_code == 422
    other = w.client("chair").post("/api/v1/conferences/", json={"name": "Other conference"}).json()
    other_track = w.client("chair").post(f"/api/v1/conferences/{other['conference_id']}/tracks", json={"name": "Other track"}).json()
    assert w.client("author").put(base + "/metadata", json=details(w, base, first, track_id=other_track["track_id"])).status_code == 422


def test_required_metadata_keeps_upload_as_draft_until_completed(world):
    w = world
    item = track(w)
    configure(w, require_title=True, require_abstract=True, require_authors=True, require_track=True)
    base, first = create_paper(w)
    assert w.client("author").get(base).json()["status"] == "draft"
    assert move(w.client("author"), base, "submitted").status_code == 409
    payload = details(w, base, first, title="Research title", abstract="An abstract.", authors=[{"name": "Researcher", "affiliation": "University"}], track_id=item["track_id"])
    assert w.client("author").put(base + "/metadata", json=payload).status_code == 200
    assert move(w.client("author"), base, "submitted").status_code == 200
    paper = w.client("author").get(base).json()
    assert paper["title"] == "Research title" and paper["paper_number"] > 0 and paper["authors"][0]["name"] == "Researcher"
    assert w.client("other").get(base).status_code == 404


def test_initial_declared_metadata_is_saved_without_changing_extracted_report(world):
    w = world
    supplied = {"title": "Declared title", "abstract": "Declared abstract", "authors": [{"name": "Declared author"}]}
    response = w.client("author").post(f"/api/v1/conferences/{w.conf.conference_id}/submissions", files={"file": ("paper.tex", PAPER)}, data={"metadata_json": json.dumps(supplied)})
    assert response.status_code == 201, response.text
    base = "/api/v1/submissions/" + response.json()["submission_id"]
    first = w.client("author").get(base + "/revisions").json()["revisions"][0]
    assert response.json()["title"] == "Declared title" and first["metadata"]["title"] != "Declared title"
    assert w.client("author").get(base + "/metadata").json()["metadata"]["source"] == "declared"
    assert w.client("other").get(base).status_code == 404


def test_metadata_history_optimistic_versions_and_immutable_revisions(world):
    w = world
    base, first = create_paper(w)
    checks = w.client("author").get(base + f"/revisions/{first['revision_id']}/checks").json()
    payload = details(w, base, first, title="New title")
    assert w.client("author").put(base + "/metadata", json=payload).status_code == 200
    assert w.client("author").put(base + "/metadata", json=payload).status_code == 409
    stale = details(w, base, first, title="Stale revision")
    assert upload(w.client("author"), base, first).status_code == 201
    assert w.client("author").put(base + "/metadata", json=stale).status_code == 409
    history = w.client("author").get(base + "/metadata/history", params={"limit": 1}).json()
    assert history[0]["title"] == "New title" and history[0]["revision_id"] == first["revision_id"]
    older = w.client("author").get(base + "/metadata/history", params={"before_version": history[0]["version"]}).json()
    assert older and older[0]["version"] == 1
    assert w.client("author").get(base + f"/revisions/{first['revision_id']}/checks").json() == checks
    for sql in ("UPDATE submission_catalog SET paper_number=100", "DELETE FROM submission_catalog", "UPDATE submission_metadata_versions SET title='oops'", "DELETE FROM submission_metadata_versions"):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            w.submissions._connect().execute(sql)


@pytest.mark.parametrize("actor,expected", [("other", 404), ("reviewer", 403), ("coauthor", 403)])
def test_metadata_writes_enforce_paper_permissions(world, actor, expected):
    w = world
    base, first = create_paper(w)
    assign(w, base)
    w.submissions.update_status(base.rsplit("/", 1)[1], SubmissionStatus.SUBMITTED)
    if actor == "coauthor":
        w.submissions._connect().execute("INSERT INTO submission_collaborators VALUES (?,?,0)", (base.rsplit("/", 1)[1], actor))
    response = w.client(actor).put(base + "/metadata", json=details(w, base, first, title="Unauthorized edit"))
    assert response.status_code == expected


def test_metadata_is_locked_during_review_and_after_finalization(world):
    w = world
    base, first = create_paper(w)
    assign(w, base)
    payload = details(w, base, first, title="Changed")
    assert w.client("author").put(base + "/metadata", json=payload).status_code == 409
    assert move(w.client("chair"), base, "accepted", "Accepted").status_code == 200
    assert w.client("chair").put(base + "/metadata", json=payload).status_code == 409


def test_editing_collaborator_access_and_chair_recusal_are_enforced(world):
    w = world
    base, first = create_paper(w)
    sid = base.rsplit("/", 1)[1]
    w.submissions._connect().execute("INSERT INTO submission_collaborators VALUES (?,?,1)", (sid, "coauthor"))
    assert w.client("coauthor").put(base + "/metadata", json=details(w, base, first, title="Collaborator edit")).status_code == 200
    w.submissions._connect().execute("DELETE FROM submission_collaborators WHERE submission_id=?", (sid,))
    assert w.client("coauthor").get(base + "/metadata/history").status_code == 404
    assert w.client("chair").post(base + "/conflicts", json={"reviewer_id": "chair", "reason": "Institutional conflict"}).status_code == 201
    assert w.client("chair").put(base + "/metadata", json=details(w, base, first, title="Recused edit")).status_code == 403


def test_closed_conference_blocks_new_reviews_and_decisions_and_can_reopen(world):
    from .test_phase4_reviews import setup, save, release
    w = world
    base, first, payload = setup(w)
    configure(w, lifecycle_status="closed")
    assert save(w, base, payload).status_code == 409
    assert not w.client("reviewer").get(base + "/reviews").json()["can_review"]
    assert move(w.client("chair"), base, "accepted", "Too early").status_code == 409
    assert w.client("chair").post(base + "/review", json="unassigned").status_code == 409
    configure(w, lifecycle_status="reviewing")
    assert save(w, base, {**payload, "submit": True}).status_code == 200
    assert move(w.client("chair"), base, "accepted", "Accepted").status_code == 200
    configure(w, lifecycle_status="closed")
    assert release(w, base, first).status_code == 200


def test_malformed_metadata_cannot_grant_access_or_create_partial_papers(world):
    w = world
    url = f"/api/v1/conferences/{w.conf.conference_id}/submissions"
    for payload in ('{invalid', json.dumps({"authors": [{"name": "other", "user_id": "other"}]})):
        response = w.client("author").post(url, files={"file": ("paper.tex", PAPER)}, data={"metadata_json": payload})
        assert response.status_code == 422
    assert len(w.submissions.list_by_conference(w.conf.conference_id)) == 1
    response = w.client("author").post(url, files={"file": ("paper.tex", PAPER)}, data={"metadata_json": json.dumps({"authors": [{"name": "other"}]})})
    assert response.status_code == 201
    assert w.client("other").get("/api/v1/submissions/" + response.json()["submission_id"]).status_code == 404


def test_track_mutations_require_chairs_and_paper_numbers_are_conference_local(world):
    w = world
    assert w.client("author").post(f"/api/v1/conferences/{w.conf.conference_id}/tracks", json={"name": "Forbidden"}).status_code == 403
    item = track(w)
    assert w.client("author").put(f"/api/v1/conferences/{w.conf.conference_id}/tracks/{item['track_id']}", json={"name": "Forbidden", "expected_version": 1}).status_code == 403
    other = w.client("chair").post("/api/v1/conferences/", json={"name": "Another conference"}).json()
    w.versions.save(w.version, other["conference_id"])
    result = w.client("chair").post(f"/api/v1/conferences/{other['conference_id']}/submissions", files={"file": ("paper.tex", PAPER)})
    assert result.status_code == 201, result.text
    assert result.json()["paper_number"] == 1


def test_concurrent_metadata_edits_have_one_winner(world):
    w = world
    base, first = create_paper(w)
    payload = details(w, base, first, title="Concurrent title")
    client = w.client("author")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.put(base + "/metadata", json=payload), range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert len(client.get(base + "/metadata/history").json()) == 2


def test_paper_numbers_are_unique_and_filtering_respects_visibility(world):
    w = world
    client = w.client("author")
    def create(index):
        return client.post(f"/api/v1/conferences/{w.conf.conference_id}/submissions", files={"file": ("paper.tex", PAPER + f"\n% {index}".encode())})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, range(2)))
    assert all(r.status_code == 201 for r in responses)
    numbers = [r.json()["paper_number"] for r in responses]
    assert len(set(numbers)) == 2
    paper = responses[0].json()
    base = "/api/v1/submissions/" + paper["submission_id"]
    revision = client.get(base + "/revisions").json()["revisions"][0]
    item = track(w)
    assert client.put(base + "/metadata", json=details(w, base, revision, title="Searchable research", track_id=item["track_id"])).status_code == 200
    listing = f"/api/v1/conferences/{w.conf.conference_id}/submissions"
    assert len(client.get(listing, params={"q": "Searchable", "track_id": item["track_id"]}).json()) == 1
    assert w.client("other").get(listing, params={"q": "Searchable"}).json() == []


def test_settings_and_metadata_roll_back_when_audit_fails(world, monkeypatch):
    w = world
    base, first = create_paper(w)
    payload = details(w, base, first, title="Must roll back")
    def fail(*args, **kwargs):
        raise RuntimeError("Simulated audit failure")
    monkeypatch.setattr(w.submissions, "audit", fail)
    from fastapi.testclient import TestClient
    with TestClient(w.app, base_url="https://testserver", raise_server_exceptions=False) as client:
        client.headers["Authorization"] = w.client("author").headers["Authorization"]
        assert client.put(base + "/metadata", json=payload).status_code == 500
        client.headers["Authorization"] = w.client("chair").headers["Authorization"]
        assert client.put(settings_url(w), json={"expected_version": 0, "settings": {"abbreviation": "Rollback"}}).status_code == 500
    assert w.client("author").get(base + "/metadata").json()["metadata"]["version"] == 1
    assert w.client("chair").get(settings_url(w)).json()["version"] == 0


def test_archiving_requires_finalized_papers_and_is_terminal(world):
    w = world
    configure(w, lifecycle_status="closed")
    closed = w.client("chair").get(settings_url(w)).json()
    response = w.client("chair").put(settings_url(w), json={"expected_version": closed["version"], "settings": {**closed["settings"], "lifecycle_status": "archived"}})
    assert response.status_code == 409  # The fixture has a legacy draft.
    w.submissions.update_status(w.submission.submission_id, SubmissionStatus.WITHDRAWN)
    archived = configure(w, lifecycle_status="archived")
    assert w.client("chair").put(settings_url(w), json={"expected_version": archived["version"], "settings": {"lifecycle_status": "open"}}).status_code == 409
    assert w.client("chair").post(f"/api/v1/conferences/{w.conf.conference_id}/tracks", json={"name": "New track"}).status_code == 409


@pytest.fixture
def schema5_world(monkeypatch, request):
    from app.storage import migrate
    all_migrations = migrate.MIGRATIONS
    monkeypatch.setattr(migrate, "MIGRATIONS", tuple(item for item in all_migrations if item[0] <= 5))
    w = request.getfixturevalue("world")
    monkeypatch.setattr(migrate, "MIGRATIONS", all_migrations)
    return w


def test_old_schema_keeps_uploads_and_copy_upgrade_backfills_without_inventing_metadata(schema5_world):
    w = schema5_world
    base, first = create_paper(w)
    assert not w.client("chair").get(settings_url(w)).json()["enabled"]
    assert w.client("author").put(base + "/metadata", json={"expected_version": 0, "expected_revision_id": first["revision_id"]}).status_code == 503
    target = w.tmp_path / "upgraded.db"
    upgrade_target(w.submissions.db_path, target, offline=True)
    with sqlite3.connect(target) as conn:
        from app.storage.migrate import MIGRATIONS
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == MIGRATIONS[-1][0]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT count(*) FROM submission_catalog").fetchone()[0] == 2
        assert conn.execute("SELECT title,authors_json,source FROM submission_metadata_versions").fetchall() == [("", "[]", "legacy"), ("", "[]", "legacy")]
    assert w.submissions._connect().execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 5
