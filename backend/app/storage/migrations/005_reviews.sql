CREATE TABLE review_forms (
    form_id TEXT PRIMARY KEY,
    conference_id TEXT NOT NULL REFERENCES conferences(conference_id),
    number INTEGER NOT NULL,
    form_json TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES users(user_id),
    created_at TEXT NOT NULL,
    UNIQUE(conference_id, number),
    UNIQUE(conference_id, form_id)
);
CREATE TABLE conference_review_policy (
    conference_id TEXT PRIMARY KEY REFERENCES conferences(conference_id),
    form_id TEXT NOT NULL,
    policy_json TEXT NOT NULL,
    version INTEGER NOT NULL,
    FOREIGN KEY(conference_id, form_id) REFERENCES review_forms(conference_id, form_id)
);
CREATE TABLE formal_reviews (
    review_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
    assignment_id TEXT NOT NULL REFERENCES review_assignments(assignment_id),
    reviewer_id TEXT NOT NULL REFERENCES users(user_id),
    revision_id TEXT NOT NULL,
    form_id TEXT NOT NULL REFERENCES review_forms(form_id),
    version INTEGER NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('draft','submitted')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(assignment_id, revision_id),
    UNIQUE(submission_id, review_id),
    FOREIGN KEY(submission_id, revision_id) REFERENCES paper_revisions(submission_id, revision_id)
);
CREATE TABLE review_versions (
    review_id TEXT NOT NULL REFERENCES formal_reviews(review_id),
    version INTEGER NOT NULL,
    recommendation TEXT,
    answers_json TEXT NOT NULL,
    confidential_comments TEXT NOT NULL,
    submitted INTEGER NOT NULL CHECK(submitted IN (0,1)),
    created_at TEXT NOT NULL,
    PRIMARY KEY(review_id, version)
);
CREATE TABLE review_releases (
    release_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    review_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    identities_visible INTEGER NOT NULL CHECK(identities_visible IN (0,1)),
    publish_recommendation INTEGER NOT NULL CHECK(publish_recommendation IN (0,1)),
    created_by TEXT NOT NULL REFERENCES users(user_id),
    created_at TEXT NOT NULL,
    UNIQUE(review_id, version),
    FOREIGN KEY(submission_id, review_id) REFERENCES formal_reviews(submission_id, review_id),
    FOREIGN KEY(review_id, version) REFERENCES review_versions(review_id, version)
);
CREATE TABLE review_conflicts (
    conflict_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
    reviewer_id TEXT NOT NULL REFERENCES users(user_id),
    reason TEXT NOT NULL,
    declared_by TEXT NOT NULL REFERENCES users(user_id),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by TEXT REFERENCES users(user_id),
    resolution_reason TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX one_active_conflict ON review_conflicts(submission_id,reviewer_id) WHERE resolved_at IS NULL;
CREATE INDEX reviews_paper ON formal_reviews(submission_id, revision_id);
CREATE TABLE review_private_notifications (
    notification_id TEXT PRIMARY KEY REFERENCES notifications(notification_id)
);
CREATE TABLE paper_decisions (
    decision_id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL UNIQUE REFERENCES submissions(submission_id),
    revision_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('accepted','rejected')),
    reason TEXT NOT NULL,
    decided_by TEXT NOT NULL REFERENCES users(user_id),
    decided_at TEXT NOT NULL,
    minimum_reviews INTEGER NOT NULL,
    FOREIGN KEY(submission_id, revision_id) REFERENCES paper_revisions(submission_id, revision_id)
);
CREATE TABLE decision_reviews (
    decision_id TEXT NOT NULL REFERENCES paper_decisions(decision_id),
    review_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    PRIMARY KEY(decision_id,review_id),
    FOREIGN KEY(review_id,version) REFERENCES review_versions(review_id,version)
);
CREATE TRIGGER decision_no_update BEFORE UPDATE ON paper_decisions
BEGIN
    SELECT RAISE(ABORT, 'Conference decisions are immutable');
END;
CREATE TRIGGER decision_no_delete BEFORE DELETE ON paper_decisions
BEGIN
    SELECT RAISE(ABORT, 'Conference decisions are immutable');
END;
CREATE TRIGGER decision_review_no_update BEFORE UPDATE ON decision_reviews
BEGIN
    SELECT RAISE(ABORT, 'Decision review snapshots are immutable');
END;
CREATE TRIGGER decision_review_no_delete BEFORE DELETE ON decision_reviews
BEGIN
    SELECT RAISE(ABORT, 'Decision review snapshots are immutable');
END;
CREATE TRIGGER review_form_no_update BEFORE UPDATE ON review_forms
BEGIN
    SELECT RAISE(ABORT, 'Review forms are immutable');
END;
CREATE TRIGGER review_form_no_delete BEFORE DELETE ON review_forms
BEGIN
    SELECT RAISE(ABORT, 'Review forms are immutable');
END;
CREATE TRIGGER review_identity_no_update BEFORE UPDATE OF submission_id,assignment_id,reviewer_id,revision_id,form_id ON formal_reviews
BEGIN
    SELECT RAISE(ABORT, 'Review identity is immutable');
END;
CREATE TRIGGER review_version_no_update BEFORE UPDATE ON review_versions
BEGIN
    SELECT RAISE(ABORT, 'Review versions are immutable');
END;
CREATE TRIGGER review_version_no_delete BEFORE DELETE ON review_versions
BEGIN
    SELECT RAISE(ABORT, 'Review versions are immutable');
END;
CREATE TRIGGER review_release_no_update BEFORE UPDATE ON review_releases
BEGIN
    SELECT RAISE(ABORT, 'Review releases are immutable');
END;
CREATE TRIGGER review_release_no_delete BEFORE DELETE ON review_releases
BEGIN
    SELECT RAISE(ABORT, 'Review releases are immutable');
END;
