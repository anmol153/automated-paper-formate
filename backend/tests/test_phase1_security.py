"""Adversarial session, paper, file, and transaction regression tests."""
import sqlite3
import zipfile
from io import BytesIO
from types import SimpleNamespace

import pytest
from app import auth
from app.api import routes, submission_routes
from app.api.template_routes import get_template_version_store
from app.config import get_settings
from app.dependencies import get_conference_store
from app.main import create_app
from app.models.conference import ConferenceRole
from app.models.notification import NotificationType
from app.models.report import CheckResult
from app.models.rules import RuleSet, Severity
from app.models.user import UserInDB
from app.parsing.errors import ParseError
from app.security.files import PrivateFiles, validate_document
from app.storage.conference_store import ConferenceStore
from app.storage.database import MigrationRequired, transaction
from app.storage.issue_store import IssueStore, get_issue_store
from app.storage.notification_store import NotificationStore, get_notification_store
from app.storage.report_store import ReportStore
from app.storage.submission_store import SubmissionStore, get_submission_store
from app.storage.template_store import TemplateStore
from app.storage.template_version_store import TemplateVersionStore
from app.storage.user_store import UserStore
from fastapi.testclient import TestClient

PAPER = br'\documentclass{article}\begin{document}\section{Introduction}A paper.\end{document}'


@pytest.fixture(scope="module")
def password_hash():
    return auth.get_password_hash("password123")


@pytest.fixture()
def world(tmp_path, monkeypatch, password_hash):
    path = tmp_path / "platform.db"
    users = UserStore(path)
    for name in ["chair", "author", "other", "reviewer", "unassigned", "coauthor", "outsider"]:
        users.create(UserInDB(user_id=name, email=name + "@example.org", full_name=name, hashed_password=password_hash))
    conferences = ConferenceStore(path)
    submissions = SubmissionStore(path)
    versions = TemplateVersionStore(conferences, path)
    notifications = NotificationStore(path)
    issues = IssueStore(path)
    reports = ReportStore(path)
    templates = TemplateStore(path)
    monkeypatch.setattr(auth, "get_user_store", lambda: users)
    monkeypatch.setattr(routes, "get_report_store", lambda: reports)
    monkeypatch.setattr(routes, "get_store", lambda: templates)
    monkeypatch.setattr(submission_routes, "SUBMISSION_FILE_DIR", tmp_path / "private")
    app = create_app()
    app.dependency_overrides.update({get_conference_store: lambda: conferences,
        get_submission_store: lambda: submissions, get_template_version_store: lambda: versions,
        get_notification_store: lambda: notifications, get_issue_store: lambda: issues})
    conf = conferences.create("Conference")
    for name, role in [("chair", ConferenceRole.OWNER), ("author", ConferenceRole.AUTHOR),
                       ("other", ConferenceRole.AUTHOR), ("coauthor", ConferenceRole.AUTHOR),
                       ("reviewer", ConferenceRole.REVIEWER), ("unassigned", ConferenceRole.REVIEWER)]:
        conferences.add_member(conf.conference_id, name, role)
    version = versions.save(RuleSet(name="Rules"), conf.conference_id)
    clients = []
    cached = {}
    def client(name, *, cookie=False):
        if (name, cookie) in cached:
            return cached[name, cookie]
        result = TestClient(app, base_url="https://testserver")
        login = result.post("/api/v1/auth/login", data={"username": name + "@example.org", "password": "password123"})
        assert login.status_code == 200, login.text
        if not cookie:
            result.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        clients.append(result)
        cached[name, cookie] = result
        return result
    submission = submissions.create(conf.conference_id, version.template_id, "paper.tex")
    key, sha256 = PrivateFiles(tmp_path / "private").put(PAPER)
    submissions.secure(submission.submission_id, "author", key, sha256, len(PAPER))
    submissions.assign_reviewer(submission.submission_id, "reviewer", "chair")
    issue = issues.create_from_check_result(submission.submission_id, CheckResult(
        id="page.limit", name="Page limit", category="page", status="failed", severity=Severity.BLOCKING))
    yield SimpleNamespace(**locals())
    for cl in clients:
        cl.close()
    for store in [users, conferences, submissions, versions, notifications, issues, reports, templates]:
        store.close()


@pytest.mark.parametrize("actor", ["other", "unassigned", "outsider"])
def test_unrelated_people_cannot_read_or_mutate_papers(world, actor):
    w = world
    client = w.client(actor)
    base = "/api/v1/submissions/" + w.submission.submission_id
    for suffix in ["", "/file", "/discussion", "/issues"]:
        assert client.get(base + suffix).status_code == 404
    issue = "/api/v1/issues/" + w.issue.issue_id
    assert client.get(issue).status_code == 404
    assert client.get(issue + "/comments").status_code == 404
    assert client.post(issue + "/comments", json={"text": "Intrusion"}).status_code == 404
    assert client.patch(issue, json={"status": "resolved"}).status_code == 404
    assert client.post(base + "/discussion", json={"text": "Intrusion"}).status_code == 404
    listed = client.get(f"/api/v1/conferences/{w.conf.conference_id}/submissions")
    assert listed.status_code == (403 if actor == "outsider" else 200)
    if actor != "outsider":
        assert listed.json() == []
    assert w.issues.get_comments(w.issue.issue_id) == []


@pytest.mark.parametrize("actor", ["author", "reviewer", "chair"])
def test_participants_can_access_the_named_paper(world, actor):
    base = "/api/v1/submissions/" + world.submission.submission_id
    client = world.client(actor)
    response = client.get(base)
    assert response.status_code == 200
    assert response.json()["reviewer_id"] == ("reviewer" if actor == "chair" else None)
    assert client.get(base + "/file").content == PAPER
    assert client.get(base + "/issues").status_code == 200
    assert client.post(base + "/discussion", json={"text": "Feedback"}).status_code == 201


def test_collaborator_can_read_but_needs_edit_grant_to_resolve(world):
    w = world
    w.submissions._connect().execute("INSERT INTO submission_collaborators VALUES (?,?,0)", (w.submission.submission_id, "coauthor"))
    client = w.client("coauthor")
    assert client.get("/api/v1/submissions/" + w.submission.submission_id).status_code == 200
    url = "/api/v1/issues/" + w.issue.issue_id
    assert client.patch(url, json={"status": "resolved"}).status_code == 403
    w.submissions._connect().execute("UPDATE submission_collaborators SET can_edit=1")
    assert client.patch(url, json={"status": "resolved"}).status_code == 200


def test_author_cannot_change_status_or_assign_reviewers(world):
    base = "/api/v1/submissions/" + world.submission.submission_id
    client = world.client("author")
    assert client.patch(base, json="accepted").status_code == 403
    assert client.post(base + "/review", json="unassigned").status_code == 403
    assert client.post(base + "/verdict", json={"verdict": "accept", "score": 99}).status_code == 403
    assert world.submissions.get(world.submission.submission_id).status.value == "draft"


def test_legacy_ownership_is_not_inferred(world):
    w = world
    legacy = w.submissions.create(w.conf.conference_id, w.version.template_id, "legacy.pdf")
    w.submissions.assign_reviewer(legacy.submission_id, "reviewer", "chair")
    url = "/api/v1/submissions/" + legacy.submission_id
    assert w.client("reviewer").get(url).status_code == 404
    assert w.client("author").get(url).status_code == 404
    assert w.client("chair").get(url).status_code == 200
    assert w.client("chair").post(url + "/review", json="unassigned").status_code == 409


def test_revoked_assignment_and_membership_remove_access(world):
    w = world
    url = "/api/v1/submissions/" + w.submission.submission_id
    client = w.client("reviewer")
    assert client.get(url).status_code == 200
    w.submissions._connect().execute("UPDATE review_assignments SET status='revoked'")
    assert client.get(url).status_code == 404
    w.submissions._connect().execute("UPDATE review_assignments SET status='pending'")
    w.conferences.remove_member(w.conf.conference_id, "reviewer")
    assert client.get(url + "/file").status_code == 404


def test_issue_mixed_mutation_is_atomic(world):
    w = world
    url = "/api/v1/issues/" + w.issue.issue_id
    response = w.client("author").patch(url, json={"status": "resolved", "assignee_id": "other"})
    assert response.status_code == 403
    assert w.issues.get(w.issue.issue_id).status.value == "open"
    response = w.client("chair").patch(url, json={"status": "resolved", "assignee_id": "other"})
    assert response.status_code == 400
    assert w.issues.get(w.issue.issue_id).status.value == "open"


def test_cookie_csrf_logout_and_token_replay(world):
    w = world
    client = w.client("chair", cookie=True)
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 403
    csrf = client.cookies.get(auth.CSRF_COOKIE)
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_cookie_flags_and_login_origin(world):
    client = TestClient(world.app, base_url="https://testserver")
    response = client.post("/api/v1/auth/login", data={"username": "author@example.org", "password": "password123"})
    session = next(cookie for cookie in response.headers.get_list("set-cookie") if cookie.startswith(auth.SESSION_COOKIE))
    assert "HttpOnly" in session and "Secure" in session and "SameSite=lax" in session
    assert response.headers["cache-control"] == "private, no-store"
    assert client.post("/api/v1/auth/login", headers={"Origin": "https://evil.example"}, data={"username": "author@example.org", "password": "password123"}).status_code == 403
    assert client.post("/api/v1/auth/register", headers={"Origin": "https://evil.example"}, json={"email": "new@example.org", "full_name": "New", "password": "password123"}).status_code == 403


def test_expired_sessions_deleted_and_disabled_users_are_rejected(world):
    w = world
    client = w.client("author")
    w.users._connect().execute("UPDATE auth_sessions SET expires_at=0")
    assert client.get("/api/v1/auth/me").status_code == 401
    client = w.client("other")
    w.users._connect().execute("UPDATE users SET is_active=0 WHERE user_id='other'")
    assert client.get("/api/v1/auth/me").status_code == 401
    client = w.client("outsider")
    w.users._connect().execute("DELETE FROM auth_sessions WHERE user_id='outsider'")
    w.users._connect().execute("DELETE FROM users WHERE user_id='outsider'")
    assert client.get("/api/v1/auth/me").status_code == 401
    token = auth.create_access_token({"sub": "chair"})
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_login_throttling(world):
    client = TestClient(world.app)
    for _ in range(10):
        assert client.post("/api/v1/auth/login", data={"username": "author@example.org", "password": "wrong"}).status_code == 401
    response = client.post("/api/v1/auth/login", data={"username": "author@example.org", "password": "wrong"})
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_private_reports_do_not_collide_or_expose_legacy_reports(world):
    w = world
    w.reports.save("legacy.pdf", {"score": 33}, "comparison")
    w.reports.save_for_user("same.pdf", {"score": 11}, "comparison", "author")
    w.reports.save_for_user("same.pdf", {"score": 99}, "comparison", "other")
    author = w.client("author")
    other = w.client("other")
    assert author.get("/api/v1/reports/same.pdf").json()["score"] == 11
    assert other.get("/api/v1/reports/same.pdf").json()["score"] == 99
    assert author.get("/api/v1/reports/legacy.pdf").status_code == 404
    assert author.delete("/api/v1/reports/same.pdf").status_code == 200
    assert other.get("/api/v1/reports/same.pdf").status_code == 200
    assert TestClient(w.app).get("/api/v1/reports").status_code == 401


def test_anonymous_assessment_returns_results_without_saving(world):
    w = world
    version = w.templates.create(RuleSet(name="Public rules"))
    client = TestClient(w.app)
    response = client.post("/api/v1/submissions", data={"template_id": version.template_id}, files={"files": ("anonymous.tex", PAPER)})
    assert response.status_code == 200
    assert response.json()["papers"][0]["filename"] == "anonymous.tex"
    assert w.reports.list() == []


def test_template_mutations_require_ownership(world):
    w = world
    author = w.client("author")
    created = author.post("/api/v1/templates", json=RuleSet(name="Owned").model_dump())
    assert created.status_code == 201
    tid = created.json()["template_id"]
    other = w.client("other")
    assert other.delete("/api/v1/templates/" + tid).status_code == 403
    assert other.put("/api/v1/templates/" + tid, json=RuleSet(name="Attack").model_dump()).status_code == 403
    assert author.delete("/api/v1/templates/" + tid).status_code == 200
    assert TestClient(w.app).post("/api/v1/templates", json={"name": "Anonymous"}).status_code == 401
    assert other.post(f"/api/v1/conferences/{w.conf.conference_id}/templates", json={"name": "Attack"}).status_code == 403


def test_reviewer_identity_and_notification_recipients_are_filtered(world):
    w = world
    base = "/api/v1/submissions/" + w.submission.submission_id
    reviewer = w.client("reviewer")
    assert reviewer.post(base + "/discussion", json={"text": "Please revise"}).status_code == 201
    messages = w.client("author").get(base + "/discussion").json()["messages"]
    assert messages[0]["author"] == "Reviewer"
    assert w.notifications.list_by_user("other") == []
    assert w.notifications.list_by_user("unassigned") == []
    assert w.notifications.list_by_user("author")
    # Old conference-wide notifications are also protected after migration.
    leak = w.notifications.create("other", NotificationType.DISCUSSION_MENTION, "Private", "Private body", related_id=w.submission.submission_id)
    other = w.client("other")
    assert other.get("/api/v1/notifications").json() == []
    assert other.get("/api/v1/notifications/count-unread").json() == {"count": 0}
    assert other.patch("/api/v1/notifications/" + leak.notification_id).status_code == 404
    assert w.client("author").get(f"/api/v1/conferences/{w.conf.conference_id}").json()["members"] == []
    assert TestClient(w.app).get("/api/v1/conferences").json()[0]["members"] == []


def test_upload_atomic_failure_discards_file_and_database_changes(world, monkeypatch):
    w = world
    client = w.client("author")
    before_files = set((w.tmp_path / "private").iterdir())
    before_papers = w.submissions.list_by_conference(w.conf.conference_id)
    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("simulated storage failure")
    monkeypatch.setattr(w.submissions, "audit", fail)
    with TestClient(w.app, base_url="https://testserver", raise_server_exceptions=False) as failing:
        failing.headers["Authorization"] = client.headers["Authorization"]
        response = failing.post(f"/api/v1/conferences/{w.conf.conference_id}/submissions", files={"file": ("new.tex", PAPER)})
    assert response.status_code == 500
    assert set((w.tmp_path / "private").iterdir()) == before_files
    assert w.submissions.list_by_conference(w.conf.conference_id) == before_papers


def test_file_integrity_size_and_traversal_controls(world, monkeypatch):
    w = world
    security = w.submissions.security(w.submission.submission_id)
    file = PrivateFiles(w.tmp_path / "private").path(security["storage_key"])
    file.write_bytes(b"tampered")
    assert w.client("author").get("/api/v1/submissions/" + w.submission.submission_id + "/file").status_code == 409
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 1024)
    response = w.client("author").post(f"/api/v1/conferences/{w.conf.conference_id}/submissions", files={"file": ("large.tex", PAPER * 100)})
    assert response.status_code == 413
    assert len(w.submissions.list_by_conference(w.conf.conference_id)) == 1
    with pytest.raises(Exception) as failure:
        PrivateFiles(w.tmp_path).path("../escape")
    assert failure.value.status_code == 404


def test_malicious_word_archive_is_rejected():
    data = BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", '<!DOCTYPE doc [<!ENTITY x "unsafe">]><doc />')
        archive.writestr("../outside", "unsafe")
    with pytest.raises(ParseError):
        validate_document(data.getvalue(), "paper.docx")


def test_unified_transactions_rollback_and_reject_split_databases(world, tmp_path):
    w = world
    before = w.submissions.list_by_conference(w.conf.conference_id)
    with pytest.raises(RuntimeError):
        with transaction(w.submissions, w.conferences):
            w.submissions.create(w.conf.conference_id, w.version.template_id, "rollback.pdf")
            w.conferences.update(w.conf.conference_id, name="Rollback")
            raise RuntimeError("rollback")
    assert w.submissions.list_by_conference(w.conf.conference_id) == before
    assert w.conferences.get(w.conf.conference_id).name == "Conference"
    with pytest.raises(MigrationRequired):
        with transaction(w.submissions, IssueStore(tmp_path / "other.db")):
            pass


def test_chunked_request_is_bounded_before_multipart_parsing(world, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_batch_bytes", 1024)
    app = create_app()
    client = TestClient(app)
    body = b'x' * (1048576 + 2048)
    response = client.post("/api/v1/parse", content=iter([body]), headers={"Content-Type": "multipart/form-data; boundary=test"})
    assert response.status_code == 413


def test_wrong_origin_cookie_mutation_and_invalid_bearer_do_not_fall_back(world):
    w = world
    client = w.client("author", cookie=True)
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    csrf = client.cookies.get(auth.CSRF_COOKIE)
    url = "/api/v1/submissions/" + w.submission.submission_id + "/discussion"
    assert client.post(url, json={"text": "Forged"}, headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"}).status_code == 403
    assert client.post(url, json={"text": "Valid"}, headers={"X-CSRF-Token": csrf}).status_code == 201


def test_no_self_assignment_and_conference_retains_a_chair(world):
    w = world
    chair = w.client("chair")
    url = f"/api/v1/conferences/{w.conf.conference_id}/members/chair"
    assert chair.delete(url).status_code == 409
    assert chair.post(url.rsplit("/", 1)[0], json={"user_id": "chair", "role": "author"}).status_code == 409
    w.conferences.add_member(w.conf.conference_id, "author", ConferenceRole.REVIEWER)
    assert chair.post("/api/v1/submissions/" + w.submission.submission_id + "/review", json="author").status_code == 409


def test_shared_google_credentials_require_an_explicit_user_grant(world, monkeypatch):
    monkeypatch.setattr(routes, "auth_mode", lambda: "service-account")
    client = world.client("author")
    assert client.post("/api/v1/drive/preview", json={"folder_url": "https://drive.google.com/drive/folders/abcdefghijk"}).status_code == 403
    assert client.post("/api/v1/submissions/google-doc", json={"document_url": "https://docs.google.com/document/d/abcdefghijk/edit"}).status_code == 403


def test_reviewer_score_does_not_leak_as_formatting_score(world):
    w = world
    url = "/api/v1/submissions/" + w.submission.submission_id
    before = w.client("author").get(url).json()["compliance_score"]
    response = w.client("reviewer").post(url + "/verdict", json={"verdict": "accept", "score": 98})
    assert response.status_code == 200
    author_view = w.client("author").get(url).json()
    assert author_view["verdict"] is None
    assert author_view["compliance_score"] == before
    assert w.client("chair").get(url).json()["verdict"] == "accept"
    assert w.submissions._connect().execute("SELECT score FROM legacy_review_feedback").fetchone()[0] == 98


def test_spa_fallback_cannot_serve_private_or_parent_files(tmp_path, monkeypatch):
    from app import main
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("Public app")
    (tmp_path / "secret.txt").write_text("private marker")
    monkeypatch.setattr(main, "FRONTEND_DIR", frontend)
    client = TestClient(main.create_app())
    response = client.get("/%2e%2e/secret.txt")
    assert response.status_code == 404
    assert "private marker" not in response.text
    assert client.get("/api/missing-route").status_code == 404
    assert client.get("/conferences").text == "Public app"


def test_expired_cookie_is_cleared_so_anonymous_checking_can_continue(world):
    w = world
    client = w.client("author", cookie=True)
    w.users._connect().execute("UPDATE auth_sessions SET expires_at=0")
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.cookies.get(auth.SESSION_COOKIE) is None
    version = w.templates.create(RuleSet(name="Public rules"))
    response = client.post("/api/v1/submissions", data={"template_id": version.template_id}, files={"files": ("paper.tex", PAPER)})
    assert response.status_code == 200
