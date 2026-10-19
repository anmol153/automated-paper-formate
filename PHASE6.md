# Phase 6: conference intake, tracks and paper metadata

This phase adds conference scheduling and lifecycle controls, conference-local tracks,
stable paper numbers, and editable bibliographic metadata to the existing application.
It reuses the formatting checker, template snapshots, immutable files/reports, submission
state machine, conference membership and formal-review permissions.

Implementation and tests used schema version 6 in temporary databases. The subsequent
approved Google-auth activation copied the local database to `platform-v7.db` and
activated migrations 5–7, including this phase. The original database and verified
backups remain intact; see `GOOGLE_AUTH.md` for the activation result. No dependencies
were added or production deployment performed.

## Conference settings and lifecycle

Conference chairs can configure abbreviation, research scope, an HTTP/HTTPS website,
lifecycle status, submission opening/closing times, a requested-revision deadline,
and required title, abstract, author-list and track fields. Settings use an expected
version, so stale edits return 409. Conference name/description and participant
management retain their existing APIs. Existing `start_date`/`end_date` values are
retained as historical fields and are not guessed to be new enforced deadlines.

The new settings default to an open conference with no date limits or additional
metadata requirements. This preserves existing upload behavior after activation.
Explicit deadline configuration requires timezone-aware timestamps, stored in UTC.
The UI accepts local times and labels their conversion. Opening is inclusive;
closing is exclusive. Closing must follow opening, and a configured revision deadline
cannot precede the initial submission deadline.

| Lifecycle status | Permitted next statuses |
| --- | --- |
| Setup | Open, Closed, Archived |
| Open | Setup, Reviewing, Closed |
| Reviewing | Open, Closed |
| Closed | Open, Reviewing, Archived |
| Archived | None |

Returning to Setup requires no existing papers. Archiving requires every paper to
be accepted, rejected or withdrawn. Archived settings and tracks cannot be edited.
These controls never silently accept, reject or withdraw submissions.

| Operation | Conference requirements |
| --- | --- |
| Create an initial submission, including a draft | Open and within the initial submission window |
| Revise/edit metadata on Draft or Submitted | Open and within the initial submission window |
| Revise/edit metadata on Changes Requested | Open or Reviewing and before the requested-revision deadline, when set |
| Submit a Draft for review | Initial submission window, completed metadata requirements and existing formatting gate |
| Resubmit after Changes Requested | Requested-revision window, a newer revision, completed metadata and formatting gates |
| Assign/start reviews, request changes, accept or reject | Open or Reviewing, plus all existing paper permissions and lifecycle rules |
| Save or submit a formal review | Open or Reviewing, plus its existing assignment, paper-state, deadline and edit-policy rules |

All author deadlines apply to chairs using the same upload/metadata paths; there is
no implicit chair bypass. The backend checks windows before expensive parsing and
again in the commit transaction. A file staged just before a deadline/lifecycle change
is removed if the final check rejects the upload. Reviewer assignment and review/decision
guards run inside their existing shared transactions.

Closing a conference does not delete files or revoke authorized reading. Explicit
release of already submitted reviews may occur after closure, allowing chairs to
publish finalized feedback. Withdrawal, conversation, issue handling and historical
formatting rechecks retain their existing permissions; this lifecycle is not a global
read-only archive or a retention/deletion mechanism. Reopening Closed is an explicit
configuration action. Requested revisions remain possible after initial submissions
close when the conference is Open or Reviewing and their own deadline permits them.

## Tracks

Tracks have a stable ID, conference, name, description, active flag and version.
Chairs create, rename and deactivate/reactivate them. Names are unique within a
conference under SQLite's case-insensitive `lower(name)` comparison. Updates require
the expected track version; track writes
are audited. Tracks cannot be selected across conferences.

Deactivation stops new papers from choosing that track. Existing papers retain their
track and may keep it while making another permitted metadata edit or resubmission.
Tracks are not deleted, so historical references remain valid. History retains track
IDs; displayed labels follow the track's current name.

Tracks currently organize/filter papers and share their conference's pinned formatting
template and review configuration. They do not grant access or introduce track chairs,
track-specific deadlines/templates/forms, assignment pools or visibility scopes.

## Paper numbers and metadata

Each paper receives a positive sequential number scoped to its conference. The stable
submission ID remains the API identity; the number is its human-readable label. Number
allocation occurs in the upload transaction, and concurrent uploads receive distinct
numbers. Updating metadata or uploading a revision never changes a number. Database
triggers prohibit changing/deleting catalog records, so existing numbers are not reused.
Rolled-back uploads do not consume a committed number.

The canonical paper details contain a title, abstract, ordered author names and
affiliations, and an optional conference track. They are separate from account-level
coauthor grants and from metadata extracted from the uploaded file. A declared author
name does not grant access, claim an account or automatically establish an account
conflict. The existing coauthor/assignment conflict system and manual conflict review
remain necessary.

Metadata is strictly bounded: title 500 characters, abstract 12,000, at most 50 authors,
each name 200 and affiliation 500 characters, and a multipart metadata JSON limit of
50,000 characters on initial upload. Unknown payload fields, blank author names and
invalid/cross-conference tracks are rejected. No ORCID verification, author-account
discovery, corresponding-author email collection or bibliography import is introduced.

The first upload accepts optional `metadata_json`. If omitted, schema-6 uploads seed
title/author names only from the existing extractor, when those values fit the declared
field bounds; no abstract or affiliation is invented. Source is recorded as extracted.
Explicit metadata records declared source. Legacy backfills leave these fields blank
and record legacy source. The UI sends supplied metadata when the user enters it;
otherwise the existing extraction path can seed the paper details.

If a required field is absent on initial upload, the file/report/number are retained
as a Draft, as with an unmet formatting gate. The author fills the missing details
and explicitly submits. Requirements are checked again when proceeding to review;
academic scores and formatting scores remain separate. Changing conference requirements
does not retroactively change existing paper states or decisions.

The submitting author, editing collaborators and an eligible unconflicted paper chair
may edit metadata during Draft, Submitted or Changes Requested, within the applicable
window. Read-only collaborators and reviewers cannot edit. Under Review and terminal
papers are locked; chairs request changes before editing a paper under review.
Legacy papers without an identified revision still require reconciliation.

Every edit appends an immutable metadata version with source, track, timestamp,
editing account and the current immutable revision at that edit. Saves require both
the expected metadata version and current revision ID. Concurrent edits have one
winner; stale edits return 409. Audit failure rolls back the metadata/configuration
write. Old metadata rows, files and formatting reports are never rewritten.

Authorized paper readers can browse metadata history, paginated by version (default
20, maximum 50). This is submission-level metadata history, not a claim that the
declared fields match the text of every revision. Old annotation anchors and extracted
revision metadata retain their original meanings.

## Interface and APIs

The conference paper screen now shows scheduling, scope, requirements and tracks.
Chairs have structured settings/track forms; other conference members receive read
views. The submission form includes title/abstract, ordered authors/affiliations and
track selection. Closed-window upload controls explain why intake is unavailable.
The paper list supports title/filename/number search and track filtering over only
the papers the caller can access.

The submission overview includes canonical details, metadata history, and the stable
paper number. Headers, reviewer workspace and chair dashboard use the declared title
and number while retaining the filename. Existing tabs, downloads, detailed formatting
reports, version comparisons, collaboration and formal review pages remain in place.

All paths below use `/api/v1`:

| Method | Path | Purpose |
| --- | --- | --- |
| GET, PUT | `/conferences/{id}/settings` | Member-readable settings; chair configuration with `expected_version` |
| GET, POST | `/conferences/{id}/tracks` | Member-readable tracks; chair creation |
| PUT | `/conferences/{id}/tracks/{track_id}` | Chair update with `expected_version` |
| GET, PUT | `/submissions/{id}/metadata` | Authorized details/capabilities; guarded metadata save |
| GET | `/submissions/{id}/metadata/history` | Protected history with `limit` and `before_version` |

The initial conference upload adds optional multipart `metadata_json`; existing
file-only clients keep working. Existing submission responses add `paper_number`,
`title`, `abstract`, `authors`, `track_id` and `metadata_version`. Listing accepts
`track_id` and extends existing `q` search to title and number. Existing identifiers,
routes and original fields remain available. Session/CSRF and private-response
protections apply to all new writes and reads.

## Storage and migration preparation

Migration `006_conference_intake.sql` introduces `conference_settings`,
`conference_tracks`, immutable `submission_catalog`, and immutable
`submission_metadata_versions`. Author entries and settings use bounded JSON within
their respective records, consistent with existing immutable form/report snapshots;
tracks and paper identity relationships have database foreign keys.

Copy upgrade backfills paper numbers deterministically by original creation timestamp
and submission ID within each conference. It creates one blank legacy metadata version
without inventing title, authorship, ownership or a revision. Original submission
columns, file keys, report JSON and timestamps remain intact. The legacy multi-database
import path supplies the same catalog/metadata records after copying its old rows;
unknown legacy ownership remains quarantined. Unversioned legacy store reads are
preserved. No imported paper is made public by receiving a number.

Older schema-4/5 installations continue their existing uploads, review/check/diff
features. Settings/metadata GETs report disabled capability; new configuration and
metadata writes require schema 6 and return 503 until an explicit upgrade. Existing
nonempty databases are never silently upgraded.

The read-only local preflight passed: current versions 1–4, target versions 1–6,
no preflight issues, no legacy submissions needing revision reconciliation. No target
was created. The following command is a dry run from the repository root:

```bash
PYTHONPATH=backend python -m app.storage.migrate \
  --upgrade-from backend/data/platform-v4.db --target backend/data/platform-v6.db
```

Activation requires explicit approval under the original task constraint. Google
authentication now adds migration 7: use `GOOGLE_AUTH.md` and `platform-v7.db` for
the current combined activation. The commands here record this phase's original
schema-6 procedure; they do not pin the current CLI to version 6. It applies all
registered pending migrations. After approval,
stop all writers, retain verified configuration/database/file backups, then use:

```bash
PYTHONPATH=backend python -m app.storage.migrate \
  --upgrade-from backend/data/platform-v4.db --target backend/data/platform-v6.db \
  --apply --offline
```

Verify all original table contents, migration checksums, integrity and foreign keys,
then update only `WORKFLOW_DB_PATH` in `backend/.env` to the new absolute target and
restart the backend/frontend. Retain the session secret, existing database and other
configuration. The CLI applies all registered migrations, not a version inferred
from the target filename. Rollback after new writes requires reconciliation;
switching back alone would hide those new records.

## Verification and remaining work

Phase 6 focused tests cover timezone/boundary validation, closed-window writes,
deadline changes during parsing, separate revision windows, required metadata,
cross-conference and inactive tracks, immutable history/numbers, concurrent saves and
uploads, role permissions, chair recusal, closure/reopening, rollback and schema-5
copy upgrades. Migration regressions cover unversioned legacy reads/imports and
source preservation. The real-API UI harness exercises settings, tracks, declared
metadata/history and separate chair/author/reviewer accounts alongside prior flows.
Verification: **308 backend tests passed, 8 skipped** (the existing external Springer
fixtures are absent). The 26 focused Phase 6 cases passed, along with all six legacy
migration regressions. The production frontend build, complete UI harness and
whitespace checks passed. All tests used isolated temporary databases and files.

Invitations, track-chair roles and multiple membership roles, automatic conflict
discovery, embedded document annotations, double-blind documents, email/reminders,
durable processing, retention tools and production deployment remain future work.
Conference settings themselves currently retain the latest version plus audit events;
full historical settings snapshots and operational pagination outside metadata history
are not added here. Existing native-parser resource-isolation limits remain unchanged.
