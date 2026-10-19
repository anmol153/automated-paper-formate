"""Regression coverage for startup, routes, and existing conference integrations."""
from pathlib import Path

import pytest
from app.api import submission_routes
from app.api.template_routes import get_template_version_store
from app.auth import create_access_token, get_current_user_id
from app.dependencies import get_conference_store
from app.main import create_app
from app.models.conference import ConferenceRole
from app.models.document import TextFormat
from app.models.notification import NotificationType
from app.models.rules import RuleSet
from app.models.submission import SubmissionStatus
from app.storage.conference_store import ConferenceStore
from app.storage.issue_store import IssueStore, get_issue_store
from app.storage.notification_store import NotificationStore, get_notification_store
from app.storage.submission_store import SubmissionStore, get_submission_store
from app.storage.template_version_store import TemplateVersionStore
from app.utils.diff_engine import diff_rulesets
from fastapi.testclient import TestClient


@pytest.fixture()
def workflow(tmp_path, monkeypatch):
    from app import auth
    from app.models.user import UserInDB
    from app.storage.user_store import UserStore
    path = tmp_path / "platform.db"
    users = UserStore(path)
    for user_id in ["owner", "reviewer"]:
        users.create(UserInDB(user_id=user_id, email=user_id + "@example.org", full_name=user_id, hashed_password="unused"))
    monkeypatch.setattr(auth, "get_user_store", lambda: users)
    conferences = ConferenceStore(path)
    submissions = SubmissionStore(path)
    versions = TemplateVersionStore(conferences, path)
    notifications = NotificationStore(path)
    issues = IssueStore(path)
    monkeypatch.setattr(submission_routes, "SUBMISSION_FILE_DIR", tmp_path / "files")
    monkeypatch.setattr(submission_routes, "get_issue_store", lambda: issues)
    app = create_app()
    app.dependency_overrides.update({
        get_current_user_id: lambda: "owner",
        get_issue_store: lambda: issues,
        get_conference_store: lambda: conferences,
        get_submission_store: lambda: submissions,
        get_template_version_store: lambda: versions,
        get_notification_store: lambda: notifications,
    })
    conf = conferences.create("Baseline")
    conferences.add_member(conf.conference_id, "owner", ConferenceRole.OWNER)
    token = create_access_token({"sub": "owner"})
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        yield client, conf, versions, submissions, notifications
    for store in (users, conferences, submissions, versions, notifications, issues):
        store.close()


def test_startup_routes_are_unique(workflow):
    client, *_ = workflow
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    from collections import Counter
    signatures = Counter(
        (method, route.path)
        for route in client.app.routes
        for method in getattr(route, "methods", set())
    )
    assert all(count == 1 for count in signatures.values())
    assert "/api/v1/conferences/{conf_id}/templates" in paths
    assert "/api/v1/conferences/{conf_id}/submissions" in paths
    assert "/api/v1/submissions/{submission_id}" in paths
    assert not any("/conferences/conferences/" in path for path in paths)


def test_template_snapshots_and_diff(workflow):
    client, conf, _, *_ = workflow
    url = f"/api/v1/conferences/{conf.conference_id}/templates"
    rules = RuleSet(name="Same name")
    first = client.post(url, json=rules.model_dump()).json()
    rules.pages.max_pages = 8
    response = client.post(url, json=rules.model_dump())
    assert response.status_code == 201, response.text
    second = response.json()
    assert first["template_id"] != second["template_id"]
    assert client.get(url + "/latest").json()["template_id"] == second["template_id"]
    assert client.get(url + "/" + first["template_id"]).json() == first
    assert len(client.get(url).json()) == 2
    result = client.post(url + "/diff", json={
        "old_template_id": first["template_id"], "new_template_id": second["template_id"],
    })
    assert result.status_code == 200, result.text
    assert result.json()["diff"]["pages"]["changed"]["max_pages"] == [None, 8]
    assert rules.template_id == ""


def test_default_template_store_path(tmp_path, monkeypatch):
    import app.storage.template_version_store as module
    # Exercise the fallback without inheriting the developer's active database.
    monkeypatch.setenv("WORKFLOW_DB_PATH", "")
    monkeypatch.delenv("TEMPLATE_VERSION_DB_PATH", raising=False)
    monkeypatch.setattr(module, "DEFAULT_STORE_DIR", tmp_path)
    conference_store = ConferenceStore(tmp_path)
    store = TemplateVersionStore(conference_store)
    assert store.db_path == tmp_path / "template_versions.db"
    store.close()
    conference_store.close()


def test_upload_list_download_and_discussion(workflow):
    client, conf, versions, submissions, _ = workflow
    versions.save(RuleSet(name="Baseline"), conf.conference_id)
    paper = Path("samples/paper.tex").read_bytes()
    base = f"/api/v1/conferences/{conf.conference_id}/submissions"
    response = client.post(base, files={"file": ("paper.tex", paper, "application/x-tex")})
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["status"] == "submitted"
    assert saved["compliance_score"] is not None
    url = "/api/v1/submissions/" + saved["submission_id"]
    assert client.get(base, params={"q": "paper"}).json() == [saved]
    assert client.get(base, params={"q": "absent"}).json() == []
    assert client.get(url).json() == saved
    assert client.get(url + "/file").content == paper
    thread = client.get(url + "/discussion")
    assert thread.status_code == 200, thread.text
    assert client.get(url).json() == saved
    assert submissions.get(saved["submission_id"]).created_at == saved["created_at"]


@pytest.mark.parametrize("filename", ["../escape.tex", "nested/escape.tex", "broken.pdf"])
def test_bad_upload_creates_no_submission(workflow, filename):
    client, conf, versions, submissions, _ = workflow
    versions.save(RuleSet(name="Baseline"), conf.conference_id)
    response = client.post(f"/api/v1/conferences/{conf.conference_id}/submissions",
                           files={"file": (filename, b"invalid", "application/octet-stream")})
    assert response.status_code == 400, response.text
    assert submissions.list_by_conference(conf.conference_id) == []


def test_assignment_and_timestamp_round_trip(workflow):
    _, conf, _, store, _ = workflow
    submission = store.create(conf.conference_id, "template", "paper.pdf")
    assignment = store.assign_reviewer(submission.submission_id, "reviewer", "owner")
    assert assignment.status == "pending"
    assert store.get_assignment(assignment.assignment_id) == assignment
    assert store.list_assignments(submission.submission_id) == [assignment]
    assert store.get(submission.submission_id).reviewer_id == "reviewer"
    changed = store.update_status(submission.submission_id, SubmissionStatus.UNDER_REVIEW)
    assert changed.created_at == submission.created_at
    assert store.list_by_conference(conf.conference_id) == [changed]


def test_read_all_notifications_uses_static_route(workflow):
    client, conf, _, _, store = workflow
    store.create("owner", NotificationType.MEMBER_ADDED, "Membership", "Added", related_id=conf.conference_id)
    response = client.patch("/api/v1/notifications/read-all")
    assert response.status_code == 200, response.text
    assert response.json() == {"marked": 1}
    assert client.get("/api/v1/notifications/count-unread").json() == {"count": 0}


def test_conference_update_is_persisted(workflow):
    client, conf, *_ = workflow
    url = f"/api/v1/conferences/{conf.conference_id}"
    response = client.patch(url, json={"name": "Updated", "description": "Saved"})
    assert response.status_code == 200, response.text
    assert client.get(url).json()["name"] == "Updated"
    assert client.get(url).json()["description"] == "Saved"


def test_typography_diff_handles_changed_nested_values():
    old = RuleSet(name="Old")
    new = old.model_copy(deep=True)
    new.typography.body = TextFormat(font_size_pt=11)
    diff = diff_rulesets(old, new)
    assert "body" in diff["typography"]["changed"]


def test_registration_and_login_use_the_configured_password_backend(tmp_path, monkeypatch):
    from app import auth
    from app.storage.user_store import UserStore
    store = UserStore(tmp_path)
    monkeypatch.setattr(auth, "get_user_store", lambda: store)
    with TestClient(create_app()) as client:
        user = {"email": "author@example.org", "full_name": "Author", "password": "password123"}
        response = client.post("/api/v1/auth/register", json=user)
        assert response.status_code == 200, response.text
        second = client.post("/api/v1/auth/register", json={**user, "email": "other@example.org"})
        assert second.status_code == 200
        assert response.json()["user_id"] != second.json()["user_id"]
        login = client.post("/api/v1/auth/login", data={"username": user["email"], "password": user["password"]})
        assert login.status_code == 200, login.text
        assert auth.decode_access_token(login.json()["access_token"])["sub"] == response.json()["user_id"]
        assert client.post("/api/v1/auth/login", data={"username": user["email"], "password": "wrong"}).status_code == 401
    store.close()
