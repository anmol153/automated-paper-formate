"""Small sqlite3-shaped adapter for the application's PostgreSQL backend.

The application has a mature SQLite query layer. This adapter preserves that
interface while translating the small set of SQLite SQL conventions used by
the stores and routes. SQLite remains the default for local development.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path


def database_url() -> str:
    import os
    return (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "").strip()


def enabled() -> bool:
    return bool(database_url())


def shared_path() -> Path:
    # A shared sentinel makes existing transaction guards recognize that all
    # stores use the same logical database; it is never opened as a file.
    return Path("/tmp/paper-format-shared-postgres/workflow.db")


class Row(dict):
    """Mapping row that retains sqlite3.Row-style integer indexing."""
    def __iter__(self):
        # sqlite3.Row iterates over column values, which is relied on by
        # dict(conn.execute(...).fetchall()) for key/value query results.
        return iter(self.values())

    def __getitem__(self, key):
        if isinstance(key, int):
            key = tuple(self.keys())[key]
        return super().__getitem__(key)


def _row_factory(cursor):
    names = [item.name for item in cursor.description]
    return lambda values: Row(zip(names, values))


def _placeholders(sql: str) -> str:
    # Replace qmark parameters without touching quoted SQL string literals.
    out, quote, i = [], None, 0
    while i < len(sql):
        char = sql[i]
        if quote:
            out.append(char)
            if char == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    out.append(sql[i + 1]); i += 1
                else:
                    quote = None
        elif char in ("'", '"'):
            quote = char; out.append(char)
        elif char == "?":
            out.append("%s")
        else:
            out.append(char)
        i += 1
    return "".join(out)


def translate_sql(sql: str) -> tuple[str, bool]:
    text = sql.strip()
    if text.upper().startswith("PRAGMA "):
        return "", False
    text = re.sub(r"^BEGIN\s+IMMEDIATE\b", "BEGIN", text, flags=re.I)
    ignored = bool(re.match(r"^INSERT\s+OR\s+IGNORE\s+INTO\b", text, flags=re.I))
    if ignored:
        text = re.sub(r"^INSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", text, count=1, flags=re.I)
    text = re.sub(
        r"strftime\('%Y-%m-%dT%H:%M:%fZ',\s*'now'\)",
        "to_char(timezone('UTC', CURRENT_TIMESTAMP), 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"')",
        text, flags=re.I,
    )
    text = re.sub(r"strftime\('%s',\s*'now'\)", "EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)::bigint", text, flags=re.I)
    text = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+COLLATE\s+NOCASE\b", r"lower(\1)", text, flags=re.I)
    text = _placeholders(text)
    if ignored:
        text = text.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return text, True


class Cursor:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        return self._cursor.fetchmany(size) if size else self._cursor.fetchmany()


class Connection:
    def __init__(self, raw):
        self.raw = raw

    @property
    def in_transaction(self):
        from psycopg.pq import TransactionStatus
        return self.raw.info.transaction_status == TransactionStatus.INTRANS

    def execute(self, sql, parameters=()):
        text, run = translate_sql(sql)
        if not run:
            return EmptyCursor()
        try:
            return Cursor(self.raw.execute(text, parameters or ()))
        except Exception as exc:
            import psycopg
            if isinstance(exc, psycopg.IntegrityError) or getattr(exc, "sqlstate", None) == "P0001":
                raise sqlite3.IntegrityError(str(exc)) from exc
            if getattr(exc, "sqlstate", None) == "42P01":
                raise sqlite3.OperationalError(f"no such table: {getattr(exc.diag, 'table_name', '')}") from exc
            raise

    def executemany(self, sql, parameters):
        text, run = translate_sql(sql)
        if not run:
            return EmptyCursor()
        try:
            return Cursor(self.raw.executemany(text, parameters))
        except Exception as exc:
            import psycopg
            if isinstance(exc, psycopg.IntegrityError) or getattr(exc, "sqlstate", None) == "P0001":
                raise sqlite3.IntegrityError(str(exc)) from exc
            raise

    def executescript(self, script):
        # Store-local schemas contain only simple CREATE statements.
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)
        return EmptyCursor()

    def commit(self):
        if self.in_transaction:
            self.raw.commit()

    def rollback(self):
        if self.in_transaction:
            self.raw.rollback()

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.rollback() if exc_type else self.commit()


class EmptyCursor:
    rowcount = 0
    def fetchone(self): return None
    def fetchall(self): return []
    def fetchmany(self, size=None): return []


def connect(path: Path, **kwargs):
    url = database_url()
    if not url:
        return sqlite3.connect(path, **kwargs)
    import psycopg
    raw = psycopg.connect(url, autocommit=True, row_factory=_row_factory, prepare_threshold=None)
    return Connection(raw)
