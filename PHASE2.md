# Phase 2: immutable revisions and saved formatting checks

This phase implements revision history and revision-bound formatting reports on
the existing conference submission workflow. It reuses the existing parsers,
fact extractor, rule engine, report components, account sessions, object permissions,
and private file storage. The local database is now activated on schema version 3;
see the activation update below. No deployment was performed.

## Implemented behavior

- A conference upload creates revision 1 and its complete formatting assessment
  atomically with the submission, ownership, generated issues, and audit event.
- Every revision has its own generated private file key, SHA-256, size, original
  filename, uploader, upload time, parent, sequential number, change summary, and
  submission status at upload. Extracted metadata is saved when the parser provides it.
- The initial conference template is pinned as a complete rules snapshot. Further
  revisions and rechecks use that snapshot even after the conference publishes a
  newer template. Adopting another template requires a later explicit workflow.
- Each recheck appends a report with a run ID, sequence, engine version, timestamp,
  assessment, and validation status. Earlier reports remain available. A recheck
  of an older revision cannot replace the current revision's formatting score.
- Reports retain the existing rule IDs, severity, expected/actual values, evidence,
  advice, extracted facts, and parser confidence. No new layout capabilities or
  reliable page coordinates are claimed.
- Validation statuses are `passed`, `passed_with_warnings`, `failed`, and
  `unable_to_validate`. Processing is shown while the request is active. Formatting
  outcomes are separate from conference acceptance/rejection decisions.
- Parser/storage failures during recheck produce an appended unable-to-validate
  attempt with a safe error message. Prior reports remain readable. The compatibility
  score is cleared if the latest check of the current revision cannot validate it.
- Upload retries use a submission-scoped request key. Reusing it with identical
  inputs returns the same revision; different inputs return 409. An identical
  current file is rejected. Uploads require the expected current parent, checked
  again inside the transaction, so concurrent uploads have one winner.
- Database triggers reject UPDATE and DELETE for revision/report records. Files
  are never overwritten by application upload routes. Normal failed writes roll
  back all related records and delete only the newly staged file.
- The submitting author, editing collaborators, and conference chairs can upload
  and recheck. Assigned reviewers can read history/reports and download authorized
  files. Finalized accepted/rejected papers cannot receive new revisions. All
  permissions are enforced on the backend and rechecked before writes commit.
- Existing generated issues are linked to the exact report and revision that
  produced them. Later revisions create their own issues. Rechecks append reports
  without duplicating issues or automatically resolving earlier discussions.
- Uploading a revision clears the compatibility submission verdict. Earlier legacy
  reviewer feedback stays stored; formal reviews tied to exact revisions remain
  a later phase.

## Main implementation files

| File | Responsibility |
| --- | --- |
| `backend/app/services/formatting.py` | Shared `evaluate_document` service and formatting-status classification |
| `backend/app/checks/submission.py` | Existing standalone batch adapter uses the shared service and preserves per-file failure reports |
| `backend/app/storage/migrations/003_revisions.sql` | `paper_revisions`, `revision_checks`, `issue_findings`, immutability triggers |
| `backend/app/storage/revisions.py` | Scoped reads, immutable inserts, compatibility updates, and report projections |
| `backend/app/api/submission_routes.py` | Initial revision integration and replacement of the recheck placeholder |
| `backend/app/api/revision_routes.py` | History, protected files/reports, retry-safe uploads, and recheck execution |
| `backend/app/api/issue_routes.py` | Issue origin projected as revision/check IDs |
| `backend/app/storage/migrate.py` | Explicit versioned copy upgrade; source database remains intact |
| `frontend/src/pages/ConferencePapers.jsx` | Conference paper list and first upload |
| `frontend/src/pages/SubmissionDetail.jsx` | Overview, formatting checks, files/revisions, and historical report selection |
| `frontend/src/pages/Results.jsx` | Existing detailed `PaperCard` reused with formatting labels |
| `frontend/component-test.mjs` | Existing UI checks plus authenticated conference/revision/report flows |
| `backend/tests/test_phase2_revisions.py` | Preservation, permissions, races, retries, rollback, and copy-upgrade regression tests |

## API and screens

The existing first-upload and latest-file routes retain their shapes. The standalone
`POST /api/v1/submissions` batch checker and its reports remain available.

| Method | Path | Result |
| --- | --- | --- |
| POST | `/api/v1/conferences/{conf_id}/submissions` | Existing submission response; also creates revision 1 and its full report |
| GET | `/api/v1/submissions/{id}/file` | Compatibility download of the current file |
| GET | `/api/v1/submissions/{id}/revisions` | History, current revision ID, and current user's edit capabilities |
| POST | `/api/v1/submissions/{id}/revisions` | Multipart `file`, `parent_revision_id`, `request_key`, optional `change_summary` |
| GET | `/api/v1/submissions/{id}/revisions/{rev}/file` | Authorized, integrity-checked attachment |
| GET | `/api/v1/submissions/{id}/revisions/{rev}/checks` | Saved reports, latest first, including linked issue IDs |
| POST | `/api/v1/submissions/{id}/check-compliance` | Optional JSON `revision_id`; defaults to current; appends a report |

Frontend routes are `/conferences/:confId/submissions` and
`/submissions/:submissionId`. A `?revision=...` URL preserves selection of an earlier
revision. Conferences link to their paper workspace. Issue details link back to the
originating revision. Downloads use the authenticated API rather than public file paths.

## Processing and limits

For this phase, parsing/assessment runs during the upload/recheck request in the
existing application's worker thread pool, outside the event loop. Parsing finishes
before the short database write transaction starts. Existing byte/page/archive bounds
and request throttles apply. This introduces no queue or additional service.

There are no persisted queued/running jobs or restart retries. A crash before commit
can leave an unreachable generated file, as in Phase 1; reconciliation and cleanup
must inspect references before deleting files. Native parser CPU/memory isolation,
process deadlines, and durable jobs remain future work. Saved completed reports survive
restarts. Explicit rechecks are retryable but deliberately create another report;
only revision uploads have request-key deduplication.

The current history APIs return all revisions/checks. Pagination and retention policy
should be added before operating conferences with large revision/check histories.
Administrative retention/deletion will need an explicit audited mechanism consistent
with the immutability triggers; ordinary application deletes are intentionally blocked.

## Explicit database activation

The version 2 installation remains readable for its existing features. Fresh empty
test databases initialize to version 3. Existing nonempty databases are never silently
upgraded. Revision operations and new conference uploads require version 3 and report
503 with a migration-required message until activation.

Read-only preparation, from the repository root:

```bash
PYTHONPATH=backend python -m app.storage.migrate \
  --upgrade-from backend/data/platform.db --target backend/data/platform-v3.db
```

The local dry-run found schema versions 1 and 2 and zero submissions. It created
no target. Legacy templates and reports retain their previous ownership protections.

After explicit approval, stop application writers, retain verified database/file
and configuration backups, and run:

```bash
PYTHONPATH=backend python -m app.storage.migrate \
  --upgrade-from backend/data/platform.db --target backend/data/platform-v3.db \
  --apply --offline
```

The command uses SQLite's consistent backup into a staged database, checks the source
schema checksums, applies the new migration in a transaction, checks integrity and
foreign keys, and publishes a new mode-0600 target without overwriting an existing
file. It leaves `platform.db` intact. After verifying original table contents, update
only `WORKFLOW_DB_PATH` in `backend/.env` to the new absolute path and restart.
Keep the persistent session secret and other settings.

Before accepting new writes, rollback can restore the previous configuration/code
against the retained database. After new writes, rollback needs reconciliation;
switching the path alone would hide those new records.

Existing papers without trustworthy revision records keep their current protected
download. Their revision endpoints show an empty history, and new revisions/rechecks
return 409 until a separately audited reconciliation supplies the original file,
owner, and template. No file or old assessment is invented. The local activated
database currently has no such papers.

## Verification and remaining scope

Full backend regression: **205 passed, 8 skipped** (existing external Springer fixtures
are absent). The production frontend build passed. The UI harness additionally checks
authenticated paper lists, revision history, retained check attempts, file controls,
and links to earlier revisions. All UI checks passed against an isolated temporary
database. Whitespace checks passed. The version 2 database and backend configuration
were not modified during that verification.

### Activation update

The approved copy upgrade has since completed, and `backend/.env` selects
`backend/data/platform-v3.db`. Verified original data and configuration backups are
retained under `backend/data/backups/phase2-20261017T063238Z/`; the original
`platform.db` remains intact. A WAL publishing defect found during activation was
fixed with explicit connection closure, journal consolidation, reopen verification,
and a regression test. The incomplete first artifact is preserved in the backup.
See `PHASE3.md` for the activation details and the next copy upgrade.

This phase does not add formal reviews, review criteria, a full submission state
machine, configurable formatting gates, coauthor invitations, annotations, document
diffs, double-blind projections, or durable notifications/jobs. The existing single-blind
foundation and legacy review endpoints retain their documented limits.
