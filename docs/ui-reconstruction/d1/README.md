# D1 review — shared tokens and application shell

Implemented under the user's D1 approval. D2 (the paper workspace body) has not
started. This change reorganizes navigation and establishes shared styling while
retaining existing page bodies and all route/API behavior.

## What changed

- Paper-Format's original document mark, a 224 px management sidebar and grouped
  Workspace/Formatting tools navigation. No unfinished Dashboard route is exposed.
- A 56 px desktop breadcrumb header with the existing notification, account and
  theme controls. Paper pages and tablet layouts use a 64 px navigation rail.
- A compact branded mobile header and modal navigation drawer. Native modal
  behavior is supplemented with explicit forward/reverse keyboard focus wrapping,
  Escape/backdrop closing, trigger focus restoration and background scroll locking.
- Separate light/dark semantic tokens and reusable button, status, page-header,
  field, notice and underline-navigation primitives for subsequent page work.
- Existing routes, historical revision/report/page/comparison query parameters,
  invitation fragments and account-keyed remount behavior remain intact.
- Theme-toggle sun visibility is corrected; unavailable browser storage no longer
  breaks initial theme restoration.

No backend, parser, formatting-engine, API-contract, database, configuration or
dependency changes were made. No external messages were sent. Legacy `.panel` and
`.btn-*` page-body styling is deliberately retained for incremental migration; the
new shell's blue and legacy pages' indigo may coexist until those pages are approved.

## Screenshots

These are real REA Chromium captures of the local application's public results
empty state. They contain no private papers or account data. PNG dimensions,
SHA-256 digests and REA Evidence IDs are recorded in [screenshot-manifest.json](screenshot-manifest.json).

| View | Capture |
|---|---|
| Desktop, 1440×1000 | [Desktop shell](screenshots/desktop.png) |
| Mobile, 390×844 | [Mobile shell](screenshots/mobile.png) |
| Mobile navigation, 390×844 | [Open drawer](screenshots/mobile-navigation.png) |
| Tablet dark theme, 1024×768 | [Dark compact rail](screenshots/tablet-dark.png) |

Earlier signed-in screenshots used a disposable backend and a synthetic QA account,
not operator data. Those temporary artifacts expired when the environment restarted;
the final signed-out captures above are saved in the repository to persist.

## Reference comparison and refinements

The observed PaperFox signed-in interface established persistent sidebar navigation,
blue selection, breadcrumb context and restrained surfaces. This shell uses a
narrower 224 px sidebar and smaller 14 px navigation text to reserve more space for
papers. It does not reproduce PaperFox's credits, registrations or hosting requests.
GitHub's separation of global and contextual navigation informs the compact paper
rail; the paper-specific tabs/sidebar are D2 work, not falsely presented here.

Visual review found that an initial mobile header lacked product identity. It now
shows Paper-Format's mark/name and avoids a duplicate sign-in action on the login
page. At 320 px the name collapses to the accessible brand mark so account controls
fit. Auxiliary shell text was increased to 12 px for readability. Real-browser QA
found keyboard escape at the last modal control; explicit focus wrapping corrected
that behavior. The final focus list is filtered for disabled/hidden controls and
ordered by document position across browser/DOM implementations.

The source page content inside the shell remains unchanged: large legacy cards in
the screenshots are not a completed redesign of Results or Login. The reference
products' exact styling/source/assets are not copied.

## Verification

- **12 shell scenarios passed** (`npm run test:shell`): navigation, modal lifecycle,
  focus wrapping, query/fragment preservation, account replacement, sign-out retry,
  theme, field associations and distinct compliance/decision states.
- **Four final Chromium viewport checks passed** at 1440, 1024, 390 and 320 px:
  layout bounds, collapse/drawer behavior, forward/reverse focus cycles, Escape,
  focus return and dark theme. No page-wide horizontal overflow was observed.
- Before the environment restarted, **four signed-in Chromium journeys passed**
  against a disposable real backend, covering login/logout, account controls and
  notification-panel bounds, plus the **existing real-API frontend harness passed**
  across formatting, reports, conferences, revisions, document review and reviews.
- The current production build passed. Vite retains a size advisory for the
  502.67 kB JavaScript chunk (145.19 kB gzip); no bundle-warning suppression or new
  component library was introduced.
- Light/dark semantic text pairs for normal, muted, accent, success, attention and
  danger passed a calculated 4.5:1 contrast threshold. This is not a complete
  accessibility certification of legacy page bodies.
- `git diff --check` passed. All four stored screenshot hashes/dimensions verified.

The environment restart removed the temporary Python virtual environment and
preview server. The live backend is not running on this host at review time;
backend dependencies were not reinstalled for this UI-only change. Current final
checks therefore use the public empty-results screen and isolated API adapters.
The earlier real-API pass is recorded separately rather than claimed as a new run.

## Review it yourself

With the existing frontend dependencies, from `frontend/`:

```bash
npm run dev
npm run test:shell
npm run build
```

Open `http://localhost:5173/results`. This intentionally shows the existing
no-report state without requiring a paper upload. Check desktop navigation collapse,
mobile menu, Tab/Shift+Tab, Escape, theme, skip-to-content and route links. When your
backend is available, sign in normally to review account and notification controls.

The optional [browser-checks.mjs](browser-checks.mjs) reproduces the public-screen
Chromium checks using existing Playwright tooling. It does not install anything:

```bash
PAPER_BROWSER_MODULE=/absolute/path/to/playwright-core/index.mjs \
  node docs/ui-reconstruction/d1/browser-checks.mjs
```

`PAPER_BROWSER_PATH` overrides `/usr/bin/chromium`; `PAPER_UI_BASE_URL` overrides
`http://localhost:5173`. The browser checks create fresh private contexts and only
read the public results route; they do not write application data.

## Files and next approval gate

Changed: `frontend/src/App.jsx`, `frontend/src/index.css`,
`frontend/src/components/ThemeToggle.jsx`, `frontend/package.json`.

Added: `frontend/src/styles/{tokens,workspace}.css`,
`frontend/src/components/layout/{AppShell,AppNavigation}.jsx`,
`frontend/src/components/ui/{Button,StateBadge,PageHeader,UnderlineNav,Field,StateNotice}.jsx`,
`frontend/ui-shell-test.mjs` and these review artifacts. No unrelated changes in the
pre-existing working tree were reverted or committed.

After D1 review, D2 will recompose `SubmissionDetail`, `SubmissionWorkflow`,
`PaperMetadata` and `PaperConversation`, add PaperHeader/PaperSidebar/RevisionToolbar
and update the paper-workspace tests. It will preserve existing actions, permissions
and historical links. D2 requires separate approval under the requested incremental
workflow; conference dashboards and the other page bodies remain later slices.
