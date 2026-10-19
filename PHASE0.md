# Phase 0: executable baseline

This phase repairs the existing application. It introduces no schema changes,
conference lifecycle expansion, immutable paper revisions, or formal review system.
The parsers, comparison engine, and standalone assessment contracts are retained.

## Repairs

- Frontend syntax errors and missing template-page modules/routes.
- Conference list response handling, member loading, template helpers, and notification API contracts.
- Conflicting conference template/submission routes, missing submission detail route, query parameter handling, and missing imports.
- Conference upload now builds PaperFacts before assessment and validates the file before creating a submission.
- Template versions initialize correctly, retain their IDs, support repeated names, and do not mutate the caller's rules.
- Submission scores and persisted timestamps survive reads; reviewer assignments round-trip correctly.
- Discussion reads no longer execute an accidentally pasted assessment block.
- Conference edits persist. Notification read-all is registered before the dynamic notification route.
- JWT secrets can be configured; an unconfigured local process generates a random secret instead of using a fixed placeholder.
- Passlib's compatible bcrypt backend is constrained in requirements.
- Compose build contexts, frontend proxy, persistent data volume, non-root backend execution, and CI test working directory are corrected.
- CI also builds the frontend.

## Configuration

Set `SECRET_KEY` to a random value of at least 32 characters for persistent sessions
and all multi-worker deployments. Without it, local sessions stop working on restart.
Compose requires this value explicitly.

Uploaded conference files default to `backend/data/submissions`, independent of the
launch directory. For existing installations whose files are under another directory,
set `SUBMISSION_FILE_DIR` to that directory. No existing files are moved.

`EMAIL_LOG_DIR` can redirect fallback email logs. Importing the application no longer
creates the log directory. Optional SMTP configuration is blank in `.env.example`.

Canonical conference routes now use:

- `/api/v1/conferences/{conf_id}/templates`
- `/api/v1/conferences/{conf_id}/templates/latest`
- `/api/v1/conferences/{conf_id}/templates/{template_id}`
- `/api/v1/conferences/{conf_id}/templates/diff`
- `/api/v1/conferences/{conf_id}/submissions`
- `/api/v1/submissions/{submission_id}` and its file/discussion/review endpoints

The standalone `/api/v1/submissions` assessment endpoint remains unchanged.
The formerly overlapping duplicate-prefix routes are not retained as ambiguous aliases.

## Validation

Backend tests run from the repository root with `PYTHONPATH=backend` and
`python -m pytest backend/tests -q`. Use temporary values for all `*_DB_PATH`
settings when running against a checkout containing real records; existing tests
can otherwise persist reports. New workflow tests use temporary stores.

The frontend production build and existing `component-test.mjs` harness were checked.
The harness requires a running backend and writes templates/reports, so it must
also use temporary database paths. No production records or migrations were used.

Compose configuration was validated; container images were not built or deployed.
Eight existing LNCS tests require external Springer template files absent here.
Full Ruff checking reports an existing repository-wide lint backlog; undefined-name,
duplicate-import, and syntax checks pass. No broad formatting cleanup was applied.

## Still deferred

Submission-level privacy, complete session controls, immutable revisions, processing
jobs, formal reviews, the conference compliance recheck placeholder, and the
unsupported conference deletion action remain outside phase 0. The existing UI
still lacks a login screen. Phase 0 does not make conference workflows ready for
private production submissions.
