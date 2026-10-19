# Bottom-left account menu

The signed-in user's name and email now anchor the bottom of the desktop sidebar.
Click the identity button to open a grouped account menu beside it:

- **Settings** → existing `/account` settings.
- **My Invitations** → `/my-invitations`, where a received private invitation link
  can be opened for inspection and explicit acceptance.
- **My Schedule** → `/my-schedule`, showing deadlines from the user's active review
  assignments, with undated assignments listed separately.
- **Docs** → `/docs`, an original in-app guide to submissions, conference setup,
  reviewing and standalone formatting checks.
- **Sign out** → existing authenticated logout API, including failure/retry.

On the compact desktop rail, the trigger retains its avatar and accessible name.
On mobile, the same menu is available through the header avatar and at the bottom
of the navigation drawer. A drawer menu opens above the account identity.
Duplicate signed-in account/name/sign-out controls were removed from the header.
Existing account and notification navigation remains available.

The menu supports click, Enter, Arrow Up/Down, Home/End, Escape and Tab. Escape
restores trigger focus. In a mobile drawer, Escape closes the account popover
before the outer navigation dialog. Choosing a page closes the popover and drawer.
Outside pointer interaction, route changes and window resize dismiss the popover.
Signing out clears the session only after the existing API succeeds.

## Reference investigation

REA inspected the user's open PaperFox dashboard and performed the declared
account-button click. Directly observed: a bottom-left avatar/name/email trigger
with an ellipsis, a compact bordered flyout to its right, a repeated identity
header, four navigation entries and a separated sign-out action. Entries were
**Settings**, **My Invitations**, **My Schedule**, **Docs**, **Sign Out**. A declared
Settings click was followed by passive inspection confirming navigation to
`/settings/profile`. No profile updates or external data writes were performed.

Relevant REA Evidence IDs:

- Dashboard target discovery: `ev_191f974678e875b976663671d6f002eaeaae0bab344d346531313a1a728f7ef7`.
- Menu click with screenshot and accessibility: `ev_34f7fc06bd9a09f11e34064c4f696c9a240dd804d3dd07b79c4bc07a5cf0314f`.
- Settings destination: `ev_daa0c850795ec2c8823b8fb2750291d434cc79e509a5c45d6dab0c16f1800529`.

The first connected scenario screenshot clipped the bottom of the page; its
accessibility menu was usable, but its pixels were not used for layout judgment.
The follow-up used the observed viewport dimensions and showed the menu. PaperFox
mobile menu behavior was not directly inspected in this slice. The responsive
adaptation is original Paper-Format work, checked in Chromium. Reference captures
include the user's identity and are not copied into the repository.

## Capability boundaries

The current backend has conference-scoped outgoing invitation history plus
token inspection/acceptance; it does not expose a personal pending-invitation
inbox. **My Invitations** therefore opens private links rather than displaying
invented incoming records. It validates same-site `/invitations#token=…` links,
then navigates locally. It does not accept automatically or persist the token.
The existing chair Invitations tab retains outgoing invitation management.

**My Schedule** uses `getReviewerWorkspace()` and its configured review deadlines.
It does not claim conference event scheduling, author calendars or calendar sync.
Failed loads show retry rather than an empty calendar. Overdue and submitted
review states use the real assignment data. Docs is a local product guide, not
an external service's documentation or the backend Swagger page.

No backend, schema, formatting engine, dependency or environment changes were
made. All new controls use existing APIs or local navigation.

## Validation

- `npm run test:shell`: **14 scenarios passed**, including menu destinations,
  keyboard controls, dismissal and sign-out retry, alongside existing shell checks.
- `npm run test:management`: **21 scenarios passed**, including link validation,
  inspection without acceptance, schedule failures/retry and anonymous access.
- `npm run build`: passed. The existing Vite large-chunk advisory remains
  (551.72 kB JavaScript, 157.28 kB gzip).
- Chromium journeys passed at **1440, 1024, 390 and 320 px**. Menu bounds stayed
  inside the viewport; no page-wide overflow, runtime page errors or unexpected
  fixture API requests were observed. Checks include all menu destinations,
  compact rail, header avatar, drawer, keyboard focus and sign-out failure/retry.
- `git diff --check`: passed.

The tests use isolated adapters and intercepted synthetic browser API responses.
They do not change real accounts, invitations or paper data, and do not prove
current live-backend or Google-provider availability. Test fixtures remain in QA
scripts; the app does not substitute synthetic data when an API fails.

The JSDOM management harness now supplies browser `FormData`, preventing Node's
incompatible global constructor from producing a React form-event exception.
Popover screenshots use viewport capture: resizing a long page for a full-page
screenshot can legitimately dismiss a resize-sensitive menu.

## Review

Start the frontend with `npm run dev` in `frontend/`. Sign in, then click your
name at the bottom-left. The separate review preview is available at
`http://127.0.0.1:5174` while running. Check Escape, arrow keys, Tab, outside clicks,
each destination, sidebar collapse and the mobile navigation drawer.

| Capture | Desktop | Mobile |
|---|---|---|
| Account menu | [1440 px](screenshots/account-menu-1440.png) | [390 px](screenshots/account-menu-390.png) |
| Collapsed rail | [1440 px](screenshots/account-menu-collapsed-1440.png) | — |
| Drawer menu | — | [390 px](screenshots/account-menu-drawer-390.png) |
| My invitations | [1440 px](screenshots/my-invitations-1440.png) | [390 px](screenshots/my-invitations-390.png) |
| My schedule | [1440 px](screenshots/my-schedule-1440.png) | [390 px](screenshots/my-schedule-390.png) |
| Docs | [1440 px](screenshots/docs-1440.png) | [390 px](screenshots/docs-390.png) |

All saved application screenshots use synthetic QA accounts and paper records.

To reproduce browser QA using existing browser tooling:

```bash
PAPER_UI_BASE_URL=http://127.0.0.1:5174 \
PAPER_BROWSER_MODULE=/absolute/path/to/playwright-core/index.mjs \
  node docs/ui-reconstruction/account-menu/browser-checks.mjs
```

`PAPER_BROWSER_PATH` overrides `/usr/bin/chromium`. No dependencies are installed.
