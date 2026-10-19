"""Build a versioned workflow database without modifying legacy source files.

Dry-run is the default. --apply writes a NEW target only, never upgrades sources.
"""
import argparse
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS = ((1, "001_initial.sql"), (2, "002_security.sql"), (3, "003_revisions.sql"), (4, "004_collaboration.sql"), (5, "005_reviews.sql"), (6, "006_conference_intake.sql"), (7, "007_google_auth.sql"), (8, "008_conference_invitations.sql"))


def migration_scripts():
    import hashlib
    for version, filename in MIGRATIONS:
        script = (Path(__file__).parent / "migrations" / filename).read_text()
        yield version, script, hashlib.sha256(script.encode()).hexdigest()


def sources():
    from . import (
        conference_store,
        issue_store,
        notification_store,
        report_store,
        submission_store,
        template_store,
        template_version_store,
        user_store,
    )
    return [user_store, conference_store, template_store, template_version_store,
            submission_store, issue_store, notification_store, report_store]


def statements(script):
    pending = ""
    for line in script.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            yield pending
            pending = ""
    if pending.strip():
        raise ValueError("Incomplete migration statement")


def initialize_connection(conn):
    """Fresh database only; transactional schema and recorded migration versions."""
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone():
            from .database import require_security_schema
            require_security_schema(conn)
            conn.commit()
            return
        conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, checksum TEXT NOT NULL)")
        for version, script, checksum in migration_scripts():
            for sql in statements(script):
                conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations VALUES (?, ?, ?)",
                         (version, datetime.now(timezone.utc).isoformat(), checksum))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def inspect_sources(source_dir):
    """Read counts only, including WAL-visible records; no private record output."""
    inventory = []
    for module in sources():
        path = (source_dir / module.DB_FILENAME).resolve()
        if not path.is_file():
            continue
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            counts = {table: conn.execute('SELECT COUNT(*) FROM "' + table.replace('"', '""') + '"').fetchone()[0] for table in tables}
        inventory.append({"path": str(path), "tables": counts})
    return inventory



def preflight(source_dir):
    """Report dangling relational references using read-only queries, never identities."""
    inventory = inspect_sources(source_dir)
    tables = {table: Path(entry["path"]) for entry in inventory for table in entry["tables"]}
    issues = []
    if "schema_migrations" in tables:
        issues.append({"reason": "Sources already contain versioned data; use a verified backup instead"})
        return issues
    relationships = {
        "conference_members": [("user_id", "users", "user_id"), ("conference_id", "conferences", "conference_id")],
        "template_versions": [("conference_id", "conferences", "conference_id")],
        "submissions": [("conference_id", "conferences", "conference_id"), ("reviewer_id", "users", "user_id")],
        "discussion_threads": [("submission_id", "submissions", "submission_id")],
        "review_assignments": [("submission_id", "submissions", "submission_id"), ("reviewer_id", "users", "user_id"), ("assigned_by", "users", "user_id")],
        "issues": [("submission_id", "submissions", "submission_id"), ("assignee_id", "users", "user_id"), ("resolved_by", "users", "user_id")],
        "issue_comments": [("issue_id", "issues", "issue_id"), ("author_id", "users", "user_id")],
        "notifications": [("user_id", "users", "user_id")],
    }
    # Only hard-coded schema identifiers enter SQL below.
    cache = {}
    for table, relations in relationships.items():
        if table not in tables:
            continue
        for column, target, target_column in relations:
            key = (target, target_column)
            if key not in cache:
                cache[key] = set()
                if target in tables:
                    with sqlite3.connect(tables[target].as_uri() + "?mode=ro", uri=True) as conn:
                        cache[key] = {row[0] for row in conn.execute(f'SELECT "{target_column}" FROM "{target}"')}
            with sqlite3.connect(tables[table].as_uri() + "?mode=ro", uri=True) as conn:
                count = sum(row[0] is not None and row[0] not in cache[key] for row in conn.execute(f'SELECT "{column}" FROM "{table}"'))
            if count:
                issues.append({"table": table, "column": column, "unresolved_references": count})
    return issues

def create_target(target, source_dir=None, *, offline=False):
    if target.exists():
        raise ValueError("Target already exists; refusing to overwrite")
    if source_dir is not None and not offline:
        raise ValueError("Stop application writers and confirm --offline before copying legacy databases")
    if source_dir is not None and preflight(source_dir):
        raise ValueError("Legacy references need reconciliation; run the read-only preflight")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".paper-migration-", dir=target.parent) as staging:
        staged = Path(staging) / "platform.db"
        with sqlite3.connect(staged) as conn:
            initialize_connection(conn)
            conn.execute("BEGIN IMMEDIATE")
            try:
                if source_dir is not None:
                    for entry in inspect_sources(source_dir):
                        source = Path(entry["path"])
                        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as old:
                            if "schema_migrations" in entry["tables"]:
                                raise ValueError("Source is already versioned; use a verified backup rather than a legacy import")
                            for table, count in entry["tables"].items():
                                if table in {"schema_migrations", "auth_sessions", "request_limits"}:
                                    continue  # existing sessions are deliberately invalidated
                                if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                                    raise ValueError("Unexpected legacy table; reconcile the source before migration")
                                quoted = '"' + table.replace('"', '""') + '"'
                                cols = [row[1] for row in old.execute("PRAGMA table_info(" + quoted + ")")]
                                names = ','.join('"' + col.replace('"', '""') + '"' for col in cols)
                                cursor = old.execute("SELECT " + names + " FROM " + quoted)
                                while rows := cursor.fetchmany(500):
                                    conn.executemany("INSERT INTO " + quoted + " (" + names + ") VALUES (" + ','.join('?' for _ in cols) + ")", rows)
                                if conn.execute("SELECT COUNT(*) FROM " + quoted).fetchone()[0] != count:
                                    raise ValueError("Source changed or verification failed; migration aborted")
                    # Legacy rows arrive after empty-target migrations have run.
                    # Supply only new catalog/history records; never infer owners
                    # or change the imported submission and formatting records.
                    if conn.execute("SELECT 1 FROM schema_migrations WHERE version=6").fetchone():
                        conn.execute(
                            "INSERT INTO submission_catalog SELECT submission_id,conference_id,"
                            "row_number() OVER (PARTITION BY conference_id ORDER BY created_at,submission_id) FROM submissions"
                        )
                        conn.execute(
                            "INSERT INTO submission_metadata_versions SELECT submission_id,1,conference_id,NULL,'','','[]','legacy',NULL,NULL,updated_at FROM submissions"
                        )
                if conn.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("Legacy references need reconciliation; migration aborted")
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Database integrity verification failed")
        os.chmod(staged, 0o600)
        # Atomic, refuses an existing target even if another process raced us.
        os.link(staged, target)


def upgrade_target(source, target, *, offline=False):
    """Upgrade a consistent copy, retaining the entire source database for rollback."""
    from .database import require_security_schema
    if not offline:
        raise ValueError("Stop application writers and confirm --offline before upgrading")
    if target.exists():
        raise ValueError("Target already exists; refusing to overwrite")
    source = source.resolve(strict=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".paper-upgrade-", dir=target.parent) as staging:
        staged = Path(staging) / "platform.db"
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as old:
            require_security_schema(old)
            with closing(sqlite3.connect(staged)) as conn:
                old.backup(conn)
        with closing(sqlite3.connect(staged)) as conn:
            # A backup inherits WAL mode. Publish a self-contained main file,
            # never a database whose applied migration still lives in a WAL.
            conn.execute("PRAGMA journal_mode=DELETE")
            require_security_schema(conn)
            applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            for version, script, checksum in migration_scripts():
                if version not in applied:
                    for sql in statements(script):
                        conn.execute(sql)
                    conn.execute("INSERT INTO schema_migrations VALUES (?,?,?)",
                                 (version, datetime.now(timezone.utc).isoformat(), checksum))
            if conn.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Foreign key verification failed")
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Database integrity verification failed")
            conn.commit()
            require_security_schema(conn)
        with closing(sqlite3.connect(staged.as_uri() + "?mode=ro", uri=True)) as conn:
            require_security_schema(conn)
            if conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] != MIGRATIONS[-1][0]:
                raise ValueError("Staged database does not contain the completed upgrade")
        with staged.open("rb") as durable:
            os.fsync(durable.fileno())
        os.chmod(staged, 0o600)
        os.link(staged, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--source-dir", type=Path)
    inputs.add_argument("--upgrade-from", type=Path)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    report = {"target": str(args.target), "mode": "apply" if args.apply else "dry-run",
              "sources": inspect_sources(args.source_dir) if args.source_dir else [],
              "legacy_submission_ownership": "unclaimed; chair-only",
              "preflight_issues": preflight(args.source_dir) if args.source_dir else []}
    if args.upgrade_from:
        from .database import require_security_schema
        with sqlite3.connect(args.upgrade_from.resolve().as_uri() + "?mode=ro", uri=True) as conn:
            require_security_schema(conn)
            report["current_versions"] = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
            report["legacy_submissions_without_revisions"] = conn.execute(
                "SELECT COUNT(*) FROM submissions" + (
                    " WHERE submission_id NOT IN (SELECT submission_id FROM paper_revisions)"
                    if 3 in report["current_versions"] else ""),
            ).fetchone()[0]
        report["upgrade_from"] = str(args.upgrade_from)
        report["target_versions"] = [v for v, _ in MIGRATIONS]
    if args.apply:
        if args.upgrade_from:
            upgrade_target(args.upgrade_from, args.target, offline=args.offline)
        else:
            create_target(args.target, args.source_dir, offline=args.offline)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
