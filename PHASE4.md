# Phase 4: formal reviews, conflicts, release and decisions

This phase adds formal academic review records to the existing submission workspace.
Formatting assessments, ordinary conversations, reviewer recommendations, and conference
decisions remain separate records. The existing checker and immutable file/report
pipeline are reused without replacing their algorithms.

Implementation used schema version 5 in isolated test databases. The subsequent
approved Google-auth copy upgrade activated migrations 5–7, including formal reviews.
The current local backend selects `platform-v7.db`; the source and verified backups
remain intact. See `GOOGLE_AUTH.md` for the activation result. No deployment was
performed.

## Configurable forms and policy

Chairs configure a versioned review form containing up to 20 criteria. Each criterion
has a stable ID, label, score/text type, required flag, and author/chair visibility.
Scores have an explicit minimum and maximum; the server rejects booleans, nonnumeric
scores, nonfinite values, out-of-range scores, unknown criteria, and missing required
answers on submission. Text fields and the aggregate review body have size bounds.
Recommendation labels are configurable and validated against the form snapshot.

The default form provides overall score, originality, technical quality, presentation,
relevance, strengths, weaknesses, and required changes. It includes the usual accept,
reject, borderline and major-revision recommendations. A major-revision recommendation
does not itself change the submission's lifecycle: chairs still decide whether to
request changes.

Conference policy controls:

- A timezone-aware review deadline, stored in UTC.
- Whether submitted reviews may be edited before the deadline.
- Whether reviewers may see others' submitted reviews after submitting their own
  review of the same revision.
- Whether reviewer identities are visible in future author releases.
- Whether recommendations are included in author releases.
- The minimum number of eligible current-revision reviews for an acceptance/rejection
  decision during formal review.

Policy writes require an expected configuration version. Form changes append an
immutable form version; policy-only changes retain the existing form. Reviews already
started keep their original form even when the conference publishes a newer one.
A new review started with an obsolete form ID returns 409 rather than silently
changing its questions.

For compatibility, the default minimum review count is zero; chairs should configure
their required count before reviewing. Submitted papers may still receive a reasoned
desk rejection without formal reviews. Numerical scores are not averaged across forms
or used to generate an automatic acceptance decision.

An initial valid assignment publishes the default form if the conference has no
configuration. Existing migrated assignments do not cause writes on GET: a chair must
configure their form before those reviewers can start. Legacy papers without an
identified immutable revision still require the earlier reconciliation workflow.

## Draft, submission and immutable review history

Each formal review is bound to one assignment, one immutable paper revision, and one
immutable form. The server derives reviewer identity from the authenticated assignment.
Review bodies never accept a client-supplied reviewer ID.

Every save appends a `review_versions` row. The review record points to its latest
version and has a draft/submitted state. Saves require an expected version, so racing
saves have one winner. Partial drafts are allowed, but supplied answers still require
valid types/ranges. Formal submission requires all required answers and a configured
recommendation. Saving a new draft after submission reopens that review and removes
it from the current submitted-review count until it is submitted again.

Draft content is private to its reviewer. Chairs can track that a draft exists but
cannot read its body. After submission, an eligible chair can see all fields including
confidential chair comments. Other reviewers cannot see private chair fields. Authors
cannot see any version until an eligible chair explicitly releases it.

The backend only accepts writes while the paper is under review, for its current
revision, with an active eligible assignment and no declared or authorship conflict.
The deadline and submitted-edit policy are checked inside the same transaction.
Saving is limited to 60 attempts per user per hour; stale/failed saves preserve earlier
versions. The existing cookie-session and CSRF protections apply.

When a paper is revised, its earlier reviews remain bound to their original revision.
They do not count toward a configured requirement for the new revision. Reviewers
write a new review for that revision. A reviewer explicitly reassigned after revocation
can read their own earlier versions again, but an old revoked submission does not
unlock peer-review visibility for the new assignment.

## Explicit review release and privacy

Release appends a record referencing the exact submitted review version. It includes
only active, eligible submitted reviews of the expected current paper revision.
Repeating release is idempotent for already released versions. A stale revision ID
returns 409. Withdrawn papers cannot publish new releases.

Author projections omit confidential comments and chair-only criterion answers and
labels. Release records snapshot reviewer-identity and recommendation visibility.
Changing conference policy later does not unmask an earlier release. Later reviewer
edits do not change an already released version; chairs explicitly release a newer
submitted version if appropriate. The history endpoint returns only the versions the
caller is allowed to see. Released reviews from an inactive assignment remain visible
as historical records and do not count toward current decisions.

This remains the existing single-blind paper workflow. Authors and document metadata
are not automatically anonymized. The setting for reviewer identity applies to formal
author releases; this phase does not claim double-blind review or safe PDF redaction.

## Conflicts and chair recusal

Self/coauthor review assignments remain prohibited. Reviewers may declare an assignment
conflict, or eligible chairs may record one for an active conference account. A conflict
revokes that person's active assignments on the paper immediately. Reviewer file,
discussion, review and report access through that assignment is removed. Conflict
reasons and their activity events are chair-only.

Conflicts retain the declarer, timestamp, resolution reason, resolver, and version.
A reviewer can withdraw their own declaration from the reviewer workspace, or an
eligible chair can record a resolution. Resolving never restores an assignment
automatically: a chair must explicitly reassign the reviewer. A reviewer cannot clear
a chair-recorded declaration through the self-withdraw endpoint.

Chairs who authored/coauthored the paper or have an active conflict cannot manage its
formal reviews, see chair-only discussion/activity, assign/revoke reviewers, release
reviews, or make chair lifecycle decisions on it. Their author-visible projections
also hide reviewer identities in submission, workflow, issue and discussion responses.
They retain the ordinary author/participant access that their paper membership permits.
Another unconflicted chair must handle the paper. Conference-wide configuration and
membership administration retain their existing conference-role permissions.

## Decisions, progress and notifications

The existing transition service is the only final-decision path. It enforces the
configured number of distinct eligible submitted reviewers of the current revision
when accepting/rejecting from under review, in addition to Phase 3 state, reason and
stale-revision guards. Revoked assignments, conflicted reviewers, inactive accounts,
drafts, old revisions, and legacy feedback do not satisfy that requirement.

New final decisions append an immutable `paper_decisions` record with the paper
revision, decision, reason, chair, timestamp and configured minimum. `decision_reviews`
snapshots the exact submitted review versions considered. Authors see the decision
and reason without receiving unreleased review details. Historical decisions made
before this schema retain their existing status/reason/history; no formal decision or
review snapshot is invented for them.

The reviewer workspace lists the authenticated user's eligible assignments, current
review state, deadlines, and their own active conflict declarations. The conference
chair dashboard lists only papers the chair can handle, including current submitted
and missing review counts. Each submission's Reviews tab provides the configured
form, own review, permitted review history, chair progress/release controls, and
conflict management.

Formal submission persists generic chair notifications atomically with the review.
These notifications carry an additional private scope and disappear if the recipient
is no longer an eligible chair for that paper. Release sends generic participant
notifications; confidential fields and conflict reasons are not sent. Email delivery,
scheduled deadline reminders, real-time push and notification preferences remain
outside this phase.

## Main implementation files

| File | Responsibility |
| --- | --- |
| `backend/app/models/review.py` | Strict configurable form, criterion, policy, save/release and conflict contracts |
| `backend/app/services/reviews.py` | Assignment/conflict authorization, versioned saves, safe projections, progress, decision guards and snapshots |
| `backend/app/api/review_routes.py` | Configuration, review/history, release, conflict, reviewer workspace and chair dashboard APIs |
| `backend/app/storage/migrations/005_reviews.sql` | Forms/policy, formal reviews/versions/releases, conflicts, private notification scopes and immutable decisions |
| `backend/app/security/permissions.py` | Paper-specific chair recusal and identity projections |
| `backend/app/services/workflow.py` | Formal decision gate integrated with the existing lifecycle |
| `frontend/src/components/ReviewConfiguration.jsx` | Structured criterion editor, visibility settings, deadlines and thresholds |
| `frontend/src/components/FormalReviews.jsx` | Draft/submission form, permitted review/history views, release and conflict controls |
| `frontend/src/components/ConferenceReviewProgress.jsx` | Chair progress dashboard |
| `frontend/src/pages/ReviewerWorkspace.jsx` | Reviewer assignments and conflict declarations |
| `backend/tests/test_phase4_reviews.py` | Formal-review confidentiality, lifecycle, revisions, versions, races, conflict and decision regressions |

All API paths below use `/api/v1`:

| Method | Path |
| --- | --- |
| GET, PUT | `/conferences/{conf_id}/review-configuration` |
| GET | `/conferences/{conf_id}/review-progress` |
| GET | `/submissions/{id}/reviews` |
| PUT | `/submissions/{id}/reviews/mine` |
| GET | `/submissions/{id}/reviews/{review_id}/history` |
| POST | `/submissions/{id}/reviews/release` |
| GET, POST | `/submissions/{id}/conflicts` |
| PATCH | `/submissions/{id}/conflicts/{conflict_id}` |
| GET | `/reviewer/workspace` |
| POST | `/reviewer/assignments/{assignment_id}/conflict` |
| POST | `/reviewer/conflicts/{conflict_id}/withdraw` |

The browser adds `/reviewer` navigation and a Reviews tab to the existing submission
page. All downloads, formatting report components and earlier conference routes stay
in place. The legacy verdict endpoint is retained for papers without formal reviews;
once formal records exist, it cannot overwrite that paper's feedback through the
compatibility path. It never becomes a formal review or counts toward a decision gate.
Formatting compliance scores remain separate from academic review scores.

## Database activation

The approved Phase 3 copy upgrade initially selected `platform-v4.db` with versions
1–4. The later approved combined activation now selects `platform-v7.db`. See
`GOOGLE_AUTH.md` for the latest activation record. The source `platform-v3.db` and
verified configuration/data backups remain intact under
`backend/data/backups/phase3-20261017T064910Z/`. All 134 original records were compared;
18 original data files were unchanged. The session secret and other configuration
values were preserved.

Phase 4 is now activated through the combined schema-7 copy upgrade. Its original read-only preflight found
schema versions 1–4 and zero legacy submissions without revisions. It created no
target. Phase 6 now adds migration 6; the current upgrader applies all registered
pending migrations. Google authentication now adds schema 7. Use the combined
schema-5-through-7 activation procedure and `platform-v7.db` target in
`GOOGLE_AUTH.md`, after explicit approval. Do not use a target named `platform-v5.db`
expecting the current CLI to stop at version 5.

Verify original table values, schema checksums, integrity and foreign keys, then point
only `WORKFLOW_DB_PATH` in `backend/.env` to the new absolute target and restart. Keep
the existing session secret and prior databases. The upgrader consolidates and closes
its staged SQLite database before publishing the new file. Rollback after accepting
new writes requires reconciliation; changing the path alone would hide those writes.
No production deployment or in-place schema upgrade is included.

## Verification and remaining scope

Tests cover draft privacy, chair-only comments/criteria, explicit release, immutable
released versions, identity-policy snapshots, score/field validation, deadlines/edit
locks, pinned forms, stale review saves, revision-bound review counts and decisions,
assignment conflicts/revocation/reassignment, author-chair recusal, private notification
scopes, transactional failure rollback, concurrent saves, throttling and dashboard
permissions. The UI harness exercises separate chair, author and reviewer accounts,
the configured form, reviewer workspace, unreleased invisibility and released public
content alongside all earlier checker/collaboration flows.

Final verification: 254 backend tests passed and 8 skipped, including 27 Phase 4
cases. The frontend production build, full UI harness and whitespace checks passed.
Existing thread/file-processing limits remain as documented in earlier phases. Review lists
and history currently return all authorized records; pagination and operational
retention/deletion tooling remain future work. Automatic institution/coauthor-network
conflict detection, bid-based assignment, review calibration, appeals, revised final
decisions, camera-ready processing and double-blind document handling are not included.
