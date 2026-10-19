# D3 — Formatting Checks and Issues

Implemented under the user's D3 approval, following the previously approved
[GitHub PR + Primer reference specification](../github-pr-reference/README.md).
This slice changes the frontend only. Backend routes, database/schema, parser,
formatting engine, immutable files and saved report contracts are preserved.
No libraries were added or installed.

## Delivered behavior

**Formatting Checks** stays inside the paper workspace and follows the selected
revision. A saved-run selector exposes retained history; an exact unavailable run
has its own state rather than falling back to another result. Run status, timestamp,
pinned template and available engine version appear above expandable category
groups. Search and status filters operate on the saved results. Details show the
existing expected/actual values, severity, confidence, rule ID, evidence and advice.
Legacy document and policy categories remain visible alongside modern categories.

Passed, failed, missing and not-evaluated counts come from individual saved
results. Not evaluated means disabled or unmeasurable, not passed; the UI explains
its exclusion from the compliance score. Unable-to-validate runs keep their error
and do not borrow an older assessment. The existing detailed `PaperCard` report
remains available under an explicit disclosure. Rechecking uses the existing
selected-revision endpoint, disables duplicate requests and shows processing
without an invented percentage. It creates no new review or decision capability.

Each finding links to its existing tracked issue when the report supplies the
rule-to-issue relationship. The report-level issue link filters by **both original
revision and run**, without creating duplicate issues. Findings do not currently
provide structured page/bounding-box anchors; this UI does not guess locations
from evidence text.

**Issues** retains `/issues/:submissionId` and adds shareable `?issue=…` detail
links. The list provides search, severity/status filters, real counts and optional
revision/run scope. Issue detail shows expected/actual values, correction advice,
evidence, discussion, status, timestamps and resolution metadata returned by the
server. An original-report link includes its immutable revision and run. Resolving
an issue never changes the saved formatting result.

Comments now use the existing **separate comments endpoint**: the former UI
incorrectly expected them inside an issue response. Successful posts append the
confirmed comment response, avoiding a second POST if a later read fails. Failed
posts retain drafts. Saving status shows the confirmed server result; rejected
changes keep the draft and error, with no fake success. Late issue responses
cannot replace a newly selected issue, and an issue from another paper is not
rendered inside the current workspace.

Assignment controls use the existing workflow's `is_chair` flag and are hidden
when that permission is unavailable. Status updates retain the existing backend
authorization: paper editors or active assigned reviewers may update them. The
issue response has no granular `can_update` flag, so the UI does not claim a status
change is authorized before the server confirms it. Denial remains explicit and
recoverable. Clearing an assignment is unsupported by the existing PATCH contract;
the UI explains that limitation instead of reporting a fake unassignment.

Manual issue creation, arbitrary annotation anchors, full issue-resolution
history and new reviewer-identity visibility are not invented. These require
additional backend capabilities or separately approved work.

## Visual review

The adaptation follows the observed GitHub
[check grouping](../github-pr-reference/screenshots/github-check-suite-open.png)
and [failed check details](../github-pr-reference/screenshots/github-failed-check-detail.png),
using the existing Paper-Format shell, blue action color and light/dark tokens.
The single-column expandable groups adapt the reference to paper requirements;
they do not copy GitHub's build-log layout or imply access to CI logs.

Visual review checked dense status rows, 1 px borders, category hierarchy,
expected/actual alignment, readable wrapped evidence and stacked mobile controls.
It caught a 36 px select at the 768 px boundary; controls and action links now meet
44 px mobile targets. No page-wide overflow was observed in the final runs.

All screenshots use **synthetic intercepted API data**, not real papers/accounts.

| View | Desktop | Mobile |
|---|---|---|
| Formatting checks | [1440 px](screenshots/checks-1440.png) | [390 px](screenshots/checks-390.png) |
| Issues | [1440 px](screenshots/issues-1440.png) | [390 px](screenshots/issues-390.png) |
| Issue detail | [1440 px](screenshots/issue-detail-1440.png) | [390 px](screenshots/issue-detail-390.png) |
| Chair assignment | [1440 px](screenshots/chair-issue-1440.png) | [390 px](screenshots/chair-issue-390.png) |
| Empty filtered list | [1440 px](screenshots/issues-filter-empty-1440.png) | [390 px](screenshots/issues-filter-empty-390.png) |
| Unable to validate | [1440 px](screenshots/unable-to-validate-1440.png) | [390 px](screenshots/unable-to-validate-390.png) |
| Report-loading error | [1440 px](screenshots/checks-load-error-1440.png) | [390 px](screenshots/checks-load-error-390.png) |
| Dark checks | [1440 px](screenshots/checks-dark-1440.png) | [390 px](screenshots/checks-dark-390.png) |

Additional main-page captures cover 1024, 768 and 320 px in this screenshot folder.

## Validation

- `npm run test:checks`: **15 isolated scenarios passed**: category coverage,
  saved-result counts, filters, unavailable runs, immutable origins, separate
  comments, confirmed status/assignment writes, denied changes, retained drafts,
  retries, stale responses, cross-paper URLs and permission-load failure.
- Existing `npm run test:paper`: **18 scenarios passed**.
- Existing `npm run test:document`: **11 scenarios passed**.
- **44 isolated frontend scenarios total.** No live database writes or sign-ins.
- Chromium journeys cover **1440, 1024, 768, 390 and 320 px**: check expansion,
  keyboard disclosures and issue links, filters, saved-run selection, immutable
  origins, comment retry, permission-denied status changes, chair assignment,
  recheck scope/processing, unavailable runs, report-read retry, dark theme and
  mobile targets. Unexpected API requests and runtime page errors fail the harness.
- Production build passed: 165 modules, approximately 579 kB minified JavaScript.
  The existing >500 kB chunk advisory remains. `git diff --check` passed.

The first isolated D3 run passed assertions but Vite reported a sandbox socket
restriction; the suite was rerun outside the sandbox without that error. The
first mobile browser pass caught the select sizing defect described above; the
corrected complete runs passed. Tests verify frontend behavior/contracts, not live
parser correctness, provider authentication or actual PDF visual fidelity. Native
browser zoom and a full manual screen-reader audit were not performed.

## Files and reproduction

Added `frontend/src/components/PaperChecks.jsx`,
`frontend/src/styles/paper-checks.css`, `frontend/checks-issues-test.mjs`, and this
review directory. Updated `SubmissionDetail.jsx`, `Issues.jsx`, the existing API
client (a wrapper for `GET /issues/:id/comments`), stylesheet import and package
test script. Previous D2 working-tree changes were preserved.

Open **Conferences → conference → Papers → paper → Formatting checks**. Expand a
finding, select an earlier run and follow a tracked issue. In Issues, use search
and filters, add a comment and try permitted status/assignment changes. Actual
visibility and successful mutations depend on backend account and conference rules.

Run the three isolated suites and `npm run build` from `frontend`. With the
frontend running, reproduce screenshot QA using existing tooling:

```bash
PAPER_UI_BASE_URL=http://127.0.0.1:5174 \
PAPER_BROWSER_MODULE=/absolute/path/to/playwright-core/index.mjs \
node docs/ui-reconstruction/d3/browser-checks.mjs
```

`PAPER_BROWSER_PATH` optionally overrides `/usr/bin/chromium`. Every API request is
intercepted in private browser contexts.

## Next approval gate

D4 covers the deeper Files/Revisions, revision comparison and formal-review UI.
Those redesigns have not started and require separate approval.
