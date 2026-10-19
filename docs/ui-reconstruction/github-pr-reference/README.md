# GitHub PR + Primer — Paper-Format design specification

**Reference investigation: 19 October 2026 · D2 specification approved by the user.**

REA inspected the two user-selected tabs through `http://127.0.0.1:9222`, one at a
time: the public VS Code GitHub repository and Primer. The GitHub investigation
went beyond the listing into individual PRs, checks, review history and diffs.
Only documentation and reference artifacts were added during this investigation.
Existing D2 code was left intact during investigation. The user's subsequent
approval authorized the refinement documented in
[the D2 implementation and QA notes](../d2/README.md). D1 remains independent.

## 1. GitHub: directly observed

Primary reference: [VS Code PR #342518](https://github.com/microsoft/vscode/pull/342518).
Additional public PRs provided [approval history](https://github.com/microsoft/vscode/pull/342496)
and [change requests](https://github.com/microsoft/vscode/pull/342101).

| Area | REA observation | Screenshot |
|---|---|---|
| Header | Large title and muted number; Draft/Open badge; author; source/target branches; branch-copy action. A compact header remains visible after scrolling. | [Header](screenshots/github-header-desktop.png), [scrolled header](screenshots/github-review-thread.png) |
| Tabs | Conversation, Commits, Checks and Files changed are contextual links with counts and an outlined active state. They remain separate from repository navigation. | [Commits](screenshots/github-commits.png) |
| Conversation | An avatar rail and vertical connector link bordered comment cards with smaller commit/review events. Bylines distinguish people, bots, roles, timestamps and edited content. | [Timeline](screenshots/github-review-thread.png) |
| Sidebar | Reviewers and approval requirement; assignee; labels; projects; milestone; related development and participants. Several sections explicitly show no assigned value. | [Metadata sidebar](screenshots/github-header-desktop.png) |
| Checks | Commit scope, grouped expandable suites, an initially empty detail panel and distinct in-progress, passed, failed and skipped indicators. REA expanded Code OSS and opened a failed job. Full logs require sign-in. | [Expanded suite](screenshots/github-check-suite-open.png), [failed job](screenshots/github-failed-check-detail.png) |
| Reviews | Human approval events are distinct from a bot's recommendation text. History retains dismissed stale approvals and links to reviewed changes. A human “requested changes” event was verified in the accessibility tree of #342101. | [Approval history](screenshots/github-approved-pr.png), [history context](screenshots/github-review-history.png) |
| Files changed | Searchable file tree, collapsible files, change counts, original/new line gutters, colored additions/removals, hunk controls and embedded review conversations. | [Unified diff](screenshots/github-files-changed.png) |
| Diff controls | Commit-scope selector, file/conversation filters and a settings popover. Unified/Split and whitespace options are visible; split view was loaded after applying its setting. | [Settings](screenshots/github-diff-settings.png), [split diff](screenshots/github-split-diff-loaded.png) |
| Narrow view | A valid 390 CSS-pixel capture shows wrapped discussion text and stacked event content; code hunks retain horizontal scrolling. The sticky title truncates rather than consuming the full page. | [Mobile discussion](screenshots/github-mobile-thread.png) |

**Observation limits:** these were signed-out public views. Posting comments,
submitting reviews, changing assignments, resolving a thread as an authorized
participant and merging were not tested. Review forms must not be described as
observed. The exact change-request event is supported by accessibility evidence;
the linked screenshot shows surrounding history, not that event itself. Counts
and check states are snapshots of live pages, not fixed product requirements.

## 2. Primer: directly observed documentation and examples

The selected [Primer homepage](https://primer.style/) separates Product UI from
Brand UI. Product UI is the relevant application reference; the homepage's large
marketing cards are not a paper-workspace layout.

| Inspected guidance | Observed pattern | Screenshot |
|---|---|---|
| Product UI | Grouped guidance for components, primitives and interaction patterns; breadcrumb context and a collapsible navigation control. | [Product UI](screenshots/primer-product-ui.png) |
| Color | Semantic foreground/background/border roles and theme-specific values. The light table includes accent `#0969da`, text `#1f2328`, attention `#9a6700` and danger `#d1242f`. | [Color](screenshots/primer-color.png) |
| Typography and size | Named sans-serif/monospace families, typography roles and reusable size tokens. These are documented values, not measurements of every GitHub screen. | [Typography](screenshots/primer-typography-loaded.png), [size](screenshots/primer-size.png) |
| UnderlineNav | Links switch related views; active navigation is visually stronger. Examples include counters and leading icons. | [Navigation](screenshots/primer-underline-navigation.png) |
| Button and FormControl | Primary/default/quiet/danger priorities; size variants; labels above fields; required indicators; caption and validation examples. Documentation examples do not establish backend validation behavior. | [Buttons](screenshots/primer-buttons.png), [fields](screenshots/primer-form-controls.png) |
| Responsive guidance | Adapt layout and interaction to viewport, input method, zoom and user preferences. A minimum supported viewport of 320 px is documented. | [Responsive](screenshots/primer-responsive-guidance.png) |
| Loading and empty states | Scoped progress feedback; determinate progress only when meaningful; empty/error explanations with an appropriate next action. | [Loading](screenshots/primer-loading.png), [empty states](screenshots/primer-empty-states.png) |
| Narrow documentation | Text and examples reflow into a narrow column; the header retains a navigation button. | [390 px view](screenshots/primer-mobile-pattern.png) |

## 3. Proposed Paper-Format adaptation — original design

The following choices are proposals, not features observed on either reference.

| GitHub concept | Paper-Format treatment |
|---|---|
| PR and branch header | Paper title/number, submission status, conference/track, current revision and selected historical revision. Use conference/template context instead of research “branches.” |
| Conversation | Paper discussion with author/reviewer/chair labels, revision/page references and confidential-chair visibility where authorized. |
| Commits | Immutable paper revisions with uploader, timestamp, change summary, file integrity and saved reports. |
| Checks | Formatting runs and supported findings, with expected/actual values, severity and reliable document locations. No invented checks or progress percentages. |
| Files changed | Manuscript text/property/finding comparison with explicit base/target revisions and report runs. Text changes do not prove semantic or visual equivalence. |
| Reviewers | Assigned academic reviewers and permission-filtered progress. Never expose hidden identities or confidential content. |
| Approval | Formal reviewer recommendation remains separate from the chair's final editorial decision. A formatting pass is neither of these. |

**Paper layout:** retain the PaperFox-inspired application shell. Within the paper
workspace use a title/status header, contextual navigation, a revision toolbar and
a broad content column with a 264–280 px metadata sidebar. Overview should state
readiness, the next responsible role, available actions and important dates only
when returned by existing APIs. Conversation should separate ordinary threads,
formal-review events and automated findings. Keep Document and its protected
preview available as a document-centered review tool.

**Proposed tokens:** reuse existing `--pf-*` semantic tokens and the Paper-Format
blue accent `#245edb`. Use system sans-serif, monospace only for identifiers/diffs,
28 px titles, 16 px section headings, 14 px body and 12 px metadata. Use 4/8/12/16/
24/32 px spacing, 1 px borders, 6 px controls and 8 px panels. Keep ordinary panels
flat; reserve shadows for overlays. These dimensions are original implementation
targets, not copied or claimed GitHub measurements.

**Interactions and accessibility:** use real links for URL-addressable sections,
`aria-current` for the current page, explicit labels, visible focus and semantic
status text/icons. Keep one primary action per action group. Disable duplicate
submissions while saving and retain drafts after errors. Distinguish “no content,”
“loading,” “failed to load” and “not authorized.” A check may be passed, warning,
failed, processing or unable to validate; skipped/unmeasured is not passed.

**Responsive proposal:** stack the sidebar below content at approximately 850 px;
at small widths wrap actions and allow contextual tabs and code diffs to scroll
within their own regions. Preserve readable prose and at least 44 px mobile action
hit areas. Verify 1440, 1024, 768, 390 and 320 px, light/dark themes, keyboard use
and zoom. These breakpoints are Paper-Format choices; exact GitHub breakpoints and
the mobile sidebar's final placement were not measured.

## 4. Implementation sequence after approval

1. Review the existing D2 frame against this evidence. Reuse `AppShell`,
   `UnderlineNav`, `Button`, `Field`, `StateBadge` and existing tokens.
2. Refine only the paper header, revision context, Overview, Conversation and
   metadata sidebar. Primary files: `frontend/src/pages/SubmissionDetail.jsx`,
   `frontend/src/components/{PaperWorkspace,PaperConversation,SubmissionWorkflow,PaperMetadata}.jsx`
   and `frontend/src/styles/paper-workspace.css`.
3. Preserve existing submission/revision/workflow/metadata APIs, conversation
   permission flags, private preview/download authorization and all historical
   query parameters. Current workflow actions must never target an older selected
   revision accidentally. Do not relocate earlier annotations to a new upload.
4. Test author/reviewer/chair visibility, revision links, thread actions, failure
   recovery, keyboard behavior and responsive screenshots against this specification.
5. Seek separate approval for deeper Checks/Issues and revision-comparison/review
   redesigns. Visual PDF diff and reliable cross-revision text anchors remain
   optional future capabilities, not requirements for D2.

No new component library, backend change, schema change or formatting-engine
replacement is proposed. If progress counts, dates or actions are unavailable from
the existing API, omit them or identify the dependency; never simulate success.

## Evidence and approval

[Evidence manifest](evidence-manifest.json) records public URLs, REA Evidence IDs,
image hashes, capture dimensions and limitations. Screenshots are unedited. Failed
selector attempts and clipped viewport experiments are not design evidence.

**D2 and D3 approved and implemented.** See the [D3 review](../d3/README.md) for
Formatting Checks and Issues. Deeper comparison/review redesigns require separate
approval.
