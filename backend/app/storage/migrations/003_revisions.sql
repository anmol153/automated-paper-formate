CREATE TABLE paper_revisions (
    revision_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
    number INTEGER NOT NULL CHECK(number > 0),
    parent_revision_id TEXT,
    storage_key TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes > 0),
    filename TEXT NOT NULL,
    uploaded_by TEXT REFERENCES users(user_id),
    uploaded_at TEXT NOT NULL,
    template_id TEXT NOT NULL,
    rules_json TEXT NOT NULL,
    metadata_json TEXT,
    change_summary TEXT NOT NULL DEFAULT '',
    submission_status TEXT NOT NULL,
    request_key TEXT,
    UNIQUE(submission_id, number),
    UNIQUE(submission_id, revision_id),
    UNIQUE(submission_id, request_key),
    FOREIGN KEY(submission_id, parent_revision_id)
        REFERENCES paper_revisions(submission_id, revision_id)
);
CREATE TABLE revision_checks (
    run_id TEXT PRIMARY KEY,
    revision_id TEXT NOT NULL REFERENCES paper_revisions(revision_id),
    sequence INTEGER NOT NULL CHECK(sequence > 0),
    requested_by TEXT REFERENCES users(user_id),
    created_at TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('passed','passed_with_warnings','failed','unable_to_validate')),
    assessment_json TEXT,
    error TEXT,
    UNIQUE(revision_id, sequence)
);
CREATE TABLE issue_findings (
    issue_id TEXT PRIMARY KEY REFERENCES issues(issue_id),
    run_id TEXT NOT NULL REFERENCES revision_checks(run_id),
    rule_id TEXT NOT NULL
);
CREATE TRIGGER revision_immutable_update BEFORE UPDATE ON paper_revisions
BEGIN
    SELECT RAISE(ABORT, 'Paper revisions are immutable');
END;
CREATE TRIGGER revision_immutable_delete BEFORE DELETE ON paper_revisions
BEGIN
    SELECT RAISE(ABORT, 'Paper revisions are immutable');
END;
CREATE TRIGGER check_immutable_update BEFORE UPDATE ON revision_checks
BEGIN
    SELECT RAISE(ABORT, 'Formatting reports are immutable');
END;
CREATE TRIGGER check_immutable_delete BEFORE DELETE ON revision_checks
BEGIN
    SELECT RAISE(ABORT, 'Formatting reports are immutable');
END;
