"""Real uploads, object permissions, retained reports, races and copy upgrades."""
import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import revision_routes
from app.models.rules import RuleSet
from app.models.submission import SubmissionStatus
from app.storage import revisions
from app.storage.database import MigrationRequired, require_security_schema
from app.storage.migrate import migration_scripts, statements, upgrade_target

from .test_phase1_security import PAPER, password_hash, world  # noqa: F401


def create_paper(w, data=PAPER):
    client = w.client("author")
    result = client.post(f"/api/v1/conferences/{w.conf.conference_id}/submissions",
                         files={"file": ("paper.tex", data)})
    assert result.status_code == 201, result.text
    base = "/api/v1/submissions/" + result.json()["submission_id"]
    history = client.get(base + "/revisions").json()
    return base, history["revisions"][0]


def upload(client, base, parent, data=PAPER + b"\n% revised", key=None):
    return client.post(base + "/revisions", files={"file": ("revision.tex", data)},
                       data={"parent_revision_id": parent["revision_id"], "request_key": key or uuid4().hex,
                             "change_summary": "Responded to feedback"})


def test_revisions_retain_files_reports_rules_metadata_and_issue_origins(world):
    w = world
    base, first = create_paper(w)
    client = w.client("author")
    checks_url = base + f"/revisions/{first['revision_id']}/checks"
    original = client.get(checks_url).json()
    assert len(original) == 1
    assert original[0]["assessment"]["facts"]["file"]["sha256"] == hashlib.sha256(PAPER).hexdigest()
    assert original[0]["issues"]
    rules = RuleSet(name="New conference policy")
    rules.sections.abstract_required = False
    w.versions.save(rules, w.conf.conference_id)
    result = upload(client, base, first)
    assert result.status_code == 201, result.text
    second = result.json()
    assert second["number"] == 2 and second["parent_revision_id"] == first["revision_id"]
    assert second["template_id"] == first["template_id"] == w.version.template_id
    assert "storage_key" not in second and "rules_json" not in second
    assert client.get(base + "/file").content == PAPER + b"\n% revised"
    assert client.get(base + f"/revisions/{first['revision_id']}/file").content == PAPER
    assert client.get(checks_url).json() == original
    assert client.get(base + "/revisions").json()["current_revision_id"] == second["revision_id"]
    assert client.get(base).json()["filename"] == "revision.tex"


def test_reports_and_revisions_reject_mutations_at_database_level(world):
    base, first = create_paper(world)
    conn = world.submissions._connect()
    for sql in ["UPDATE paper_revisions SET filename='changed'", "DELETE FROM paper_revisions",
                "UPDATE revision_checks SET status='passed'", "DELETE FROM revision_checks"]:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(sql)
    assert world.client("author").get(base + f"/revisions/{first['revision_id']}/file").content == PAPER


def test_recheck_appends_against_pinned_rules_without_changing_current_revision_score(world):
    w = world
    base, first = create_paper(w)
    client = w.client("author")
    first_url = base + f"/revisions/{first['revision_id']}/checks"
    original = client.get(first_url).json()[0]
    better = PAPER.replace(b"A paper.", br"\begin{abstract}An abstract.\end{abstract}A paper.")
    assert upload(client, base, first, better).status_code == 201
    score = client.get(base).json()["compliance_score"]
    w.versions.save(RuleSet(name="Changed policy"), w.conf.conference_id)
    result = client.post(base + "/check-compliance", json={"revision_id": first["revision_id"]})
    assert result.status_code == 200, result.text
    assert result.json()["assessment"] == original["assessment"]
    assert result.json()["run_id"] != original["run_id"]
    assert client.get(first_url).json()[1] == original
    assert client.get(base).json()["compliance_score"] == score
    assert len(w.issues.list_by_submission(base.rsplit('/', 1)[1])) == len(original["issues"]) + len(
        client.get(base + '/revisions/' + client.get(base+'/revisions').json()['current_revision_id'] + '/checks').json()[0]['issues'])


@pytest.mark.parametrize("actor", ["other", "unassigned", "outsider"])
def test_revision_endpoints_do_not_leak_other_papers(world, actor):
    base, first = create_paper(world)
    client = world.client(actor)
    for suffix in ["/revisions", f"/revisions/{first['revision_id']}/checks", f"/revisions/{first['revision_id']}/file"]:
        assert client.get(base + suffix).status_code == 404
    assert upload(client, base, first).status_code == 404
    assert client.post(base + "/check-compliance").status_code == 404


def test_reviewers_read_history_but_cannot_upload_or_recheck(world):
    w = world
    base, first = create_paper(w)
    paper_id = base.rsplit('/', 1)[1]
    w.submissions.assign_reviewer(paper_id, "reviewer", "chair")
    client = w.client("reviewer")
    assert client.get(base + "/revisions").status_code == 200
    assert not client.get(base + "/revisions").json()["can_upload_revision"]
    assert client.get(base + f"/revisions/{first['revision_id']}/file").content == PAPER
    assert upload(client, base, first).status_code == 403
    assert client.post(base + "/check-compliance").status_code == 403
    w.submissions._connect().execute("DELETE FROM review_assignments WHERE submission_id=?", (paper_id,))
    assert client.get(base + "/revisions").status_code == 404


def test_revision_ids_are_scoped_and_finalized_papers_are_locked(world):
    w = world
    base, first = create_paper(w)
    _, other = create_paper(w)
    client = w.client("author")
    assert client.get(base + f"/revisions/{other['revision_id']}/checks").status_code == 404
    assert client.post(base + "/check-compliance", json={"revision_id": other["revision_id"]}).status_code == 404
    w.submissions.update_status(base.rsplit('/', 1)[1], SubmissionStatus.ACCEPTED)
    assert upload(client, base, first).status_code == 409
    assert client.get(base + f"/revisions/{first['revision_id']}/file").status_code == 200


def test_duplicate_stale_and_retry_uploads_are_safe(world):
    base, first = create_paper(world)
    client = world.client("author")
    assert upload(client, base, first, PAPER).status_code == 409
    key = uuid4().hex
    second = upload(client, base, first, key=key)
    assert second.status_code == 201
    assert upload(client, base, first, key=key).json() == second.json()
    assert upload(client, base, first, PAPER + b"\n% different", key=key).status_code == 409
    assert upload(client, base, first, PAPER + b"\n% stale").status_code == 409
    assert len(client.get(base + "/revisions").json()["revisions"]) == 2


def test_concurrent_uploads_have_one_winner(world, monkeypatch):
    w = world
    base, first = create_paper(w)
    client = w.client("author")
    original = revision_routes.evaluate_document
    barrier = Barrier(2, timeout=10)
    def simultaneous(*args, **kwargs):
        result = original(*args, **kwargs)
        barrier.wait()
        return result
    monkeypatch.setattr(revision_routes, "evaluate_document", simultaneous)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(upload, client, base, first, PAPER + f"\n% branch {i}".encode()) for i in range(2)]
        results = [f.result(timeout=20) for f in futures]
    assert sorted(r.status_code for r in results) == [201, 409], [r.text for r in results]
    assert len(client.get(base + "/revisions").json()["revisions"]) == 2


def test_failed_revision_write_rolls_back_and_removes_only_new_file(world, monkeypatch):
    w = world
    base, first = create_paper(w)
    before = set((w.tmp_path / "private").iterdir())
    client = w.client("author")
    def fail(*args):
        raise sqlite3.OperationalError("simulated failure")
    monkeypatch.setattr(w.submissions, "audit", fail)
    with TestClient(w.app, base_url="https://testserver", raise_server_exceptions=False) as failing:
        failing.headers["Authorization"] = client.headers["Authorization"]
        assert upload(failing, base, first).status_code == 500
    assert set((w.tmp_path / "private").iterdir()) == before
    assert len(client.get(base + "/revisions").json()["revisions"]) == 1


def test_recheck_failure_is_retained_and_previous_report_survives(world, monkeypatch):
    base, first = create_paper(world)
    client = world.client("author")
    url = base + f"/revisions/{first['revision_id']}/checks"
    original = client.get(url).json()[0]
    def fail(*args):
        raise RuntimeError("private internals")
    monkeypatch.setattr(revision_routes, "evaluate_document", fail)
    failed = client.post(base + "/check-compliance")
    assert failed.status_code == 200
    assert failed.json()["status"] == "unable_to_validate"
    assert "private internals" not in failed.text
    assert client.get(url).json()[1] == original
    assert client.get(base).json()["compliance_score"] is None


def test_legacy_file_is_not_overwritten_or_fabricated_as_revision(world):
    w = world
    base = "/api/v1/submissions/" + w.submission.submission_id
    client = w.client("author")
    assert client.get(base + "/revisions").json()["revisions"] == []
    assert upload(client, base, {"revision_id": "missing"}).status_code == 409
    assert client.post(base + "/check-compliance").status_code == 409
    assert client.get(base + "/file").content == PAPER


def version_two(path):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,applied_at TEXT,checksum TEXT)")
        for version, script, checksum in migration_scripts():
            if version <= 2:
                for sql in statements(script):
                    conn.execute(sql)
                conn.execute("INSERT INTO schema_migrations VALUES (?,?,?)", (version, "original", checksum))
        conn.execute("INSERT INTO users VALUES ('existing','user@example.org','password-hash','Name',1,'created','updated')")


def test_copy_upgrade_preserves_source_and_records_and_refuses_overwrite(tmp_path):
    source, target = tmp_path / "v2.db", tmp_path / "v3.db"
    version_two(source)
    original = source.read_bytes()
    with pytest.raises(ValueError, match="offline"):
        upgrade_target(source, target)
    upgrade_target(source, target, offline=True)
    assert source.read_bytes() == original
    with sqlite3.connect(target) as conn:
        require_security_schema(conn)
        from app.storage.migrate import MIGRATIONS
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == MIGRATIONS[-1][0]
        assert conn.execute("SELECT hashed_password,created_at FROM users").fetchone() == ("password-hash", "created")
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    before = target.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        upgrade_target(source, target, offline=True)
    assert target.read_bytes() == before
    assert target.stat().st_mode & 0o777 == 0o600


def test_v2_is_read_compatible_but_revision_operations_require_upgrade(tmp_path):
    from app.storage.submission_store import SubmissionStore
    source = tmp_path / "v2.db"
    version_two(source)
    store = SubmissionStore(source)
    require_security_schema(store._connect())
    with pytest.raises(MigrationRequired, match="Phase 2"):
        revisions.require_revisions(store)
    assert not store._connect().execute("SELECT 1 FROM sqlite_master WHERE name='paper_revisions'").fetchone()
    store.close()


def test_wal_upgrade_publishes_self_contained_database(tmp_path):
    from app.storage.migrate import MIGRATIONS
    source, target = tmp_path / "wal.db", tmp_path / "upgraded.db"
    version_two(source)
    with sqlite3.connect(source) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("UPDATE users SET full_name='WAL record'")
        writer.commit()
        upgrade_target(source, target, offline=True)
        # immutable=1 reads the published main file without consulting sidecars.
        with sqlite3.connect(target.as_uri() + "?immutable=1", uri=True) as conn:
            assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == MIGRATIONS[-1][0]
            assert conn.execute("SELECT full_name FROM users").fetchone()[0] == "WAL record"
            assert conn.execute("SELECT name FROM sqlite_master WHERE name='paper_revisions'").fetchone()
    assert not target.with_name(target.name + "-wal").exists()
