CREATE TABLE conference_access_requests (
    request_id TEXT PRIMARY KEY,
    conference_id TEXT NOT NULL REFERENCES conferences(conference_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    requested_role TEXT NOT NULL CHECK(requested_role IN ('author','reviewer')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','declined')),
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT REFERENCES users(user_id)
);
CREATE UNIQUE INDEX conference_access_pending_user
    ON conference_access_requests(conference_id,user_id) WHERE status='pending';
CREATE INDEX conference_access_queue
    ON conference_access_requests(conference_id,status,created_at DESC);
