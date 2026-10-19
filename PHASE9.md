# Phase 9 — Conference invitations

Conference chairs can invite authors and reviewers by email without collecting
account IDs. Invitations grant conference membership only; reviewer assignment and
access to individual papers still follow the existing permission rules. Chair
privileges cannot be granted through an invitation.

## Try it yourself

1. Open `http://localhost:5173`, sign in as the conference chair, and open
   **Conferences → Members → Invite participants**.
2. Enter the participant's email, select Author or Reviewer, and choose an expiry
   between 1 and 30 days. Create and copy the private link.
3. Share the link yourself. The application does **not** send invitation emails.
   The link is displayed only immediately after creation. If lost, revoke it and
   create another; history never retrieves its secret.
4. Open the link in a different browser profile. Sign in or create an account with
   the invited email. Inspecting the invitation does not join the conference.
5. Select **Accept invitation**, then open the conference's papers page. Authors
   can follow the existing submission workflow. Reviewers still need an explicit
   assignment before seeing private papers.
6. As chair, check the invitation history. Try revoking a second pending link,
   opening it with the wrong account, and opening it after expiry. None should
   grant membership. Existing conference members cannot have their roles replaced
   through invitations.

Use test accounts and a test conference for these checks. Do not paste private
links into public channels or issue trackers.

## Implementation and access

- `backend/app/api/invitation_routes.py`: chair-only GET/POST
  `/api/v1/conferences/{conf_id}/invitations`, DELETE
  `/api/v1/conferences/{conf_id}/invitations/{invitation_id}`, and authenticated
  POST `/api/v1/invitations/inspect` and `/accept`.
- `backend/app/services/invitations.py`: recipient and issuer checks, expiry,
  revocation, pagination, atomic membership creation, acceptance and audit events.
- `backend/app/models/invitation.py`: constrained recipient, role, expiry and token
  payloads. New invitation secrets contain 256 random bits; only hashes persist.
- `frontend/src/components/ConferenceInvitations.jsx`: chair form and history.
- `frontend/src/pages/Invitation.jsx`: inline authentication and explicit consent.
  Links use a URL fragment, not a query parameter. Successful acceptance removes
  the fragment. Secrets are not saved in browser storage.

Invitation states are pending, accepted, revoked and expired. History also marks
pending links invalidated by loss of issuer authority. Existing recipient accounts
are bound to their account ID; ambiguous case-normalized email matches fail closed.
Acceptance rechecks the issuer's active chair membership and conference state.
Removing a member does not allow an already accepted link to recreate membership.
Archived conferences cannot issue or accept invitations. Ordinary deadlines remain
independent of membership. Existing authentication, CSRF, Origin checks and rate
limits apply to the new APIs.

Password registration currently does not verify mailbox ownership. Invitation-link
possession is the credential; an email match is an additional restriction, not proof
of mailbox ownership. Email delivery, mailbox verification, reminders and bulk
invitations are future work. Never share the secret with an unintended recipient.

## Persistence and local activation

Migration `008_conference_invitations.sql` adds invitation records, pending-recipient
uniqueness and immutable terms/terminal-record guards. Phases 7 and 8 needed no new
migration, so Phase 9 uses schema version 8. Schema-7 installations remain readable;
the invitation controls report that activation is required until upgraded.

Activation copies the stopped schema-7 database to a new schema-8 database, verifies
integrity, foreign keys and all pre-existing rows, then changes only
`WORKFLOW_DB_PATH`. The original database, private uploads, Google configuration
and signing key are retained. See the activation record below for local results.

For recovery, stop all backend writers first. Restore the backed-up configuration
to select the retained database and restart. Returning to the old database loses
visibility of any subsequent schema-8 writes; reconcile those before production
rollback. Do not run concurrent servers against different copies during cutover.

## Automated verification

Run the backend suite through its isolated runner, which excludes local `.env`
and data. Replace the Python path if using a different virtual environment:

```bash
/tmp/paper-format-phase2-venv/bin/python backend/run_isolated_tests.py
/tmp/paper-format-phase2-venv/bin/python backend/run_ui_checks.py
```

The second command starts its own disposable backend on a reserved local port and
runs the real-API frontend harness. From `frontend/`, run:

```bash
npm run test:invitations
npm run build
```

Verified: 378 backend tests passed, 8 optional-fixture tests skipped; 25 of those
backend tests cover invitations. All 10 invitation UI scenarios, the real-API
component harness and the production frontend build passed. Coverage includes
permissions, wrong recipients, concurrency, rollback, expiry/revocation, immutable
records, schema-7 compatibility, authentication, fragment cleanup and pagination.
A real Google account consent flow still requires manual browser verification.

An initial legacy regression run inherited local database configuration and added
five test templates. Those exact records were removed after a recovery backup and
row-by-row verification that all other data was unchanged. The isolated runners
prevent subsequent regression runs from using the live database.


## Activation record

Activated 2026-10-18T18:09:07.005141+00:00. Local configuration now selects
`backend/data/platform-v8.db` (schema 8). The retained source is
`backend/data/platform-v7.db` (schema 7). Private recovery backups are in
`backend/data/backups/invitations-20261018T180906Z/`.

All existing rows across 45 tables were preserved; integrity and
foreign-key checks passed. The source database and retained data files were
verified unchanged. Only the workflow database path changed in configuration.

The backend restarted successfully on port 8000. Backend and frontend-proxy health
checks returned HTTP 200; both Google configuration endpoints reported sign-in
enabled. Open `http://localhost:5173` to test the invitation journey above.
