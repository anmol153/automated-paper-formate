"""Direct tests for the SQLite-backed template store.

The API tests exercise the store indirectly through HTTP; these pin the store
contract itself -- persistence across instances, ordering, and the not-found
errors that the API layer maps to 404s.
"""

from __future__ import annotations

import sqlite3
import threading

import pytest

from app.models.rules import RuleSet
from app.storage.template_store import (
    DEFAULT_STORE_DIR,
    DB_FILENAME,
    TemplateNotFound,
    TemplateStore,
    default_db_path,
)


@pytest.fixture()
def store(tmp_path):
    return TemplateStore(tmp_path / "db")


@pytest.fixture()
def rules_payload() -> dict:
    return {
        "name": "Test Venue",
        "description": "Fixture rules",
        "file_type": {"accepted_extensions": ["pdf"], "max_file_size_mb": 50},
        "pages": {
            "max_pages": 8,
            "page_size_label": "A4",
            "orientation": "portrait",
            "columns": 2,
            "margins": {"top_pt": 64, "bottom_pt": 64, "left_pt": 54, "right_pt": 54},
        },
        "sections": {"required": ["Abstract", "Introduction", "References"]},
        "anonymisation": {
            "detect_author_block": True,
            "detect_email": True,
            "detect_affiliation": True,
            "detect_acknowledgements": True,
            "detect_funding": True,
            "detect_orcid": True,
            "detect_self_citation": True,
            "detect_file_metadata": True,
        },
        "references": {"min_count": 10, "max_count": 60},
    }


def test_database_file_is_created(store):
    assert store.db_path.is_file()


def test_create_assigns_a_unique_id_and_persists(store, rules_payload):
    rules = store.create(RuleSet.model_validate(rules_payload))
    assert rules.template_id.startswith("test-venue-")
    assert store.exists(rules.template_id)


def test_get_round_trips_the_whole_rule_set(store, rules_payload):
    created = store.create(RuleSet.model_validate(rules_payload))
    loaded = store.get(created.template_id)
    assert loaded.model_dump() == created.model_dump()


def test_templates_survive_a_new_store_instance(tmp_path, rules_payload):
    """The point of the database: data outlives the process that wrote it."""
    first = TemplateStore(tmp_path / "db")
    created = first.create(RuleSet.model_validate(rules_payload))

    second = TemplateStore(tmp_path / "db")
    assert second.get(created.template_id).name == "Test Venue"


def test_list_returns_every_template(store, rules_payload):
    for name in ("Alpha Venue", "Beta Venue", "Gamma Venue"):
        payload = {**rules_payload, "name": name}
        store.create(RuleSet.model_validate(payload))
    assert {t.name for t in store.list()} == {"Alpha Venue", "Beta Venue", "Gamma Venue"}


def test_list_is_most_recently_updated_first(store, rules_payload):
    first = store.create(RuleSet.model_validate(rules_payload))
    second = store.create(RuleSet.model_validate({**rules_payload, "name": "Second Venue"}))

    listed = store.list()
    assert [t.template_id for t in listed] == [second.template_id, first.template_id]

    # Touching the older template moves it to the front.
    first.name = "Alpha Venue, revised"
    store.save(first)
    assert store.list()[0].template_id == first.template_id


def test_list_is_empty_for_a_fresh_database(store):
    assert store.list() == []


def test_save_updates_in_place_without_changing_the_id(store, rules_payload):
    created = store.create(RuleSet.model_validate(rules_payload))
    original_id = created.template_id

    created.name = "Renamed Venue"
    created.pages.max_pages = 12
    store.save(created)

    reloaded = store.get(original_id)
    assert reloaded.name == "Renamed Venue"
    assert reloaded.pages.max_pages == 12
    assert len(store.list()) == 1


def test_save_without_an_id_creates(store, rules_payload):
    """Matches create() semantics: no id means a new template, not an update."""
    created = store.create(RuleSet.model_validate(rules_payload))
    original_id = created.template_id
    created.template_id = ""
    saved = store.save(created)
    assert saved.template_id
    # create() mutates in place, so compare against the captured id.
    assert saved.template_id != original_id
    assert len(store.list()) == 2


def test_save_of_unknown_id_raises(store, rules_payload):
    rules = RuleSet.model_validate(rules_payload)
    rules.template_id = "does-not-exist"
    with pytest.raises(TemplateNotFound):
        store.save(rules)


def test_delete_removes_the_template(store, rules_payload):
    created = store.create(RuleSet.model_validate(rules_payload))
    store.delete(created.template_id)
    assert store.list() == []
    assert not store.exists(created.template_id)


def test_delete_of_unknown_id_raises(store):
    with pytest.raises(TemplateNotFound):
        store.delete("does-not-exist")


def test_get_unknown_id_raises(store):
    with pytest.raises(TemplateNotFound):
        store.get("does-not-exist")


def test_ids_are_treated_as_data_not_paths(store, rules_payload):
    """The old file store had to sanitise ids; SQL parameters make it moot."""
    created = store.create(RuleSet.model_validate(rules_payload))
    assert store.get(created.template_id) is not None
    with pytest.raises(TemplateNotFound):
        store.get("../../../etc/passwd")


def test_a_row_that_no_longer_validates_is_skipped_not_fatal(store, rules_payload):
    """One bad row must not break the list endpoint for every other template."""
    good = store.create(RuleSet.model_validate(rules_payload))
    store._connect().execute(
        "INSERT INTO templates VALUES ('broken', 'Broken', 'not json', '2020-01-01', '2020-01-01')"
    )
    assert [t.template_id for t in store.list()] == [good.template_id]


def test_schema_is_applied_to_an_existing_database(tmp_path, rules_payload):
    """Re-opening must not wipe or duplicate the schema."""
    first = TemplateStore(tmp_path / "db")
    created = first.create(RuleSet.model_validate(rules_payload))
    TemplateStore(tmp_path / "db")
    assert TemplateStore(tmp_path / "db").get(created.template_id).name == "Test Venue"


def test_concurrent_writes_from_many_threads_all_land(store, rules_payload):
    """Each thread gets its own connection; none of them should be lost."""
    errors: list[BaseException] = []
    created_ids: list[str] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        try:
            rules = store.create(
                RuleSet.model_validate({**rules_payload, "name": f"Venue {index}"})
            )
            with lock:
                created_ids.append(rules.template_id)
        except BaseException as exc:  # noqa: BLE001 - surfaced via assert below
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, f"concurrent writes failed: {errors}"
    assert len(created_ids) == 8
    assert len({t.template_id for t in store.list()}) == 8


def test_store_uses_a_real_sqlite_file(tmp_path):
    store = TemplateStore(tmp_path / "db")
    with sqlite3.connect(store.db_path) as raw:
        columns = {row[1] for row in raw.execute("PRAGMA table_info(templates)")}
    assert {"template_id", "name", "rules_json", "created_at", "updated_at"} <= columns


def test_a_directory_location_gets_a_database_inside_it(tmp_path):
    store = TemplateStore(tmp_path / "nested" / "db")
    assert store.db_path == tmp_path / "nested" / "db" / "templates.db"
    assert store.db_path.is_file()


def test_a_file_path_is_used_verbatim(tmp_path):
    store = TemplateStore(tmp_path / "custom.db")
    assert store.db_path == tmp_path / "custom.db"
    assert store.db_path.is_file()


def test_env_var_overrides_the_default_location(tmp_path, monkeypatch):
    target = tmp_path / "mounted" / "volume.db"
    monkeypatch.setenv("TEMPLATE_DB_PATH", str(target))
    assert default_db_path() == target
    assert TemplateStore().db_path == target
    assert target.is_file()


def test_blank_env_var_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("TEMPLATE_DB_PATH", "   ")
    assert default_db_path() == DEFAULT_STORE_DIR / DB_FILENAME


def test_env_var_is_read_per_construction(monkeypatch, tmp_path):
    """A store built after the variable changes follows it; one built before
    does not silently move out from under the running process."""
    monkeypatch.delenv("TEMPLATE_DB_PATH", raising=False)
    first = TemplateStore(tmp_path / "a")
    monkeypatch.setenv("TEMPLATE_DB_PATH", str(tmp_path / "b.db"))
    assert TemplateStore().db_path == tmp_path / "b.db"
    assert first.db_path == tmp_path / "a" / "templates.db"
