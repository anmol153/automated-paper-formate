CREATE TABLE conference_settings (
    conference_id TEXT PRIMARY KEY REFERENCES conferences(conference_id),
    version INTEGER NOT NULL CHECK(version > 0),
    settings_json TEXT NOT NULL,
    updated_by TEXT REFERENCES users(user_id),
    updated_at TEXT NOT NULL
);
CREATE TABLE conference_tracks (
    track_id TEXT PRIMARY KEY,
    conference_id TEXT NOT NULL REFERENCES conferences(conference_id),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    version INTEGER NOT NULL CHECK(version > 0),
    UNIQUE(conference_id, track_id)
);
CREATE UNIQUE INDEX track_names ON conference_tracks(conference_id, lower(name));
CREATE UNIQUE INDEX submission_conference_pair ON submissions(submission_id, conference_id);
CREATE TABLE submission_catalog (
    submission_id TEXT PRIMARY KEY,
    conference_id TEXT NOT NULL,
    paper_number INTEGER NOT NULL CHECK(paper_number > 0),
    UNIQUE(conference_id, paper_number),
    FOREIGN KEY(submission_id, conference_id) REFERENCES submissions(submission_id, conference_id)
);
INSERT INTO submission_catalog
SELECT submission_id, conference_id,
       row_number() OVER (PARTITION BY conference_id ORDER BY created_at, submission_id)
FROM submissions;
CREATE TABLE submission_metadata_versions (
    submission_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK(version > 0),
    conference_id TEXT NOT NULL,
    track_id TEXT,
    title TEXT NOT NULL,
    abstract TEXT NOT NULL,
    authors_json TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('declared','extracted','legacy')),
    revision_id TEXT,
    updated_by TEXT REFERENCES users(user_id),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(submission_id, version),
    FOREIGN KEY(submission_id, conference_id) REFERENCES submissions(submission_id, conference_id),
    FOREIGN KEY(conference_id, track_id) REFERENCES conference_tracks(conference_id, track_id),
    FOREIGN KEY(submission_id, revision_id) REFERENCES paper_revisions(submission_id, revision_id)
);
INSERT INTO submission_metadata_versions
SELECT submission_id, 1, conference_id, NULL, '', '', '[]', 'legacy', NULL, NULL, updated_at
FROM submissions;
CREATE TRIGGER catalog_no_update BEFORE UPDATE ON submission_catalog
BEGIN
    SELECT RAISE(ABORT, 'Paper numbers are immutable');
END;
CREATE TRIGGER catalog_no_delete BEFORE DELETE ON submission_catalog
BEGIN
    SELECT RAISE(ABORT, 'Paper numbers are immutable');
END;
CREATE TRIGGER metadata_no_update BEFORE UPDATE ON submission_metadata_versions
BEGIN
    SELECT RAISE(ABORT, 'Metadata history is immutable');
END;
CREATE TRIGGER metadata_no_delete BEFORE DELETE ON submission_metadata_versions
BEGIN
    SELECT RAISE(ABORT, 'Metadata history is immutable');
END;
