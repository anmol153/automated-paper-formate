# D2 — Paper workspace: Overview and Conversation

Implemented and refined under the user's approval of the
[GitHub PR + Primer specification](../github-pr-reference/README.md).
The existing PaperFox-inspired application shell, semantic tokens and blue accent
remain consistent with the management pages. These are original components and
adaptations; reference screenshots are not product assets.

## Delivered

- Header: 30 px regular-weight desktop title, muted paper number, prominent actual
  submission status, authoritative current revision, document and upload actions.
- Navigation: four primary PR tabs with original icons and an outlined active
  tab: Conversation, Files and revisions, Formatting checks, Compare revisions.
  Overview, Document, Reviews, Activity and Issues remain as secondary tools.
  Shared `UnderlineNav` supplies active-page semantics and the actual revision count.
  Existing historical revision, report, page and
  comparison query parameters survive section navigation.
- Revision context: selected upload, explicit earlier-version warning and a
  working return-to-current action. Changing revisions clears stale report/page
  selections. Old comment anchors remain on their original revision.
- Overview: current workflow readiness and next responsible role, abstract,
  selected revision summary, permitted workflow actions, collaborators and paper
  metadata. Submission-window and review-phase closure override formatting
  readiness. Workflow actions still target the current revision when reading an
  earlier upload, with existing status/revision concurrency guards.
- Sidebar: 264 px desktop column, permission-filtered authors, selected file and
  formatting status, review access and chair-only assignments. Conference
  navigation remains a link; unavailable names, deadlines and review totals are
  not fabricated. Below 850 px the sidebar follows the main content.
- Conversation is now the default landing page. A paper-description card uses
  permission-filtered declared authors/abstract, followed by a timeline combining
  actual upload snapshots and discussion threads. Equal upload timestamps break
  ties by revision number. No review events or identities are fabricated.
  It has an avatar rail and connector, bordered discussion cards, role/time
  bylines, immutable revision/page links, resolved states and a separate composer.
  All/unresolved/resolved filters use returned data and retain the new-discussion
  draft. Replies, editing, deletion, resolution and reopening retain the existing
  endpoints and permission flags. Replies collapse until opened; replying to a
  comment expands and focuses its editor. Confidential chair drafts clear on role
  loss. Current workflow readiness follows the timeline, with links to checks,
  formal reviews and management. Large management forms stay on Overview.
- The formal-review screen reached from **Reviewer workspace → Open review** uses
  the same PR frame and sidebar. Existing configurable scores, recommendations,
  confidential fields, draft/submission payloads and revision guards are unchanged.
  Conflict declarations use a native disclosure. This is a presentation correction,
  not the deferred deeper revision-comparison/review-history work.
- Responsive styling: flat 8 px panels, 6 px controls, readable 12 px metadata,
  theme tokens and at least 44 px mobile button/control targets. Tabs scroll
  inside their own row. Loading, empty and recoverable errors remain distinct.

The density refinement limits the reading area to 1140 px, combines the discussion
heading and filters, removes duplicate sidebar status, and consolidates actions
for single-comment threads. Detailed readiness information is expandable; the
comment composer uses a shorter editor with options and submit action together.
Formal-review scores use a responsive grid, with explicit visibility hints. Body
text and mobile touch targets remain readable. The shared document-thread actions
and existing review payload/revision guards are retained.

No backend, schema, parser, formatting engine, API-contract or dependency changes.
Document preview, protected downloads, files, detailed checks, activity, formal
reviews and revision-comparison bodies retain their existing behavior. Formatting
compliance, reviewer recommendations and final chair decisions remain separate.

## Screenshot review

Screenshots show the local frontend with **synthetic intercepted API responses**,
not real papers or accounts. Visual review compared the title/sidebar hierarchy,
discussion rail, borders and narrow layouts with the observed
[GitHub header](../github-pr-reference/screenshots/github-header-desktop.png),
[discussion timeline](../github-pr-reference/screenshots/github-review-thread.png),
and [mobile discussion](../github-pr-reference/screenshots/github-mobile-thread.png).
Scroll and focus reset before capture keeps sticky navigation in its proper
position in full-page screenshots.

| View | Desktop | Mobile |
|---|---|---|
| Default paper PR | [1440 px](screenshots/paper-landing-1440.png) | [390 px](screenshots/paper-landing-390.png) |
| Formal-review form | [1440 px](screenshots/review-form-1440.png) | [390 px](screenshots/review-form-390.png) |
| Formal-review dark theme | [1440 px](screenshots/review-form-dark-1440.png) | [390 px](screenshots/review-form-dark-390.png) |
| Overview | [1440 px](screenshots/overview-1440.png) | [390 px](screenshots/overview-390.png) |
| Conversation | [1440 px](screenshots/conversation-1440.png) | [390 px](screenshots/conversation-390.png) |
| Earlier revision | [1440 px](screenshots/historical-1440.png) | [390 px](screenshots/historical-390.png) |
| Chair visibility | [1440 px](screenshots/chair-conversation-1440.png) | [390 px](screenshots/chair-conversation-390.png) |
| Reviewer visibility | [1440 px](screenshots/reviewer-conversation-1440.png) | [390 px](screenshots/reviewer-conversation-390.png) |
| Discussion error | [1440 px](screenshots/conversation-error-1440.png) | [390 px](screenshots/conversation-error-390.png) |
| Dark theme | [1440 px](screenshots/conversation-dark-1440.png) | [390 px](screenshots/conversation-dark-390.png) |
| Preview fallback | [1440 px](screenshots/document-fallback-1440.png) | [390 px](screenshots/document-fallback-390.png) |

Additional Overview and Conversation captures cover
[1024 px](screenshots/conversation-1024.png),
[768 px](screenshots/conversation-768.png) and
[320 px](screenshots/conversation-320.png).

## Validation

- `npm run test:paper`: **20 scenarios passed**, including permissions, actual
  revision counts, historical queries, current-revision guards, closed deadlines
  and review phases, private drafts, thread actions, metadata, filters, retry,
  default conversation, sorted upload events, collapsed replies, and the formal
  review's current-revision guard and draft-save payload.
- `npm run test:document`: **11 scenarios passed**, including protected preview
  lifetime, original page anchors and shared conversation controls.
- **31 isolated scenarios rerun for this correction.** Earlier shell, onboarding
  and management results belong to previous slices and are not added to this count.
- Chromium journeys passed at **1440, 1024, 768, 390 and 320 px**: overflow, metadata
  save, status transitions, threads, filters, immutable anchors, download, upload
  failure/retry with the same idempotency key, new revision selection, existing
  checks/reviews/activity routes, preview fallback, permissions and dark theme.
  Journeys also verify the default landing page, reply disclosure/focus, primary
  versus secondary navigation, configurable formal-review fields, a confirmed
  private draft save, and disabled draft controls on historical revisions.
  The D3 Checks/Issues browser journeys were also rerun at all five widths.
- Production build passed: 165 modules. The existing JavaScript chunk-size
  advisory remains (approximately 583 kB minified). `git diff --check` passed.

All successful test writes above use fixtures. These results validate frontend
rendering/contracts, not live authentication or backend/database integration.
Browser QA exercises a synthetic preview failure; document tests cover preview
behavior without claiming PDF pixel fidelity. Native browser zoom and a full
manual screen-reader audit were not performed.

The optional legacy `test:components` smoke suite was not used for this correction:
it creates real backend accounts, templates, papers and invitations.

## Files and reproduction

This refinement changes `frontend/src/pages/SubmissionDetail.jsx`,
`frontend/src/components/{PaperWorkspace,PaperConversation,FormalReviews,SubmissionWorkflow}.jsx`,
`frontend/src/components/ui/UnderlineNav.jsx`,
`frontend/src/styles/paper-workspace.css`, `frontend/paper-workspace-test.mjs`,
and these review notes, browser checks and screenshots. No unrelated work was
reverted.

Open **Conferences → conference → Papers → paper** with an authorized account.
Inspect Overview and Conversation, select an earlier upload, follow a page
reference, return to current, and try permitted actions. Visible controls depend
on the server's conference role, lifecycle and deadline rules.

Run the three isolated suites and build inside `frontend`. Browser QA requires a
running frontend and the existing Playwright module/Chromium, without installation:

```bash
PAPER_UI_BASE_URL=http://127.0.0.1:5174 \
PAPER_BROWSER_MODULE=/absolute/path/to/playwright-core/index.mjs \
node docs/ui-reconstruction/d2/browser-checks.mjs
```

`PAPER_BROWSER_PATH` can override `/usr/bin/chromium`. The harness intercepts all
API traffic; unexpected endpoints fail QA.

## Next approval gate

D3 is the detailed Formatting Checks and Issues redesign. D4 covers deeper files,
comparison and review interactions. D3 was subsequently approved and is documented
in [its implementation and QA notes](../d3/README.md). D4 requires separate approval.
