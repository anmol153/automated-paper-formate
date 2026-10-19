CREATE TABLE conference_invitations (
    invitation_id TEXT PRIMARY KEY,
    conference_id TEXT NOT NULL REFERENCES conferences(conference_id),
    recipient_email TEXT NOT NULL,
    recipient_user_id TEXT REFERENCES users(user_id),
    role TEXT NOT NULL CHECK(role IN ('author', 'reviewer')),
    token_hash TEXT NOT NULL UNIQUE,
    issued_by TEXT NOT NULL REFERENCES users(user_id),
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL CHECK(expires_at > created_at),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','revoked','expired')),
    accepted_by TEXT REFERENCES users(user_id),
    accepted_at INTEGER,
    revoked_by TEXT REFERENCES users(user_id),
    revoked_at INTEGER,
    CHECK((status IN ('pending','expired') AND accepted_by IS NULL AND accepted_at IS NULL AND revoked_by IS NULL AND revoked_at IS NULL) OR
          (status='accepted' AND accepted_by IS NOT NULL AND accepted_at IS NOT NULL AND revoked_by IS NULL AND revoked_at IS NULL) OR
          (status='revoked' AND accepted_by IS NULL AND accepted_at IS NULL AND revoked_by IS NOT NULL AND revoked_at IS NOT NULL))
);
CREATE UNIQUE INDEX invitation_pending_recipient ON conference_invitations(conference_id, recipient_email) WHERE status='pending';
CREATE INDEX invitation_conference_history ON conference_invitations(conference_id, created_at DESC, invitation_id DESC);
CREATE TRIGGER invitation_snapshot_immutable BEFORE UPDATE OF invitation_id,conference_id,recipient_email,recipient_user_id,role,token_hash,issued_by,created_at,expires_at ON conference_invitations
BEGIN
    SELECT RAISE(ABORT, 'Invitation terms are immutable');
END;
CREATE TRIGGER invitation_terminal_immutable BEFORE UPDATE ON conference_invitations WHEN OLD.status != 'pending'
BEGIN
    SELECT RAISE(ABORT, 'Closed invitations are immutable');
END;
CREATE TRIGGER invitation_no_delete BEFORE DELETE ON conference_invitations
BEGIN
    SELECT RAISE(ABORT, 'Invitation history is retained');
END;
