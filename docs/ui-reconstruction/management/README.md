# Home, dashboard and conference management

This slice implements the user's expanded request for PaperFox-inspired internal
pages, home and dashboard. It supersedes the earlier sequence that put paper detail
before conference management. Backend code, contracts, parser, formatting engine,
database, environment settings and dependencies were not changed.

## Try it

Start the existing frontend with `npm run dev` from `frontend/`. If an older dev
server shows incomplete styles, restart that server and reload the page. The
temporary review preview uses `http://127.0.0.1:5174` while it remains running.
Normal development remains on `http://localhost:5173`.

1. Open `/` for the new home page, then choose **Open dashboard** (signed in) or
   **Get started**. Both email and Google sign-in now lead to `/dashboard`.
2. Open `/conferences`, search by name/description, and choose **Create conference**.
3. Enter the name and description. A successful API response opens the new
   conference workspace with a **Continue setup** action. Failures keep the inputs.
4. In **Settings**, save the conference identity, configure dates and requirements,
   and create tracks. Existing version checks and local-time-to-UTC conversion
   remain in use. The existing scheduling feature flag still applies.
5. In **Templates**, use the existing template editor/import/library to publish
   formatting rules. A conference cannot accept paper uploads without a template.
6. In **People**, chairs can add participants by account ID and remove members.
   The **Invitations** tab now provides creation/revocation and link history.
   Share links yourself; the app does not send
   invitation email automatically. Author views omit these controls.
7. In **Reviews**, configure formatting gates, review criteria, deadlines and
   visibility; the existing chair progress component is retained.
8. Choose **View papers** or **Submit a paper**. The paper list now links back to
   the workspace, shows status badges and keeps the existing submission form.
   Legacy conference configuration remains accessible in a disclosure on that
   page so old links and workflows continue to work.

Creating a conference grants chair membership in the backend. Creating it does not
automatically publish a template, open submissions or send invitations. The
directory remains public; private conference access is checked by existing APIs.

The dashboard's first count is the **public conference directory**, not “my
conferences”: the listing API deliberately omits membership. Its review counts
come from the signed-in user's review workspace. Failed requests display unavailable
counts rather than fabricated zeroes, and a failed review feed does not hide the
working directory.

## Routes and compatibility

| Route | Result |
|---|---|
| `/`, `/home` | New home page |
| `/dashboard` | Signed-in overview and quick actions |
| `/conferences` | Searchable conference directory |
| `/conferences/new` | Dedicated creation form |
| `/conferences/:confId` | Overview and configuration workspace |
| `?tab=settings`, `templates`, `people`, `reviews` | Bookmarkable conference sections |
| `/conferences/:confId/submissions` | Existing submission workflow with updated framing |
| `/submit` | Existing standalone checker |
| `/compare`, `/results`, `/reports`, `/setup` | Existing formatting tools |

The root route intentionally becomes Home as requested. Its previous standalone
checker remains at its existing `/submit` alias. Historical submission, report,
revision, template comparison and invitation deep links are retained.

## Reference fidelity and limits

Directly observed PaperFox patterns from the earlier investigation: persistent
sidebar, blue navigation selection, contextual breadcrumb, three dashboard summary
cards, restrained panels and form layouts with explanatory content alongside.
These informed this slice's 224 px navigation, compact typographic scale, three
honest data summaries, searchable directory rows and two-column creation/settings.
The earlier account had no populated conference; those internal pages could not be
directly inspected. Their grouping and interactions here are original design
decisions based on the working Paper-Format APIs, not claimed reproductions of
unseen PaperFox screens. No proprietary assets, logos or source were copied.

Visual QA refined the field labels to separate accessible names from hints,
removed whole-card hover underlines, adjusted mobile stacking and confirmed all
tabs/forms fit without page-wide horizontal overflow. New styles are scoped to
`.pf-management` so unrelated legacy page bodies retain their existing styles.
Paper detail, reviewer-workspace body and report-body redesigns remain separate work.

## Validation

- `npm run test:management`: **11 scenarios passed**, including successful login,
  directory failure/retry, search, anonymous creation guard, failed creation with
  input retention, successful creation/navigation, identity save errors, settings
  version/date payloads, author/chair controls, membership writes and dashboard
  partial failures.
- `npm run test:shell`: **12 scenarios passed**. The navigation assertion now
  expects the implemented dashboard; conference copy matches the new directory.
- `npm run test:onboarding`: **13 scenarios passed**, including template history,
  publishing, import errors and unlocking uploads after template publication.
- `npm run build`: passed, with the existing Vite large-chunk advisory
  (523.10 kB JavaScript, 150.65 kB gzip).
- Real Chromium journeys passed at **1440, 1024, 390 and 320 px**, visiting home,
  dashboard, directory, creation failure/retry, all conference tabs and papers,
  including the missing-template upload gate and dark mode. No runtime page errors
  or page-wide horizontal overflow were observed.
- `git diff --check`: passed.

These runs use isolated Axios adapters or browser request interception. They do not
prove current live backend availability, end-to-end persistence, Google provider
availability or email delivery. Browser fixtures are only in the QA script; the
application never substitutes fixtures or returns fake success in production.
No backend tests or migrations were run for this frontend-only slice.

To reproduce browser QA using an existing Playwright installation:

```bash
PAPER_UI_BASE_URL=http://127.0.0.1:5174 \
PAPER_BROWSER_MODULE=/absolute/path/to/playwright-core/index.mjs \
  node docs/ui-reconstruction/management/browser-checks.mjs
```

The script uses `/usr/bin/chromium` unless `PAPER_BROWSER_PATH` is set. It installs
nothing and intercepts all `/api/v1/` requests before they reach a backend.

## Screenshots

All conference data and accounts in these captures are synthetic QA fixtures.

| Page | Desktop | Mobile |
|---|---|---|
| Home | [1440 px](screenshots/home-1440.png) | [390 px](screenshots/home-390.png) |
| Dashboard | [1440 px](screenshots/dashboard-1440.png) | [390 px](screenshots/dashboard-390.png) |
| Conference directory | [1440 px](screenshots/conferences-1440.png) | [390 px](screenshots/conferences-390.png) |
| Creation | [1440 px](screenshots/create-conference-1440.png) | [390 px](screenshots/create-conference-390.png) |
| Conference overview | [1440 px](screenshots/conference-workspace-1440.png) | [390 px](screenshots/conference-workspace-390.png) |
| Settings | [1440 px](screenshots/conference-settings-1440.png) | [390 px](screenshots/conference-settings-390.png) |
| People | [1440 px](screenshots/conference-people-1440.png) | [390 px](screenshots/conference-people-390.png) |
| Templates | [1440 px](screenshots/conference-templates-1440.png) | [390 px](screenshots/conference-templates-390.png) |
| Reviews | [1440 px](screenshots/conference-reviews-1440.png) | [390 px](screenshots/conference-reviews-390.png) |
| Papers | [1440 px](screenshots/conference-papers-1440.png) | [390 px](screenshots/conference-papers-390.png) |
| Papers, dark | [1440 px](screenshots/conference-papers-dark-1440.png) | [390 px](screenshots/conference-papers-dark-390.png) |

## Source changes

New pages: `Landing.jsx`, `Dashboard.jsx`, `CreateConference.jsx`,
`ConferenceDetail.jsx`. Rebuilt directory: `Conferences.jsx`. Extracted membership
controls: `ConferencePeople.jsx`. Reused settings component gains an optional
expanded state, defaulting to the original collapsed behavior. `ConferencePapers.jsx`
adds workspace navigation and contains its configuration inside a disclosure.
`management.css` is imported after existing global styles in `main.jsx`.
`App.jsx` and shell navigation register the new routes. `Login.jsx` and
`GoogleSignIn.jsx` change only their default post-authentication destination;
callback and account-link flows retain their behavior. `management-test.mjs`, the
new package test command and the browser script provide repeatable verification.
