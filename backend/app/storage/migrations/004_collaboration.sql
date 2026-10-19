CREATE TABLE conference_workflow (
    conference_id TEXT PRIMARY KEY REFERENCES conferences(conference_id),
    formatting_gate TEXT NOT NULL CHECK(formatting_gate IN ('allow_issues','block_errors'))
);
CREATE TABLE submission_workflow (
    submission_id TEXT PRIMARY KEY REFERENCES submissions(submission_id),
    requested_revision_id TEXT REFERENCES paper_revisions(revision_id),
    decision_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(submission_id, requested_revision_id) REFERENCES paper_revisions(submission_id, revision_id)
);
CREATE TABLE paper_threads (
    thread_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
    revision_id TEXT,
    page_number INTEGER CHECK(page_number BETWEEN 1 AND 10000),
    visibility TEXT NOT NULL CHECK(visibility IN ('participants','chairs')),
    resolved INTEGER NOT NULL DEFAULT 0 CHECK(resolved IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(submission_id, revision_id) REFERENCES paper_revisions(submission_id, revision_id),
    CHECK(page_number IS NULL OR revision_id IS NOT NULL)
);
CREATE INDEX threads_paper ON paper_threads(submission_id, created_at);
CREATE TABLE paper_comments (
    comment_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES paper_threads(thread_id),
    parent_comment_id TEXT,
    author_id TEXT NOT NULL REFERENCES users(user_id),
    author_role TEXT NOT NULL,
    body TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    edited_at TEXT,
    deleted_at TEXT,
    UNIQUE(thread_id, comment_id),
    FOREIGN KEY(thread_id, parent_comment_id) REFERENCES paper_comments(thread_id, comment_id)
);
CREATE INDEX comments_thread ON paper_comments(thread_id, created_at);
CREATE TABLE paper_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
    actor_id TEXT REFERENCES users(user_id),
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    visibility TEXT NOT NULL CHECK(visibility IN ('participants','chairs')),
    revision_id TEXT REFERENCES paper_revisions(revision_id),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(submission_id, revision_id) REFERENCES paper_revisions(submission_id, revision_id)
);
CREATE INDEX events_paper ON paper_events(submission_id, event_id);
INSERT INTO paper_events(submission_id,actor_id,actor_role,action,visibility,revision_id,details_json,created_at)
SELECT s.submission_id,NULL,'legacy',e.action,
       CASE WHEN e.action='reviewer.verdict_recorded' THEN 'chairs' ELSE 'participants' END,
       NULL,'{"legacy":true}',e.created_at
FROM security_events e
LEFT JOIN issues i ON i.issue_id=e.target_id
JOIN submissions s ON s.submission_id=COALESCE(i.submission_id,e.target_id)
ORDER BY e.event_id;
CREATE TRIGGER event_no_update BEFORE UPDATE ON paper_events
BEGIN
    SELECT RAISE(ABORT, 'Activity events are immutable');
END;
CREATE TRIGGER event_no_delete BEFORE DELETE ON paper_events
BEGIN
    SELECT RAISE(ABORT, 'Activity events are immutable');
END;
