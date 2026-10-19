# Formatting workspace redesign

The existing formatting tools now share the PaperFox-inspired management style:
compact page headings, local navigation, restrained panels, blue controls,
consistent fields, readable findings and responsive layouts. The parser, checker,
database and API contracts are unchanged. No dependencies were installed.

## Updated pages

| Route | Changes |
|---|---|
| `/submit` | Template/method/upload form with conference chooser and format guidance alongside. Local uploads, batch checks and the existing Drive controls remain. |
| `/compare` | Parallel template/manuscript upload panels, existing compare/demo actions and progress. |
| `/setup` | Wider rule editor, compact import/library panels and a narrower quick-reference column. Import, load, save, update and delete handlers are retained. |
| `/results` | Shared navigation and report framing, clearer paper/finding cards, normal score orientation and a consistent empty state. |
| `/reports` | Search by paper/author/template, filter by stored verdict, keyboard-accessible report opening and explicit deletion with confirmation. Failures retain useful rows and expose retry. |
| `/conferences/:confId/latest` | Published template history uses management typography, surfaces and controls, retaining member/chair permissions. |
| `/conferences/:confId/diff?old=…&new=…` | Rule-group cards show Before/After values from the existing structured diff. Added/removed/changed fields and the full JSON remain available, with error/retry and no-change states. |

The shared `FormattingWorkspace.jsx` provides headings and navigation, and
`formatting.css` scopes the styling. Existing upload and rule-editor components
remain in use. `PaperCard` also carries the new report styling when reused in
paper review. Existing check categories, expected/actual values, blocking issues,
advice and confidence information remain available.

Stored `accepted`/`needs_review`/`rejected` formatting verdicts keep their API
values; the formatting UI labels them **Passed**, **Needs review** and **Blocking
issues**. These are not conference decisions. Explicit labels supplied by the
submission review workflow remain supported. No new automated checks are claimed.

Reports now use real buttons rather than clickable generic containers. Search and
filter operate on the loaded, authorized report index. Deletion retains the
existing confirmation and API, and a failed request does not remove a row.
Opening retrieves the report before navigating with the existing location state.

Template comparison rendering follows the actual `diff_rulesets` groups and
`changed`, `added`, `removed`, `unchanged` structure in the backend. It does not
infer semantic paper changes or replace the diff engine. Request cleanup prevents
an older response from overwriting a newly selected comparison.

## Verification

- Production build passed; the existing Vite large-chunk advisory remains.
- 14 shell scenarios passed, including the existing no-report route and deep links.
- 13 onboarding scenarios passed, including immutable conference template history,
  permissions, import failures, publication and unlocking uploads.
- 11 invitation scenarios passed for the accompanying sign-in changes.
- 22 management scenarios passed for the accompanying sign-in and existing pages.
- Formatting browser journeys passed at **1440, 1024, 390 and 320 px**, exercising
  uploads, comparison, findings, template import/load/save, conference template
  history/comparison, report search/filter, keyboard opening, delete failure/retry,
  load retry and dark theme. No runtime page errors, unexpected fixture APIs or
  page-wide horizontal overflow were observed.
- `git diff --check` passed.

Tests intercept all API requests with synthetic data, including uploaded documents,
template writes and deletion. They verify UI/API wiring without changing real
papers, rules or reports; they do not prove parser output or live server availability.
Backend parser tests were not rerun for these frontend-only changes.

The browser checks wait for initial authentication to settle before selecting
files: the existing workspace remounts when account identity changes. This security
behavior is retained. Google Drive's unavailable state is tested; live Drive
credentials and provider behavior are not exercised.

Reproduce with existing browser tooling, without installing dependencies:

```bash
PAPER_UI_BASE_URL=http://127.0.0.1:5174 \
PAPER_BROWSER_MODULE=/absolute/path/to/playwright-core/index.mjs \
  node docs/ui-reconstruction/formatting/browser-checks.mjs
```

## Review screenshots

Start the frontend with `npm run dev` in `frontend/`. The usual URL is
`http://localhost:5173`; the separate review preview is at
`http://127.0.0.1:5174` while running. Real operations need the existing backend.
All stored screenshots use synthetic data.

| View | Desktop | Mobile |
|---|---|---|
| Check papers | [1440 px](screenshots/check-papers-1440.png) | [390 px](screenshots/check-papers-390.png) |
| Drive unavailable | [1440 px](screenshots/drive-unavailable-1440.png) | [390 px](screenshots/drive-unavailable-390.png) |
| Compare documents | [1440 px](screenshots/compare-documents-1440.png) | [390 px](screenshots/compare-documents-390.png) |
| Batch results | [1440 px](screenshots/batch-results-1440.png) | [390 px](screenshots/batch-results-390.png) |
| Detailed findings | [1440 px](screenshots/formatting-findings-1440.png) | [390 px](screenshots/formatting-findings-390.png) |
| Single result | [1440 px](screenshots/single-result-1440.png) | [390 px](screenshots/single-result-390.png) |
| Template setup | [1440 px](screenshots/template-setup-1440.png) | [390 px](screenshots/template-setup-390.png) |
| Saved reports | [1440 px](screenshots/saved-reports-1440.png) | [390 px](screenshots/saved-reports-390.png) |
| Reports, dark | [1440 px](screenshots/saved-reports-dark-1440.png) | [390 px](screenshots/saved-reports-dark-390.png) |
| Empty report state | [1440 px](screenshots/no-report-1440.png) | [390 px](screenshots/no-report-390.png) |
| Conference template history | [1440 px](screenshots/conference-templates-1440.png) | [390 px](screenshots/conference-templates-390.png) |
| Template comparison | [1440 px](screenshots/template-comparison-1440.png) | [390 px](screenshots/template-comparison-390.png) |

The [sign-in review](../login/README.md) records the redesigned authentication page.
