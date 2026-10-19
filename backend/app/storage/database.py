"""Shared database configuration and explicit transaction boundaries."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class MigrationRequired(RuntimeError):
    pass


def configured_path(fallback: Path, legacy_env: str) -> Path:
    from app.config import get_settings
    unified = os.environ.get("WORKFLOW_DB_PATH", str(get_settings().workflow_db_path or "")).strip()
    legacy = os.environ.get(legacy_env, "").strip()
    if unified:
        path = Path(unified).expanduser().resolve()
        if legacy and Path(legacy).expanduser().resolve() != path:
            raise MigrationRequired("WORKFLOW_DB_PATH conflicts with a legacy database override")
        if not path.is_file():
            raise MigrationRequired("Initialize the workflow database with app.storage.migrate before enabling WORKFLOW_DB_PATH")
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
            require_security_schema(conn)
        return path
    return Path(legacy).expanduser() if legacy else fallback


def require_security_schema(conn: sqlite3.Connection) -> None:
    from .migrate import migration_scripts
    try:
        recorded = dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())
    except sqlite3.OperationalError as exc:
        raise MigrationRequired("Legacy database requires an explicit migration; see PHASE1.md") from exc
    expected = {version: checksum for version, _, checksum in migration_scripts()}
    # Existing v2 installations keep serving their original features until the
    # operator explicitly copies/upgrades them. Revision endpoints require v3.
    if (not recorded or max(recorded) < 2 or max(recorded) > max(expected)
            or recorded != {v: c for v, c in expected.items() if v <= max(recorded)}):
        raise MigrationRequired("Unsupported or modified workflow schema; see PHASE1.md")


def initialize_if_empty(path: Path) -> None:
    """Initialize only an empty database. Never upgrade an existing installation."""
    from .migrate import initialize_connection
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(descriptor)
    with sqlite3.connect(path) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone():
            initialize_connection(conn)


@contextmanager
def transaction(*stores):
    """Share one connection across related stores; rollback all writes on failure."""
    if not stores or len({store.db_path.resolve() for store in stores}) != 1:
        raise MigrationRequired("Conference writes require one WORKFLOW_DB_PATH; migrate the legacy databases first")
    conn = stores[0]._connect()
    require_security_schema(conn)
    previous = []
    for store in stores:
        previous.append(getattr(store._local, "conn", None))
        store._local.conn = conn
    nested = conn.in_transaction
    try:
        conn.execute("SAVEPOINT workflow" if nested else "BEGIN IMMEDIATE")
        yield conn
        conn.execute("RELEASE SAVEPOINT workflow" if nested else "COMMIT")
    except BaseException:
        if nested:
            conn.execute("ROLLBACK TO SAVEPOINT workflow")
            conn.execute("RELEASE SAVEPOINT workflow")
        elif conn.in_transaction:
            conn.rollback()
        raise
    finally:
        for store, original in zip(stores, previous):
            store._local.conn = original
