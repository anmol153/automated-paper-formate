# Phase 7: conference onboarding and template publishing

The documented implementation previously ended at Phase 6; this phase closes the
setup gaps encountered during manual use. It connects existing conference membership,
template versioning, rule editing and submission APIs through the current React app.
It introduces no database schema changes, migrations, application dependencies or
external delivery services. Existing databases, uploaded files and report snapshots
are retained.

## What changed

- **Conference template publishing:** the Papers page and existing
  `/conferences/:id/latest` route now offer chairs an import/edit/publish workflow.
  A chair may import PDF/DOCX/LaTeX rules, copy saved standalone rules, start a blank
  named template, or copy an earlier published version. All use the existing
  `RuleEditor` and document-rule inference API. Importing only previews rules;
  publication is a separate explicit action.
- **Published history:** conference members can select immutable template versions
  and inspect their rules in a disabled editor. A comparison link opens the existing
  diff route for the two latest versions. Editing a historical version creates a
  separate unpublished draft; publishing appends a new version. It never updates
  the historical row or the standalone source template.
- **Upload readiness:** initial paper uploads remain disabled while template history
  is loading, is unavailable, or is empty. Missing-template guidance explains what
  the chair needs to do. Successful publication reloads history and enables uploads.
  Existing submission deadlines and backend permissions remain independently enforced.
- **Conference selection:** the standalone Submit page now has a conference chooser
  that links to the selected conference's paper submission form. It explicitly
  explains standalone formatting reports versus conference review submissions.
  A public conference listing does not grant membership or paper access.
- **Account identity:** Account settings display the current user's account ID with
  a copy button and manual-copy fallback. Participants can share that ID with the
  chair instead of running browser-console commands. The ID is not a sign-in token.
- **Role guidance:** login and membership screens explain conference-scoped roles.
  The membership selector displays Chair while sending the existing `owner` value.
  New conference creators become chairs through the existing backend transaction.
- **Navigation:** conference cards link to Papers and Templates. Version comparison
  no longer requires typing IDs into browser prompts. The unsupported conference
  Delete button was removed; no data-deletion operation was added.

## Two onboarding defects fixed

The frontend used `/api/v1/conferences` while FastAPI registered the collection as
`/api/v1/conferences/`. Through Vite's proxy, FastAPI could issue an absolute 307
redirect to the backend host/port. The browser then left the same-origin proxy path,
which could lead to the reported cross-site authentication rejection. The API client
now uses the canonical trailing slash. Both GET and POST also accept the slashless
path directly for existing clients, without redirects. The slashless aliases are
hidden from OpenAPI so the documented collection remains unchanged.

The original strict Origin/Fetch Metadata check has been restored. Cookie writes
still require a valid session, allowed Origin and CSRF header. The earlier workaround
that relaxed the cross-site check is no longer needed. Browser development uses
Vite's relative `/api/v1` proxy; server-rendered tests may supply their isolated API
host explicitly.

ConferenceStore.get() returns conference metadata without populating member arrays.
The details API previously returned that empty list even for chairs, preventing the
UI from identifying its chair or displaying members. The API now populates actual
members and owner IDs only after chair authorization, including its creation and
update responses. Public lists and non-chair detail responses still redact those
arrays. Unrelated accounts still cannot read conference details.

## Data and API compatibility

Existing template endpoints are reused:

| Method | Path under `/api/v1` | Use |
| --- | --- | --- |
| GET | `/templates` | Select saved standalone rules |
| GET | `/templates/{template_id}` | Load the full standalone rule set |
| POST | `/templates/import` | Preview rules inferred from an uploaded template |
| GET | `/conferences/{id}/templates` | Read published version history |
| GET | `/conferences/{id}/templates/{template_id}` | Read an authorized snapshot |
| POST | `/conferences/{id}/templates` | Chair-only immutable publication |
| POST | `/conferences/{id}/templates/diff` | Existing version comparison |

New initial submissions use the latest published conference template. Existing
papers, later revisions of those papers and historical checks remain pinned to their
original template snapshot, as before. Publication does not recheck or alter papers,
make decisions, change deadlines or notify participants automatically.

All template writes retain backend membership checks and audit events. Hiding the
publisher for authors is additional UI guidance, not the authorization boundary.
Conference membership still uses existing account IDs and one role per conference.
No email invitation, arbitrary account lookup or automatic self-enrollment is added.

## Manual walkthrough

1. Sign in at `http://localhost:5173`. For a full role test, use separate browser
   profiles for chair, author and reviewer; tabs in one profile share a session.
2. As the chair, open Conferences and create a conference. Open its Templates page
   or its Papers page and expand **Configure a template**.
3. Choose a file and **Import template rules**, or choose a saved standalone template
   and **Load saved rules**. Review the rules, enter a name, and **Publish template
   version**. A blank rule skips that check; only configure checks the parser supports.
4. In each participant's Account settings, copy **Your account ID**. As chair,
   open the conference's Members panel and add the author/reviewer IDs with their
   respective roles. Conference membership alone does not assign a paper reviewer.
5. As the author, open Submit, choose the conference, and **Open conference
   submissions**. Fill required metadata and upload the paper. The conference's
   formatting gate determines whether it proceeds or stays in Draft. No template
   publication through DevTools or account-ID console lookup is needed.
6. As chair, assign the reviewer on the paper's Overview. As reviewer, use Review
   workspace to discuss and formally review it. The existing revision, review-release
   and decision workflow applies.
7. As chair, copy a published template for editing and publish another version.
   Confirm history retains both, the older version is read-only, and the comparison
   link opens. Existing papers retain their original template; newly created papers
   use the new version.
8. As the author, confirm published rules are visible but publication/membership
   controls are absent. An unrelated account should still fail to open private papers.

Restart the backend after the route changes and refresh the frontend. In browser
Network, a new conference POST should remain on the frontend `/api/v1/conferences/`
URL with no redirect to port 8000.

## Verification

- **82 backend regression tests passed**, including six Phase 7 cases plus session,
  file/revision and Google-auth regressions. They cover both collection URL forms
  without redirects, CSRF and untrusted/cross-site request rejection, chair-only
  membership visibility, template publication permissions, retained versions and
  different template pins for old versus new papers.
- **13 onboarding UI scenarios passed** with an isolated API adapter: saved-rule
  publication/history, author views, missing-template handling, reload and publication
  retry, import failure retention, blank drafts, account-ID copy/fallback, conference
  navigation and enabling uploads after publication.
- The expanded **real-API component harness passed**, including existing standalone
  formatting, revision comparison, collaboration and formal-review flows, plus chair
  membership/template controls and author template access. It ran against an isolated
  backend database and private-file directory under `/tmp`, then shut down. This
  harness uses JSDOM; it does not certify browser rendering or the live Google chooser.
- Production frontend build and whitespace checks passed. Existing Pydantic/Starlette
  deprecation warnings remain.

With backend dependencies installed in your selected virtual environment, run the
focused Python checks from the repository root:

```bash
COOKIE_SECURE=true GOOGLE_OAUTH_CLIENT_ID= PYTHONPATH=backend python -m pytest \
  backend/tests/test_phase7_onboarding.py backend/tests/test_phase1_security.py \
  backend/tests/test_phase2_revisions.py backend/tests/test_google_auth.py -q
```

The environment overrides are test-only: the existing security tests expect HTTPS
cookies and the default Google configuration test expects Google to be disabled.
Google-specific cases configure their own isolated settings. Do not change the local
application `.env` for these tests.

Frontend checks:

```bash
cd frontend
npm run test:onboarding
npm run build
# Run against a separately started disposable backend, never production data:
API_BASE=http://127.0.0.1:8017/api/v1 npm run test:components
```

Email invitations/reminders, multiple roles, track chairs, document selection
annotations, double-blind document delivery, durable processing and retention tooling
remain separate future work. Template history retains the existing unpaginated API;
publication has no automatic retry or idempotency-key mechanism. No deployment or
live database migration was performed in this phase.
