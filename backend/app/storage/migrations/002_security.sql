CREATE TABLE auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    csrf_hash TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    revoked_at INTEGER
);
CREATE INDEX session_user ON auth_sessions(user_id);
CREATE TABLE request_limits (
    bucket TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL,
    resets_at INTEGER NOT NULL
);
CREATE TABLE submission_security (
    submission_id TEXT PRIMARY KEY REFERENCES submissions(submission_id),
    submitter_id TEXT REFERENCES users(user_id),
    storage_key TEXT UNIQUE,
    sha256 TEXT,
    size_bytes INTEGER CHECK(size_bytes >= 0)
);
CREATE TABLE submission_collaborators (
    submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    can_edit INTEGER NOT NULL DEFAULT 0 CHECK(can_edit IN (0,1)),
    PRIMARY KEY(submission_id, user_id)
);
CREATE TABLE template_owners (
    template_id TEXT PRIMARY KEY REFERENCES templates(template_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL
);
CREATE TABLE report_owners (
    filename TEXT PRIMARY KEY REFERENCES reports(filename) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    display_filename TEXT NOT NULL,
    UNIQUE(user_id, display_filename)
);
CREATE TABLE security_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT,
    action TEXT NOT NULL,
    target_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE legacy_review_feedback (
    submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
    reviewer_id TEXT NOT NULL REFERENCES users(user_id),
    verdict TEXT NOT NULL CHECK(verdict IN ('accept','reject','review')),
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(submission_id, reviewer_id)
);
