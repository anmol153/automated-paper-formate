CREATE TABLE google_identities (
    subject TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(user_id),
    email_at_link TEXT NOT NULL,
    linked_at TEXT NOT NULL
);
CREATE TABLE google_login_challenges (
    challenge_hash TEXT PRIMARY KEY,
    nonce_hash TEXT NOT NULL,
    browser_hash TEXT NOT NULL,
    client_id TEXT NOT NULL,
    intent TEXT NOT NULL CHECK(intent IN ('login','link')),
    user_id TEXT REFERENCES users(user_id),
    session_hash TEXT REFERENCES auth_sessions(token_hash),
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    CHECK((intent='login' AND user_id IS NULL AND session_hash IS NULL) OR
          (intent='link' AND user_id IS NOT NULL AND session_hash IS NOT NULL))
);
CREATE INDEX google_challenge_expiry ON google_login_challenges(expires_at);
CREATE TRIGGER google_identity_no_update BEFORE UPDATE ON google_identities
BEGIN
    SELECT RAISE(ABORT, 'Google account connections are immutable');
END;
CREATE TRIGGER google_identity_no_delete BEFORE DELETE ON google_identities
BEGIN
    SELECT RAISE(ABORT, 'Google account connections are immutable');
END;
