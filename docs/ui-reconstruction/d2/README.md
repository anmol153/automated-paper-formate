# D2 — Paper workspace: Overview and Conversation

Implemented under the user's D2 approval. This slice changes the existing React
paper workspace; it preserves the backend, parser, formatting engine, API contracts,
private-file download path, and revision/report data. No dependencies were installed.

## Design and reference alignment

The previously observed references and their evidence are summarized in
[D1](../d1/README.md) and [the account-menu investigation](../account-menu/README.md).
D2 adapts GitHub's title/status header, contextual underline navigation, broad
conversation column, narrow metadata sidebar, restrained borders, and comment
bylines. PaperFox's existing Paper-Format shell, blue action color, form controls,
and light/dark semantic tokens remain consistent with the management pages.
No new observation of either external site was needed for this approved slice;
these are design adaptations, not claims of pixel equivalence or copied assets.

- The header exposes paper number, stable identifier, actual submission status,
  current revision, and working document/revision actions.
- Overview separates current workflow readiness from the selected revision's
  summary. Abstract and authors use the permission-filtered submission response.
  Deadline closure overrides a formatting-ready message. Next responsibility is
  described by lifecycle role; permitted actions still come from the server.
- The 264 px desktop sidebar shows conference navigation, authors, selected file,
  upload time, formatting state, review access, and chair-only assignments.
  Below 850 px it moves after the main content. Tabs scroll within their own row.
- Conversation has explicit thread boundaries, author/role/time bylines, original
  revision/page links, resolved states, a separate composer, and confidential
  chair visibility. Editing, replies, deletion, resolution and reopening retain
  their original APIs and permission flags. A private draft clears if chair access
  disappears. Loading, empty, and recoverable error states are distinct.
- Metadata editing is available through an accessible native disclosure. Workflow,
  reviewer assignment, collaborators, metadata history, and concurrency checks
  remain functional. The detailed checks, document viewer, formal reviews, revision
  comparison, files, and activity bodies retain their existing behavior.

Correctness fixes found during this work: the current revision header follows the
server pointer rather than array order; the next upload label uses the maximum
revision number; successful uploads atomically select the returned revision and
Checks tab; switching revisions clears stale page/run selections while retaining
other comparison parameters. Ordinary section links preserve all query context.

## Screenshots and visual review

These screenshots show the real local frontend with **synthetic intercepted API
responses**. They contain no private papers or actual conference accounts.

| View | Desktop | Mobile |
|---|---|---|
| Overview | [1440 px](screenshots/overview-1440.png) | [390 px](screenshots/overview-390.png) |
| Conversation | [1440 px](screenshots/conversation-1440.png) | [390 px](screenshots/conversation-390.png) |
| Earlier revision | [1440 px](screenshots/historical-1440.png) | [390 px](screenshots/historical-390.png) |
| Chair visibility | [1440 px](screenshots/chair-conversation-1440.png) | [390 px](screenshots/chair-conversation-390.png) |
| Reviewer visibility | [1440 px](screenshots/reviewer-conversation-1440.png) | [390 px](screenshots/reviewer-conversation-390.png) |
| Recoverable discussion error | [1440 px](screenshots/conversation-error-1440.png) | [390 px](screenshots/conversation-error-390.png) |
| Dark theme | [1440 px](screenshots/conversation-dark-1440.png) | [390 px](screenshots/conversation-dark-390.png) |
| Protected preview fallback | [1440 px](screenshots/document-fallback-1440.png) | [390 px](screenshots/document-fallback-390.png) |

Visual inspection compared the composition with the reference observations:
status and contextual navigation precede the work area; sidebar information uses
compact separators rather than oversized dashboard cards; comments use a muted
thread header and readable body. Refinements added explicit current-workflow
context, reduced metadata-editor clutter, kept the desktop revision label on one
line, and corrected the resulting mobile selector overflow by stacking its label
and control. Mobile retains the same actions and moves metadata below discussions.

## Validation

- `npm run test:paper`: **15 scenarios passed**, covering permission-sensitive
  controls, current/historical revisions, query preservation, current-revision
  workflow guards, closed deadlines, confidential drafts, thread operations,
  metadata edits, errors/retry, and unavailable/legacy revision states.
- Existing regression suites: **11 document**, **13 onboarding**, **14 shell**,
  and **22 management** scenarios passed; **75 frontend scenarios total**.
- Chromium journeys at **1440, 1024, 390 and 320 px** check rendered layouts and
  overflow; metadata save; status transition; resolve/reopen/post; immutable page
  anchors; download; failed/successful upload with the same idempotency key; new
  revision/Checks navigation; review/activity routes; protected-preview fallback;
  chair/reviewer visibility; discussion retry; and dark theme.
- Production build passes. The existing >500 kB JavaScript chunk advisory remains.
  `git diff --check` passes.

All automated write operations above use test fixtures. This validates frontend
contracts and rendering, not a live Google sign-in or backend/database integration
run. Existing document tests cover protected PDF blob lifetime; synthetic browser
QA intentionally exercises preview failure rather than claiming PDF pixel fidelity.

## Changed files and reproduction

Changed: `frontend/src/pages/SubmissionDetail.jsx`,
`frontend/src/components/{SubmissionWorkflow,PaperMetadata,PaperConversation}.jsx`,
`frontend/src/main.jsx`, and `frontend/package.json` (test script only).

Added: `frontend/src/components/PaperWorkspace.jsx`,
`frontend/src/styles/paper-workspace.css`, `frontend/paper-workspace-test.mjs`,
and this review directory. No unrelated working-tree changes were reverted.

With the frontend running, open an authorized paper through
**Conferences → conference → Papers → paper**. Switch between Overview and
Conversation; select an earlier revision, follow a page reference, return to the
current revision, and inspect Files and revisions. Actual allowed controls depend
on your backend account, conference role, deadline and lifecycle state.

Run `npm run test:paper` inside `frontend`. To reproduce browser QA using the
already available Playwright module and Chromium, without installing anything:

```bash
PAPER_UI_BASE_URL=http://127.0.0.1:5174 \
PAPER_BROWSER_MODULE=/absolute/path/to/playwright-core/index.mjs \
node docs/ui-reconstruction/d2/browser-checks.mjs
```

Optional `PAPER_BROWSER_PATH` overrides `/usr/bin/chromium`. The script intercepts
all API requests in private browser contexts; unexpected endpoints fail QA.

## Next approval gate

D3 is the detailed Formatting Checks and Issues redesign. D4 covers deeper files,
comparison and review interactions. Those page bodies have not been rebuilt in
D2. No invented progress counts, reviewer identities, deadlines, visual diffs,
notifications, or fake successful backend operations were added.
