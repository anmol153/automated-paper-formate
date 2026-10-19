from app.storage.migrate import MIGRATIONS, migration_scripts, statements, _postgres_statement
from app.storage.postgres_compat import Row, _row_factory, translate_sql


def test_storage_listing_queries_use_postgres_compatible_tie_breakers(tmp_path):
    from app.storage.conference_store import ConferenceStore
    from app.storage.report_store import ReportStore
    from app.storage.template_store import TemplateStore

    class EmptyResult:
        @staticmethod
        def fetchall():
            return []

    class CapturingConnection:
        def __init__(self):
            self.queries = []

        def execute(self, query, parameters=()):
            self.queries.append(query)
            return EmptyResult()

    stores = [
        (ConferenceStore(tmp_path / "conference"), ("list_conferences", (None,))),
        (TemplateStore(tmp_path / "template"), ("list", ())),
        (ReportStore(tmp_path / "report"), ("list", ())),
    ]
    for store, (method, args) in stores:
        connection = CapturingConnection()
        store._connect = lambda connection=connection: connection
        getattr(store, method)(*args)
        assert len(connection.queries) == 1
        assert "rowid" not in connection.queries[0].lower()

    conference_store, _ = stores[0]
    connection = CapturingConnection()
    conference_store._connect = lambda: connection
    conference_store.list_conferences(query="paper")
    assert "rowid" not in connection.queries[0].lower()


def test_authentication_rate_limit_upsert_works_with_sqlite(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from app import auth
    from app.storage.user_store import UserStore

    store = UserStore(tmp_path / "users")
    monkeypatch.setattr(auth, "get_user_store", lambda: store)
    request = SimpleNamespace(client=SimpleNamespace(host="rate-limit-test"))

    auth.limit_requests(request, "login", 10, 900)
    auth.limit_requests(request, "login", 10, 900)

    bucket = auth.digest("login:rate-limit-test")
    attempts = store._connect().execute(
        "SELECT attempts FROM request_limits WHERE bucket=?", (bucket,)
    ).fetchone()[0]
    assert attempts == 2


def test_qmark_translation_preserves_question_marks_inside_literals():
    sql, run = translate_sql("SELECT '?' AS literal, value FROM example WHERE id=?")
    assert run
    assert sql == "SELECT '?' AS literal, value FROM example WHERE id=%s"


def test_postgres_rows_keep_sqlite_mapping_and_sequence_behavior():
    row = Row((("version", 8), ("checksum", "abc")))
    assert row[0] == 8
    assert row["checksum"] == "abc"
    assert dict([row]) == {8: "abc"}
    assert dict(row) == {"version": 8, "checksum": "abc"}


def test_postgres_row_factory_accepts_commands_without_result_columns():
    class CommandCursor:
        description = None

    make_row = _row_factory(CommandCursor())
    assert make_row(()) == ()


def test_sqlite_runtime_syntax_is_translated_for_postgres():
    sql, _ = translate_sql("INSERT OR IGNORE INTO items(id) VALUES (?)")
    assert sql == "INSERT INTO items(id) VALUES (%s) ON CONFLICT DO NOTHING"
    sql, _ = translate_sql("SELECT name FROM tracks ORDER BY name COLLATE NOCASE")
    assert sql.endswith("ORDER BY lower(name)")
    sql, _ = translate_sql("SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now')")
    assert "to_char(timezone('UTC', CURRENT_TIMESTAMP)" in sql


def test_all_sqlite_migration_triggers_have_postgres_equivalents():
    expected = dict((version, file_name) for version, file_name in MIGRATIONS)
    assert len(expected) == len(MIGRATIONS)
    trigger_count = 0
    for _, script, _ in migration_scripts():
        for statement in statements(script):
            if "CREATE TRIGGER" in statement.upper():
                trigger_count += 1
                translated = _postgres_statement(statement)
                assert len(translated) == 2
                assert "CREATE OR REPLACE FUNCTION" in translated[0]
                assert "EXECUTE FUNCTION" in translated[1]
    assert trigger_count > 0


def test_autoincrement_migration_is_converted():
    translated = _postgres_statement("CREATE TABLE events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT)")
    assert translated == ["CREATE TABLE events (event_id BIGSERIAL PRIMARY KEY, action TEXT)"]


def test_postgres_migration_renames_reserved_session_user_index():
    translated = _postgres_statement("CREATE INDEX session_user ON auth_sessions(user_id)")
    assert translated == ["CREATE INDEX idx_session_user ON auth_sessions(user_id)"]
