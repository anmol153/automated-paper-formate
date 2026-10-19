# Phase 1: secure platform foundation

Phase 1 adds backend paper permissions, persisted sessions, bounded uploads,
private generated-key file storage, and a versioned unified database. It retains
the existing standalone checker and report rendering. The approved local database
activation is complete: legacy records were copied into `backend/data/platform.db`.
Original databases remain intact. No deployment has been performed.

## Access rules

- A conference chair can access that conference's papers.
- A submitting author can access their own paper while still a conference member.
- Explicit collaborators can read the paper; only collaborators with `can_edit`
  can resolve issues. Collaborator invitation/management UI belongs to phase 2.
- Reviewers need an active assignment to the particular paper and current reviewer
  membership. Revocation removes access. A generic reviewer role is insufficient.
- Unrelated authors, reviewers, and visitors cannot read the paper, download its
  file, read/post discussions or issue comments, or infer it from notifications.
- Ownership is never inferred for legacy submissions. They remain chair-only until
  explicitly reconciled. Legacy template edits and report history are also unclaimed.
- Authors do not receive reviewer identifiers or unreleased recommendations in
  submission payloads. Discussion reviewer identifiers are projected as `Reviewer`.
  Legacy review scores are retained separately from formatting compliance scores.
- Conference public listings omit members/owners; only chairs see member identities.
- Status changes, assignments, conference configuration, and conference template
  writes require chair permission. A conference cannot lose its final chair.

This is a single-blind foundation. Double-blind file/metadata projections, track
chairs, configurable review visibility, and full conflict handling remain later work.
Do not enable double-blind review on the basis of these identifier projections alone.

## Sessions and browser behavior

`POST /api/v1/auth/login` still accepts OAuth password form fields and returns an
access token for API clients. Tokens must correspond to a live database session;
previous stateless JWTs stop working. Expired, revoked, deleted-user, and disabled-user
sessions are rejected on every protected endpoint.

The browser uses a host-only, HttpOnly `paper_session` cookie and a readable
`paper_csrf` cookie. Cookie-authenticated mutations must supply `X-CSRF-Token`.
Cross-site login/registration and unapproved mutation origins are rejected.
`GET /auth/me` restores the browser identity; `POST /auth/logout` revokes the session.
Browser token storage is removed, and session changes reset private page state.
Login and registration have persistent request throttles; conference uploads have
per-user throttles. API responses and downloads use private/no-store headers.

Set a persistent random `SECRET_KEY` (at least 32 characters). `COOKIE_SECURE=true`
is the default and is required for HTTPS deployments. For local HTTP development
only, set `COOKIE_SECURE=false`. Configure `CORS_ORIGINS` as a JSON array of trusted
frontend origins when using another origin or an HTTPS reverse proxy.

## Checker and integration compatibility

Anonymous upload/compare still returns formatting results. Anonymous results are
not saved in globally readable report history. Sign in to create templates or
save/view/delete your own reports. Report filenames are scoped to an account, so
one user's `paper.pdf` cannot overwrite another user's report. Existing unowned
reports remain in the database and are not exposed through the private API.

Global published templates remain selectable, but only their recorded creator
can update/delete newly created templates. Legacy templates are reusable as inputs;
editing one requires an explicitly claimed owner or creating an owned copy.

Google imports require authentication. A shared service account additionally
requires an explicit user ID grant in `GOOGLE_IMPORT_USER_IDS` (JSON array, empty
by default). Downloads are streamed with a byte ceiling. The application must not
use shared service credentials as unrestricted access to everyone's private Drive.

The conference recheck endpoint now returns an honest 501 until revision-bound
processing is implemented; it no longer claims a check ran when it did not.
Conference notifications are in-app, generic, and limited to current participants;
email for these events is deferred to the later durable delivery service.

## File storage

New conference files use random storage keys independent of their display filename,
mode 0600, exclusive creation, SHA-256, and recorded size. Downloads authorize the
paper, verify integrity, reject symlink/unsafe-key paths, and send attachments.
Normal upload failures roll back submission/security/issues/audit changes and remove
the staged file. A process crash can leave an unreachable orphan; later recovery
processing must reconcile these files before deletion.

`SUBMISSION_FILE_DIR` keeps the phase 0 default, `backend/data/submissions`.
Set it explicitly if legacy files live elsewhere; no source files are moved.

`MAX_UPLOAD_BYTES` defaults to 50 MiB, aggregate `MAX_BATCH_BYTES` to 100 MiB,
`MAX_PDF_PAGES` to 500, and `MAX_ARCHIVE_BYTES` to 100 MiB. Request bounds apply before
multipart parsing, including chunked bodies. Word archives are checked for required
parts, traversal/symlink entries, duplicate entries, expansion limits, XML declarations,
and macros. Encrypted PDFs, embedded attachments, and active PDF actions are rejected.
These checks are not an antivirus or a parser sandbox. CPU/memory isolation and durable
processing/retry infrastructure remain work for the processing phase.

## Versioned database and atomic writes

`storage/migrations/001_initial.sql` and `002_security.sql` are frozen migration
snapshots with recorded checksums. Existing source schemas are not silently upgraded.
New empty test/development database files are mode 0600 and can be initialized; a legacy file requires
an explicit copy migration before security features can use it.

`WORKFLOW_DB_PATH` selects one database for all stores and is supported through the
process environment or `backend/.env`. Conflicting individual `*_DB_PATH` overrides
are rejected. Related conference writes share one SQLite transaction. The schema
adds foreign keys and security/session/ownership/audit records; account-scoped report
and global-template ownership metadata also supports the standalone adapters.

### Read-only preflight

From the repository root, using an environment with backend dependencies:

```bash
PYTHONPATH=backend python -m app.storage.migrate \
  --source-dir backend/data --target backend/data/platform.db
```

This prints counts and unresolved reference counts, without private record values,
and creates no target. The current repository preflight found 10 users, 4 conferences,
5 memberships, 103 templates, and 12 reports, with no unresolved references.
No submission database was found among these default source files. Custom legacy
paths must be inventoried separately; do not assume the default directory is exhaustive.

### Applying after explicit approval

Stop all application writers first. Keep verified backups of the source databases
(including WAL state) and paper files. For the default legacy directory:

```bash
PYTHONPATH=backend python -m app.storage.migrate \
  --source-dir backend/data --target backend/data/platform.db --apply --offline
```

The command stages a new database, preserves IDs/report JSON/timestamps/password
hashes, checks counts, references and integrity, then publishes a new mode-0600 file.
It refuses an existing target and aborts on invalid references. Source files remain
untouched. Existing sessions are invalidated. Already versioned source files are
not treated as legacy inputs.

For a genuinely fresh install, omit `--source-dir` and `--offline`; `--apply` is
still required. Configure `WORKFLOW_DB_PATH` to the resulting absolute path only
after verification, remove conflicting legacy overrides, and restart the application.
Compose expects `/app/backend/data/platform.db` and does not auto-migrate a volume.

Rollback before accepting new writes means stopping the new app, retaining the new
database, and restoring the prior code/configuration against the untouched sources.
After new writes, rollback needs data reconciliation; switching paths alone would
lose access to those writes. Do not use the old application to serve confidential
new-platform records.

## Verification and limits

New tests exercise real login/cookie/bearer sessions, CSRF, logout replay, expiry,
account state, cross-paper access, collaborator grants, reviewer identity/score
privacy, notification filtering, upload rollback, malformed archives, integrity,
chunked request limits, migration preservation/no-overwrite, and transaction rollback.
Legacy API regressions now use authenticated principals where history/mutations are
private; separate adversarial tests exercise the real authentication dependencies.

No new dependencies were installed for this phase. Existing checker tests, frontend
build, and the UI harness are retained. Full historical Ruff style cleanup, container
image builds, email retries, immutable revisions, and formal reviews are not included.

Final checks: **190 backend tests passed, 8 skipped** (external Springer fixtures
absent). The production frontend build, existing UI smoke tests plus login-form
checks, Compose configuration, focused lint checks, and whitespace checks passed.
The existing repository-wide lint backlog remains outside this phase.

## Local activation completed

Following approval to proceed, activation completed on 17 October 2026 (Asia/Kolkata).
All eight stores now resolve to `backend/data/platform.db` through `backend/.env`.
The local configuration has mode 0600 and a newly generated persistent session secret.
`COOKIE_SECURE=false` supports local HTTP development; HTTPS deployments must use
`COOKIE_SECURE=true`. The secret is not included in this document or committed files.

Verified backups are stored in
`backend/data/backups/phase1-20261016T231233Z/`: `raw/` preserves the original files,
`sqlite/` contains consistent SQLite backups, and `manifest.json` records the
inventory, source hashes, and verification results. No running backend writers or
open project data handles were found before copying. Twelve original data files
were backed up and remain byte-for-byte unchanged.

The copy preserved all original column values, including IDs, password hashes,
report JSON, and timestamps: 10 users, 4 conferences, 5 memberships, 103 templates,
and 12 reports. Schema checksums, foreign keys, integrity checks, and source hashes
passed. Legacy template/report ownership remains unclaimed as documented above.

Read-only API smoke checks against the configured database passed: health and
public conferences returned 200; unauthenticated account and report requests returned
401. Conference listings did not expose member/owner lists, and all responses had
private/no-store headers. All six migration safety tests passed in isolated storage. No test accounts or submissions were added to this database.

For isolated regression runs after activation, override `WORKFLOW_DB_PATH` explicitly
as well as the individual test database paths. An empty process `WORKFLOW_DB_PATH`
disables the configured unified path for the legacy isolation harness. Set
`COOKIE_SECURE=true` when running tests that verify the production cookie default.
Do not run a write-producing test harness against the activated database.

This completes Phase 1 activation. Immutable revisions, revision-bound processing,
and the conference submission workspace remain the next implementation phase.
