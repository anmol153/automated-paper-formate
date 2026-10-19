# Settings, invitations and collaboration pages

This slice implements the requested PaperFox-inspired settings and invitation
pages, plus notifications and the reviewer workspace. It reuses Paper-Format's
existing APIs, authentication, conference permissions and formatting workflow.
There are no backend, database, environment or dependency changes.

## Find the pages

- **Personal settings**: choose **Settings** in the sidebar, or open `/account`
  or `/settings`. Sections cover profile, conference access, connected accounts
  and appearance. Account details are displayed from the existing identity API;
  no unsupported profile-edit, email-change or password-change controls are shown.
  Account ID copying retains its manual fallback. Appearance uses the existing
  browser theme preference. Google linking retains its existing confirmation flow.
- **Conference settings**: open a conference and choose **Settings**. Event
  details, submission schedule, metadata requirements and tracks are grouped into
  separate sections. Existing optimistic version checks, local-time-to-UTC
  conversion, scheduling capability flag and archived read-only rules remain.
- **Conference invitations**: chairs now have a dedicated **Invitations** tab,
  available at `/conferences/:confId?tab=invitations`. People retains account-ID
  membership management and links to this tab. Other roles cannot load invitation
  management through a direct tab URL. The existing backend still enforces access.
- **Invitation acceptance**: existing `/invitations#token=…` links keep their
  behavior in a new layout. Guest sign-in/account creation stays in the invitation
  flow. Inspection never accepts automatically. Successful explicit acceptance
  removes the token from the URL and does not store it in navigation state.
- **Notifications**: `/notifications` has an inbox-style list, unread filter,
  server unread count, refresh, read actions, pagination and meaningful empty states.
- **Reviewer workspace**: `/reviewer` has searchable assignments, review-progress
  filtering, status badges and direct links into the existing paper review tab.
  Conflict declaration and withdrawal retain their original APIs and privacy rules.
  A failed assignment load now provides a working refresh action.

Start the frontend with `npm run dev` from `frontend/`. The ordinary dev URL is
`http://localhost:5173`; the separate review preview uses
`http://127.0.0.1:5174` while it remains running. An available backend and signed-in
account are needed for real conference operations. The app never substitutes
synthetic data when an API is unavailable.

## Try the invitation workflow

1. Sign in as a conference chair and open **Invitations**.
2. Enter a recipient email, select Author or Reviewer, and choose the expiry.
3. Create the link, copy it and share it privately. No email is sent automatically.
4. Check its history row. Search filters only the records already loaded; older
   records remain available through the existing pagination control.
5. Open the link with the intended recipient account. Confirm the conference and
   role, then explicitly accept. The resulting page links to conference papers.
6. Revoke a pending link from history when needed. Revoking a newly created link
   also removes its displayed secret. Raw links cannot be recovered from history.

Membership and reviewer assignments remain separate. Accepting an invitation does
not bypass submission deadlines, change an existing role or assign a paper.
Withdrawing a reviewer conflict does not automatically restore an assignment.

## Design evidence and implementation

The earlier PaperFox investigation directly established sidebar navigation, blue
selection, breadcrumb context, restrained surfaces and forms with explanatory
content alongside. This slice adapts those observed patterns to the real
Paper-Format controls. Populated PaperFox conference settings and invitation pages
were unavailable during that investigation; the section structure and invitation
history here are original decisions, not claimed copies of unobserved screens.
No proprietary source, logos or assets are used.

`Account.jsx`, `Invitation.jsx`, `Notifications.jsx` and `ReviewerWorkspace.jsx`
now use shared management surfaces and existing Field/Button primitives.
`ConferenceSettings.jsx` and `ConferenceInvitations.jsx` retain their persistence
handlers with updated sections, labels and status displays. `ConferenceDetail.jsx`
registers the invitation tab; `ConferencePeople.jsx` can retain the embedded manager
for older callers but uses the dedicated tab in the current workspace.
`collaboration.css` is imported after the existing styles in `main.jsx`.

Desktop form columns stack on mobile. Invitation history rows reflow into cards;
conference tabs scroll locally, without widening the page. Read-only and unavailable
states retain their meaning. Profile and appearance have a section menu, linked
headings and visible keyboard focus. Automated screenshots were visually reviewed
for card spacing, form alignment, status hierarchy and mobile layouts.

## Verification

| Check | Result |
|---|---|
| `npm run test:management` | 17 scenarios passed |
| `npm run test:invitations` | 11 scenarios passed |
| `npm run test:notifications` | 12 scenarios passed |
| `npm run test:onboarding` | 13 scenarios passed |
| `npm run test:shell` | 12 scenarios passed |
| `npm run build` | Passed; existing Vite large-chunk advisory remains |
| Chromium journeys | Passed at 1440, 1024, 390 and 320 px |
| `git diff --check` | Passed |

Browser journeys exercised settings save and track creation; invitation failures,
retry, copy and revocation; chair/author access; invalid, unavailable, guest,
pending and accepted invitation states; unread filtering and read mutation; and
reviewer filtering, conflict declaration and withdrawal. No runtime page errors,
unhandled fixture API requests or page-wide horizontal overflow were observed.

These checks use isolated Axios adapters or intercepted browser API requests.
They do not establish current live-backend availability, production persistence,
Google provider availability or email delivery. The production app still calls
the existing APIs. Tests did not create real conferences, invitations or reviews.
No backend tests or migrations were needed for these frontend-only changes.

To reproduce visual QA with an existing browser tool installation:

```bash
PAPER_UI_BASE_URL=http://127.0.0.1:5174 \
PAPER_BROWSER_MODULE=/absolute/path/to/playwright-core/index.mjs \
  node docs/ui-reconstruction/settings/browser-checks.mjs
```

`PAPER_BROWSER_PATH` overrides `/usr/bin/chromium`. The script installs nothing;
every API request is intercepted before reaching a backend.

## Screenshots

All accounts, invitations and paper details in these captures are synthetic.

| Page or state | Desktop | Mobile |
|---|---|---|
| Account settings | [1440 px](screenshots/account-settings-1440.png) | [390 px](screenshots/account-settings-390.png) |
| Account settings, dark | [1440 px](screenshots/account-settings-dark-1440.png) | [390 px](screenshots/account-settings-dark-390.png) |
| Conference settings | [1440 px](screenshots/conference-settings-1440.png) | [390 px](screenshots/conference-settings-390.png) |
| Conference invitations | [1440 px](screenshots/conference-invitations-1440.png) | [390 px](screenshots/conference-invitations-390.png) |
| Invitation created | [1440 px](screenshots/invitation-created-1440.png) | [390 px](screenshots/invitation-created-390.png) |
| Invitation acceptance | [1440 px](screenshots/invitation-accept-1440.png) | [390 px](screenshots/invitation-accept-390.png) |
| Invitation accepted | [1440 px](screenshots/invitation-accepted-1440.png) | [390 px](screenshots/invitation-accepted-390.png) |
| Invalid link | [1440 px](screenshots/invitation-invalid-1440.png) | [390 px](screenshots/invitation-invalid-390.png) |
| Unavailable invitation | [1440 px](screenshots/invitation-unavailable-1440.png) | [390 px](screenshots/invitation-unavailable-390.png) |
| Invitation sign-in | [1440 px](screenshots/invitation-sign-in-1440.png) | [390 px](screenshots/invitation-sign-in-390.png) |
| Notifications | [1440 px](screenshots/notifications-1440.png) | [390 px](screenshots/notifications-390.png) |
| Reviewer workspace | [1440 px](screenshots/reviewer-workspace-1440.png) | [390 px](screenshots/reviewer-workspace-390.png) |
| Reviewer conflict | [1440 px](screenshots/reviewer-conflict-1440.png) | [390 px](screenshots/reviewer-conflict-390.png) |
