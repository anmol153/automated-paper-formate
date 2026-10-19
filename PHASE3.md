# Phase 3: submission lifecycle and collaboration

This phase builds on the immutable revisions and formatting engine from Phase 2.
It adds explicit submission transitions, configurable formatting gates, collaborator
grants, reviewer revocation, threaded conversation, and a protected activity timeline.
Formal academic review forms, configurable scoring, and review release rules remain
Phase 4 work.

## Submission states and formatting gates

Formatting status remains separate from the submission lifecycle. A failed formatting
check does not mean that a conference has rejected the paper.

| Current state | Permitted next states | Authority/requirements |
| --- | --- | --- |
| Draft | Submitted, Withdrawn | Submit: author/editor/chair and formatting gate; withdraw: submitting author/chair |
| Submitted | Under Review, Rejected, Withdrawn | Review: chair, eligible formatting and active assignment; desk rejection: chair with reason; withdrawal: submitting author/chair |
| Under Review | Changes Requested, Accepted, Rejected, Withdrawn | Review actions: chair with reason; withdrawal: submitting author/chair |
| Changes Requested | Submitted, Withdrawn | Resubmit: author/editor/chair, a newer uploaded revision, and formatting gate; withdrawal: submitting author/chair |
| Accepted, Rejected, Withdrawn | None | Terminal; files/history remain accessible under the existing paper permissions |

The new transition API requires the expected current status and current revision ID.
They are checked again inside the write transaction. Stale actions return 409. The
compatibility PATCH route still accepts its original status payload, but now enforces
the same state machine and chair authorization; actions requiring a reason must use
the transition API. Direct arbitrary status changes are no longer an API feature.

Conference chairs select one of two policies:

- `allow_issues`: a completed assessment may proceed with formatting findings.
- `block_errors`: blocking findings must be corrected; warnings may proceed.

An unavailable or missing assessment cannot proceed under either policy. Existing
conferences default to `allow_issues` to preserve the earlier submission behavior;
the conference paper screen exposes the policy and chair configuration controls.
The policy is evaluated on initial submission, explicit submission/resubmission,
reviewer assignment, and entry into review. Changing a policy does not silently
change an already submitted paper's lifecycle state or final decision.

First uploads support multipart `submit_for_review=false` to create a draft. When
automatic submission is requested but its formatting gate fails, the upload and
report are retained as a draft. Uploads during review require the chair to request
changes first. Uploading the correction does not silently resubmit it: the author
must explicitly submit the new revision. Revision numbers and reports remain immutable.

Chairs can assign/revoke/reassign reviewers. Revocation retains the assignment record
with status `revoked` and removes paper access immediately. Self/coauthor assignments
and inactive accounts are rejected. Existing formal-review limitations still apply:
the legacy recommendation endpoint is separate from acceptance status; this phase
does not enforce review-count thresholds, configurable review forms, or release dates.

## Coauthors and permissions

Only the submitting author or a conference chair can grant/change/remove coauthor
access. Editing collaborators cannot grant access to someone else or withdraw the
paper. A coauthor needs an active existing account and conference membership; no
email invitation or account discovery is introduced.

Read/discuss grants permit files, reports, activity, and participant conversation.
Editing grants additionally permit revision uploads, rechecks, submission/resubmission,
and issue/thread resolution according to the current lifecycle. All past reviewer
assignments block adding that person as a coauthor of the same paper. Finalized papers
cannot change author grants through these endpoints. Removing the grant or membership
removes paper access and hides related notifications on subsequent requests.

These are paper-level collaboration grants, not a verified bibliographic author list.
The extracted author metadata remains parser evidence. The existing conference role
model still has one membership role per conference; track chairs and richer membership
roles remain future work.

## Conversation and document references

Normalized `paper_threads` and `paper_comments` support general discussion, replies
to specific comments, author edits, soft deletion, and explicit resolve/reopen actions.
Edits/deletes require the expected comment version. A chair can moderate by deleting
another person's comment but cannot rewrite it under that person's identity. Editing
and replying never accept a client-supplied author ID. Deleted bodies remain retained
in storage and are omitted from all conversation API projections.

A thread can reference an explicit immutable revision and optional page number.
Known exact page counts bound the page input; estimated/unknown counts do not claim
an exact bound. Anchors are never moved to newer revisions. The interface labels
earlier-version comments and links to the original revision. General discussion has
no implied revision anchor. PDF text selection, bounding boxes, automatic reanchoring,
and an embedded annotation viewer remain later work.

Chairs can create confidential threads. Nonchairs cannot list, infer content from,
reply to, edit, resolve, or access these threads or their activity events. Comment
author roles are captured when posted. Reviewer IDs remain pseudonymized as `Reviewer`
for other nonchair viewers even after assignment revocation. The original reviewer
can still recognize their own identity while authorized. This is the existing
single-blind foundation; the platform does not claim double-blind file/metadata privacy.

The existing `/discussion` compatibility API and stored messages remain intact.
The new interface renders their contents in an earlier-conversation section; new
threaded comments use `/conversation`. Old messages do not gain invented edit/revision
history or automatic anchors.

## Activity and notifications

`SubmissionStore.audit` continues writing security events and also records append-only
paper events after schema version 4 is activated. Events cover uploads, checks,
status transitions, comments, resolution, issue updates, collaborators and reviewer
assignment/revocation. Transition events retain the old/new states and reason.
Private chair events and legacy reviewer recommendations are chair-only. Reviewer
actor roles are snapshotted and projected with the same identity policy as comments.
The activity API paginates after applying visibility rules.

The migration projects earlier security events into the timeline while preserving
their timestamps and originals. Historical actors appear as `Historical participant`:
the system does not guess whether an old identity was a confidential reviewer. Old
events with no recorded revision keep a null anchor. No old comment bodies are copied
into activity payloads.

Participant comments, status changes, collaborator grants, new papers/revisions, and
check completion/failure persist generic in-app notifications in the same transaction
as the underlying action. Current paper permissions govern read/list/count access.
Issue notifications are normalized to their paper for navigation. Confidential chair
threads do not produce notifications in this phase, avoiding stale-recipient leaks.
Email, mentions, live push, preferences, and durable delivery/retry jobs are deferred.

## Main files and APIs

| File | Responsibility |
| --- | --- |
| `backend/app/services/workflow.py` | State graph, formatting eligibility, actor-role snapshots, transition authorization |
| `backend/app/api/collaboration_routes.py` | Policy, lifecycle, grants, conversation, activity and reviewer revocation APIs |
| `backend/app/storage/migrations/004_collaboration.sql` | Conference/submission workflow records, normalized discussion, immutable activity and historical projection |
| `backend/app/storage/submission_store.py` | Security and paper-event auditing |
| `backend/app/api/submission_routes.py` | Initial draft/gate behavior, guarded compatibility transitions and assignment integration |
| `backend/app/api/revision_routes.py` | Lifecycle upload locks, revision activity and participant notifications |
| `frontend/src/components/SubmissionWorkflow.jsx` | Pending actions, reviewer assignment/revocation, coauthor controls |
| `frontend/src/components/PaperConversation.jsx` | Replies, edits, deletion, private threads and immutable revision/page links |
| `frontend/src/components/PaperActivity.jsx` | Paginated protected timeline |
| `frontend/src/components/ConferenceWorkflowPolicy.jsx` | Conference formatting policy display/configuration |
| `backend/tests/test_phase3_collaboration.py` | Lifecycle, race, authorization, confidentiality, migration, rollback and CSRF regressions |

All paths below use `/api/v1`:

| Method | Path |
| --- | --- |
| GET, PUT | `/conferences/{conf_id}/workflow` |
| GET | `/submissions/{id}/workflow` |
| POST | `/submissions/{id}/transitions` |
| GET, PUT | `/submissions/{id}/collaborators` |
| DELETE | `/submissions/{id}/collaborators/{user_id}` |
| DELETE | `/submissions/{id}/assignments/{assignment_id}` |
| GET, POST | `/submissions/{id}/conversation` |
| PATCH | `/submissions/{id}/conversation/{thread_id}` |
| POST | `/submissions/{id}/conversation/{thread_id}/comments` |
| PATCH, DELETE | `/submissions/{id}/conversation/{thread_id}/comments/{comment_id}` |
| GET | `/submissions/{id}/activity?limit=50&before={event_id}` |

The existing React/Vite/Tailwind workspace now has Overview, Conversation, Formatting
Checks, Files and Revisions, Issues, and Activity navigation. Existing file/report
components remain in use. API authorization, transaction boundaries, and CSRF protections
are enforced independently of the visible buttons.

## Phase 2 activation and migration reliability fix

The approved Phase 2 activation is complete. `backend/.env` points to
`backend/data/platform-v3.db`, containing schema versions 1–3. The original
`platform.db` and verified source/configuration backups are retained in
`backend/data/backups/phase2-20261017T063238Z/`. All 134 original records across the
source tables were compared, and 15 original data files were unchanged. The persistent
session secret and other configuration values were preserved.

The initial activation attempt exposed a WAL publishing bug in the versioned copy
upgrade: a staged main database could be published before its WAL was consolidated.
That incomplete artifact was preserved in the activation backup. The upgrader now
closes connections, converts the staged database to DELETE journal mode, verifies it
after reopening, and fsyncs the main file before publishing. A regression test reads
the published file with SQLite `immutable=1`, proving it contains the complete upgrade
without relying on sidecars. Source databases remain untouched by the copy upgrade.

## Phase 3 database activation

Phase 3 implementation and verification used isolated schema-4 databases. Existing
nonempty databases are not auto-upgraded. The approved Phase 3 copy upgrade has now
completed: the active local database is `platform-v4.db`, with versions 1–4.
Verified original configuration/data backups are retained in
`backend/data/backups/phase3-20261017T064910Z/`; `platform-v3.db` remains intact.
The dry-run found versions 1–3 and zero legacy submissions lacking revision records.

Read-only preparation:

```bash
PYTHONPATH=backend python -m app.storage.migrate \
  --upgrade-from backend/data/platform-v3.db --target backend/data/platform-v4.db
```

After approval, stop application writers, keep verified database/file/configuration
backups, then apply the copy upgrade:

```bash
PYTHONPATH=backend python -m app.storage.migrate \
  --upgrade-from backend/data/platform-v3.db --target backend/data/platform-v4.db \
  --apply --offline
```

Verify original record values, foreign keys, integrity and schema checksums, then
change only `WORKFLOW_DB_PATH` to the new absolute target in `backend/.env` and restart.
Do not change the session secret or remove previous databases. Rollback before new
writes can restore the previous configuration/code; rollback after new writes requires
reconciliation. No deployment is included in this phase.

## Verification and limits

Focused Phase 3 tests cover the complete revision-request/resubmission flow, blocking
and permissive policies, warning-only submissions, stale state/revision conflicts,
terminal states, concurrent transitions, revocation/reassignment, coauthor escalation,
private threads, fixed revision/page anchors, comment versions/deletion/replies,
historical identity protection, activity visibility/pagination/immutability, atomic
notification rollback, CSRF and impersonation rejection. The UI harness exercises
lifecycle and collaborator controls, conference policy, earlier-version comments,
private chair discussion, and the activity timeline, alongside the existing checker.

Final verification: **227 backend tests passed, 8 skipped** (existing external
Springer fixtures are absent). All 21 focused Phase 3 cases passed. The production
frontend build, expanded UI harness, and whitespace checks passed. The Phase 3
copy-upgrade dry-run passed at verification time; activation subsequently completed. Existing parser/runtime
limits remain as documented in Phase 2. Conversation history currently loads all
threads/comments; cursor pagination, per-comment revision history, rate controls for
high-volume discussion, notification delivery jobs and administrative retention are
future work. Soft deletion is moderation, not a privacy erasure or retention policy.
