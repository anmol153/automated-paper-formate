"""Migration safety: legacy bytes retained, unknown ownership denied, no overwrite."""
import hashlib
import sqlite3

import pytest
from app.storage import conference_store, report_store, submission_store, user_store
from app.storage.database import MigrationRequired
from app.storage.migrate import create_target, main
from app.storage.submission_store import SubmissionStore


@pytest.fixture()
def legacy(tmp_path):
    source = tmp_path / "legacy"
    source.mkdir()
    for module in [user_store, conference_store, submission_store, report_store]:
        with sqlite3.connect(source / module.DB_FILENAME) as conn:
            conn.executescript(module.SCHEMA)
    with sqlite3.connect(source / user_store.DB_FILENAME) as conn:
        conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)", ("chair", "chair@example.org", "existing-hash", "Chair", 1, "original", "original"))
    with sqlite3.connect(source / conference_store.DB_FILENAME) as conn:
        conn.execute("INSERT INTO conferences VALUES (?,?,?,?,?,?,?)", ("conf", "Legacy", "", None, None, "original", "original"))
        conn.execute("INSERT INTO conference_members VALUES (?,?,?,?)", ("chair", "conf", "owner", "original"))
    with sqlite3.connect(source / submission_store.DB_FILENAME) as conn:
        conn.execute("INSERT INTO submissions VALUES (?,?,?,?,?,?,?,?,?,?)", ("paper", "conf", "legacy-template", "paper.pdf", "submitted", None, None, 70, "original", "original"))
    with sqlite3.connect(source / report_store.DB_FILENAME) as conn:
        conn.execute("INSERT INTO reports(filename,kind,report_json,created_at,updated_at) VALUES (?,?,?,?,?)", ("paper.pdf", "comparison", '{"score":70}', "original", "original"))
    return source


def fingerprints(source):
    return {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in source.iterdir() if file.suffix == ".db"}


def test_dry_run_does_not_create_target_or_change_sources(legacy, tmp_path, monkeypatch, capsys):
    before = fingerprints(legacy)
    target = tmp_path / "platform.db"
    monkeypatch.setattr("sys.argv", ["migrate", "--source-dir", str(legacy), "--target", str(target)])
    main()
    assert "dry-run" in capsys.readouterr().out
    assert not target.exists()
    assert fingerprints(legacy) == before


def test_copy_preserves_records_and_quarantines_unknown_ownership(legacy, tmp_path):
    before = fingerprints(legacy)
    target = tmp_path / "platform.db"
    create_target(target, legacy, offline=True)
    with sqlite3.connect(target) as conn:
        from app.storage.migrate import MIGRATIONS
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == MIGRATIONS[-1][0]
        assert conn.execute("SELECT hashed_password FROM users").fetchone()[0] == "existing-hash"
        assert conn.execute("SELECT created_at FROM submissions").fetchone()[0] == "original"
        assert conn.execute("SELECT report_json FROM reports").fetchone()[0] == '{"score":70}'
        assert conn.execute("SELECT COUNT(*) FROM submission_security").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM report_owners").fetchone()[0] == 0
        assert conn.execute("SELECT paper_number FROM submission_catalog WHERE submission_id='paper'").fetchone()[0] == 1
        assert conn.execute("SELECT title,authors_json,source FROM submission_metadata_versions WHERE submission_id='paper'").fetchone() == ("", "[]", "legacy")
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert target.stat().st_mode & 0o777 == 0o600
    assert fingerprints(legacy) == before


def test_copy_requires_offline_confirmation_and_refuses_existing_target(legacy, tmp_path):
    target = tmp_path / "platform.db"
    with pytest.raises(ValueError, match="offline"):
        create_target(target, legacy)
    assert not target.exists()
    target.write_bytes(b"do not overwrite")
    with pytest.raises(ValueError, match="already exists"):
        create_target(target, legacy, offline=True)
    assert target.read_bytes() == b"do not overwrite"


def test_orphaned_legacy_rows_abort_without_partial_target(legacy, tmp_path):
    with sqlite3.connect(legacy / conference_store.DB_FILENAME) as conn:
        conn.execute("INSERT INTO conference_members VALUES ('unknown','conf','author','original')")
    target = tmp_path / "platform.db"
    with pytest.raises(ValueError, match="reconciliation"):
        create_target(target, legacy, offline=True)
    assert not target.exists()


def test_legacy_store_is_not_silently_upgraded(legacy):
    path = legacy / submission_store.DB_FILENAME
    store = SubmissionStore(path)
    with sqlite3.connect(path) as conn:
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
    with pytest.raises(MigrationRequired):
        store.security("paper")
    assert store.get("paper").filename == "paper.pdf"
    store.close()


def test_all_stores_can_use_one_explicitly_initialized_database(tmp_path, monkeypatch):
    target = tmp_path / "platform.db"
    create_target(target)
    for key in ["TEMPLATE", "REPORT", "USER", "CONFERENCE", "SUBMISSION", "ISSUE", "NOTIFICATION", "TEMPLATE_VERSION"]:
        monkeypatch.delenv(key + "_DB_PATH", raising=False)
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(target))
    for module in [user_store, conference_store, submission_store, report_store]:
        cls = {user_store: user_store.UserStore, conference_store: conference_store.ConferenceStore,
               submission_store: submission_store.SubmissionStore, report_store: report_store.ReportStore}[module]
        store = cls()
        assert store.db_path == target
        store.close()
    monkeypatch.setenv("USER_DB_PATH", str(tmp_path / "different.db"))
    with pytest.raises(MigrationRequired, match="conflicts"):
        user_store.UserStore()
