from app.storage.migrate import MIGRATIONS, migration_scripts, statements, _postgres_statement
from app.storage.postgres_compat import Row, translate_sql


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
