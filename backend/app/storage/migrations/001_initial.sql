CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    email        TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name    TEXT NOT NULL,
    is_active    INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

CREATE TABLE IF NOT EXISTS conferences (
    conference_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    start_date  TEXT,
    end_date    TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conference_members (
    user_id       TEXT NOT NULL,
    conference_id TEXT NOT NULL,
    role          TEXT NOT NULL,
    joined_at     TEXT NOT NULL,
    PRIMARY KEY (user_id, conference_id)
,
FOREIGN KEY(user_id) REFERENCES users(user_id),
FOREIGN KEY(conference_id) REFERENCES conferences(conference_id)
);

CREATE INDEX IF NOT EXISTS idx_members_conference
    ON conference_members (conference_id, role);

CREATE TABLE IF NOT EXISTS templates (
    template_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    rules_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_templates_name ON templates (name);

CREATE TABLE IF NOT EXISTS template_versions (
    template_id      TEXT PRIMARY KEY,
    conference_id    TEXT NOT NULL,
    name             TEXT NOT NULL,
    rules_json       TEXT NOT NULL,
    version          TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    UNIQUE (conference_id, version)
,
FOREIGN KEY(conference_id) REFERENCES conferences(conference_id)
);

CREATE INDEX IF NOT EXISTS idx_versions_conference
    ON template_versions (conference_id, created_at DESC);

CREATE TABLE IF NOT EXISTS submissions (
    submission_id TEXT PRIMARY KEY,
    conference_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    reviewer_id TEXT,
    verdict TEXT,
    compliance_score INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
,
FOREIGN KEY(conference_id) REFERENCES conferences(conference_id),
FOREIGN KEY(reviewer_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS discussion_threads (
    thread_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    messages TEXT NOT NULL DEFAULT '[]'
,
FOREIGN KEY(submission_id) REFERENCES submissions(submission_id)
);

CREATE TABLE IF NOT EXISTS review_assignments (
    assignment_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    assigned_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    assigned_at TEXT NOT NULL
,
FOREIGN KEY(submission_id) REFERENCES submissions(submission_id),
FOREIGN KEY(reviewer_id) REFERENCES users(user_id),
FOREIGN KEY(assigned_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS issues (
    issue_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    check_result_id TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    expected TEXT,
    actual TEXT,
    advice TEXT,
    evidence TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    assignee_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by TEXT
,
FOREIGN KEY(submission_id) REFERENCES submissions(submission_id),
FOREIGN KEY(assignee_id) REFERENCES users(user_id),
FOREIGN KEY(resolved_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS issue_comments (
    comment_id TEXT PRIMARY KEY,
    issue_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
,
FOREIGN KEY(issue_id) REFERENCES issues(issue_id),
FOREIGN KEY(author_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_issues_submission ON issues (submission_id);
CREATE INDEX IF NOT EXISTS idx_issues_status ON issues (status);
CREATE INDEX IF NOT EXISTS idx_issues_assignee ON issues (assignee_id);
CREATE INDEX IF NOT EXISTS idx_comments_issue ON issue_comments (issue_id);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    related_id TEXT,
    read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    read_at TEXT,
    email TEXT
,
FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications (user_id, read, created_at);

CREATE TABLE IF NOT EXISTS reports (
    filename      TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    report_json   TEXT NOT NULL,
    paper_title   TEXT DEFAULT '',
    authors_json  TEXT DEFAULT '[]',
    format        TEXT DEFAULT '',
    score         INTEGER DEFAULT 0,
    verdict       TEXT DEFAULT '',
    template_name TEXT DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_updated ON reports (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_score ON reports (score DESC);
