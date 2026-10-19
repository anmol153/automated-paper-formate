"""Conference windows, tracks and versioned declared paper metadata."""
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.models.intake import BibliographicAuthor, ConferenceSettings, PaperMetadata
from app.storage.database import MigrationRequired

STATES = {
    "setup": {"open", "closed", "archived"},
    "open": {"setup", "reviewing", "closed"},
    "reviewing": {"open", "closed"},
    "closed": {"open", "reviewing", "archived"},
    "archived": set(),
}


def available(store):
    try:
        return bool(store._connect().execute("SELECT 1 FROM schema_migrations WHERE version=6").fetchone())
    except sqlite3.OperationalError as exc:
        # Legacy stores must remain readable without being initialized or upgraded.
        if "no such table" in str(exc):
            return False
        raise


def require_intake(store):
    if not available(store):
        raise MigrationRequired("Conference settings and paper metadata require the explicit Phase 6 copy upgrade; see PHASE6.md")


def configuration(store, conference_id):
    row = store._connect().execute("SELECT * FROM conference_settings WHERE conference_id=?", (conference_id,)).fetchone() if available(store) else None
    return {"version": row["version"] if row else 0,
            "settings": ConferenceSettings.model_validate_json(row["settings_json"]) if row else ConferenceSettings()}


def window(store, conference_id, *, requested_revision=False, now=None):
    if not available(store):
        return {"allowed": True, "reason": None}
    settings = configuration(store, conference_id)["settings"]
    now = now or datetime.now(timezone.utc)
    if requested_revision:
        allowed = settings.lifecycle_status in {"open", "reviewing"} and (not settings.revisions_close_at or now < settings.revisions_close_at)
        reason = "Requested revisions are closed for this conference."
    else:
        allowed = settings.lifecycle_status == "open" and (not settings.submissions_open_at or now >= settings.submissions_open_at) and (not settings.submissions_close_at or now < settings.submissions_close_at)
        reason = "The conference is not accepting initial submissions or draft edits at this time."
    return {"allowed": bool(allowed), "reason": None if allowed else reason}


def require_window(store, conference_id, *, requested_revision=False):
    result = window(store, conference_id, requested_revision=requested_revision)
    if not result["allowed"]:
        raise HTTPException(status_code=409, detail=result["reason"])


def require_review_phase(store, conference_id):
    if not review_phase_open(store, conference_id):
        raise HTTPException(status_code=409, detail="Open the conference for submissions or reviewing before changing formal reviews or decisions")


def review_phase_open(store, conference_id):
    return not available(store) or configuration(store, conference_id)["settings"].lifecycle_status in {"open", "reviewing"}


def configure(store, conference_id, payload, actor):
    require_intake(store)
    current = configuration(store, conference_id)
    if payload.expected_version != current["version"]:
        raise HTTPException(status_code=409, detail="Conference settings changed; reload before saving")
    old, new = current["settings"].lifecycle_status, payload.settings.lifecycle_status
    if new != old and new not in STATES[old]:
        raise HTTPException(status_code=409, detail="This conference lifecycle transition is not permitted")
    if new == "archived" and store._connect().execute(
        "SELECT 1 FROM submissions WHERE conference_id=? AND status NOT IN ('accepted','rejected','withdrawn') LIMIT 1", (conference_id,),
    ).fetchone():
        raise HTTPException(status_code=409, detail="Finalize or withdraw all papers before archiving the conference")
    if new == "setup" and store._connect().execute("SELECT 1 FROM submissions WHERE conference_id=? LIMIT 1", (conference_id,)).fetchone():
        raise HTTPException(status_code=409, detail="A conference with existing papers cannot return to setup")
    if old == "archived":
        raise HTTPException(status_code=409, detail="Archived conference settings are locked")
    store._connect().execute(
        "INSERT INTO conference_settings VALUES (?,?,?,?,?) ON CONFLICT(conference_id) DO UPDATE SET "
        "version=excluded.version,settings_json=excluded.settings_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
        (conference_id, current["version"] + 1, payload.settings.model_dump_json(), actor, datetime.now(timezone.utc).isoformat()),
    )
    return configuration(store, conference_id)


def tracks(store, conference_id):
    if not available(store):
        return []
    return [{**dict(row), "active": bool(row["active"])} for row in store._connect().execute(
        "SELECT * FROM conference_tracks WHERE conference_id=? ORDER BY name COLLATE NOCASE,track_id", (conference_id,),
    )]


def validate_track(store, conference_id, track_id, *, previous=None):
    if track_id is None:
        return
    row = store._connect().execute("SELECT * FROM conference_tracks WHERE conference_id=? AND track_id=?", (conference_id, track_id)).fetchone()
    if not row or (not row["active"] and previous != track_id):
        raise HTTPException(status_code=422, detail="Choose an active track belonging to this conference")


def save_track(store, conference_id, payload, track_id=None):
    require_intake(store)
    if configuration(store, conference_id)["settings"].lifecycle_status == "archived":
        raise HTTPException(status_code=409, detail="Archived conference tracks are locked")
    existing = None
    if track_id:
        existing = store._connect().execute("SELECT * FROM conference_tracks WHERE conference_id=? AND track_id=?", (conference_id, track_id)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Track not found")
        if payload.expected_version != existing["version"]:
            raise HTTPException(status_code=409, detail="Track changed; reload before saving")
    duplicate = store._connect().execute(
        "SELECT 1 FROM conference_tracks WHERE conference_id=? AND lower(name)=lower(?) AND track_id<>?", (conference_id, payload.name, track_id or ""),
    ).fetchone()
    if duplicate:
        raise HTTPException(status_code=409, detail="This conference already has a track with that name")
    track_id = track_id or "track-" + uuid4().hex
    store._connect().execute(
        "INSERT INTO conference_tracks VALUES (?,?,?,?,?,?) ON CONFLICT(track_id) DO UPDATE SET "
        "name=excluded.name,description=excluded.description,active=excluded.active,version=excluded.version",
        (track_id, conference_id, payload.name, payload.description, int(payload.active), existing["version"] + 1 if existing else 1),
    )
    return next(t for t in tracks(store, conference_id) if t["track_id"] == track_id)


def allocate_number(store, submission_id, conference_id):
    if available(store):
        store._connect().execute(
            "INSERT INTO submission_catalog SELECT ?,?,COALESCE(MAX(paper_number),0)+1 FROM submission_catalog WHERE conference_id=?",
            (submission_id, conference_id, conference_id),
        )


def metadata(store, submission_id):
    if not available(store):
        return {"version": 0, **PaperMetadata().model_dump(), "source": None}
    row = store._connect().execute("SELECT * FROM submission_metadata_versions WHERE submission_id=? ORDER BY version DESC LIMIT 1", (submission_id,)).fetchone()
    return metadata_view(row) if row else {"version": 0, **PaperMetadata().model_dump(), "source": None}


def metadata_view(row):
    result = dict(row)
    result["authors"] = json.loads(result.pop("authors_json"))
    return result


def enrich(store, paper):
    if not available(store):
        return paper
    row = store._connect().execute("SELECT paper_number FROM submission_catalog WHERE submission_id=?", (paper.submission_id,)).fetchone()
    details = metadata(store, paper.submission_id)
    return paper.model_copy(update={"paper_number": row[0] if row else None, "title": details["title"],
        "abstract": details["abstract"], "authors": [BibliographicAuthor.model_validate(a) for a in details["authors"]], "track_id": details["track_id"], "metadata_version": details["version"]})


def missing_fields(settings, details):
    return [label for required, value, label in (
        (settings.require_title, details.title, "title"), (settings.require_abstract, details.abstract, "abstract"),
        (settings.require_authors, details.authors, "author list"), (settings.require_track, details.track_id, "track"),
    ) if required and not value]


def readiness(store, paper):
    if not available(store):
        return {"eligible": True, "reason": None}
    current = metadata(store, paper.submission_id)
    details = PaperMetadata.model_validate({key: current[key] for key in PaperMetadata.model_fields})
    missing = missing_fields(configuration(store, paper.conference_id)["settings"], details)
    return {"eligible": not missing, "reason": "Complete the required metadata: " + ", ".join(missing) if missing else None}


def append_metadata(store, paper, details, actor, revision_id, *, source="declared", expected_version=None):
    require_intake(store)
    current = metadata(store, paper.submission_id)
    if expected_version is not None and current["version"] != expected_version:
        raise HTTPException(status_code=409, detail="Paper metadata changed; reload before saving")
    validate_track(store, paper.conference_id, details.track_id, previous=current["track_id"])
    store._connect().execute(
        "INSERT INTO submission_metadata_versions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (paper.submission_id, current["version"] + 1, paper.conference_id, details.track_id, details.title, details.abstract,
         json.dumps([a.model_dump() for a in details.authors]), source, revision_id, actor, datetime.now(timezone.utc).isoformat()),
    )
    store._connect().execute("UPDATE submissions SET updated_at=? WHERE submission_id=?", (datetime.now(timezone.utc).isoformat(), paper.submission_id))
    return metadata(store, paper.submission_id)
