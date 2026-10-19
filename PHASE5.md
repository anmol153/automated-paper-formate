# Phase 5: paper revision comparison

This phase adds a Compare revisions tab to the existing paper workspace. It compares
immutable files and saved formatting reports using the current parsing pipeline.
No application dependency, schema migration, processing queue or external service is
introduced. The standalone formatting checker, uploads, review forms and historical
comments retain their existing behavior.

## Using the workspace

Open a paper and choose Compare revisions. The initial base is the selected revision's
parent when available; the target is the selected revision. Both selections can be
changed independently, including comparisons in reverse order or within one revision.
A single-revision paper can compare its saved check attempts without inventing an
earlier file. Legacy papers without revision records show an explanatory empty state.

Select a saved report for each revision, or leave Latest saved report selected. Press
Compare revisions. The response records the exact report IDs that were selected;
the controls and URL then retain those IDs. Later rechecks do not silently replace
the reports in that comparison. Resetting a report selector to Latest saved report
explicitly requests its newest attempt on the next comparison.

Include extracted text changes is optional and initially disabled. Report/property
comparison does not read or parse the original files. Enabling text comparison runs
bounded extraction of both retained files in the existing worker thread pool.

The comparison displays:

- Base and target revision numbers, filenames and exact saved check snapshots.
- Overall formatting status and compliance score for the selected reports.
- Resolved, newly reported, remaining and no-longer-evaluated findings.
- Changes in status, severity, expected/actual values and extraction confidence.
- Existing tracked issue links, without opening or resolving any issue automatically.
- A table of document properties the checker already extracted into those reports.
- Optional added/removed text with context and extracted-text line numbers.

Links from comparison snapshots open the exact saved formatting report. Unknown or
cross-revision report links show an unavailable message with a link to the latest
report, instead of silently displaying another report. Submission tabs now persist
in the URL so these links open the intended section.

Comparison URLs contain revision/check identifiers, not document content or credentials.
Following a URL still requires the existing authenticated paper permissions. Opening a
comparison URL restores its selections; press Compare revisions to load its results.

## Finding semantics

Findings are matched by the checker's stable rule ID within each exact run. Reports
with empty or duplicate rule IDs are explicitly unavailable for matching rather than
being joined by descriptions or list positions.

| Base report | Target report | Comparison |
| --- | --- | --- |
| Failed or missing | Passed | Resolved |
| Failed or missing | Failed or missing | Remaining, with changed fields identified |
| Passed, not applicable, or absent | Failed or missing | Newly reported |
| Failed or missing | Not applicable or absent | No longer evaluated |

No longer evaluated does not count as resolved. Newly reported does not prove the
author introduced an error: a property might only now be measurable. Changing an
issue's manually managed state does not change immutable check results, and the diff
does not change the issue's state. Rechecking the same file can legitimately show
finding changes while its file hash remains identical.

The response warns if template rule snapshots, checker engine versions or document
formats differ. Even an explicit pass under changed conditions needs human
interpretation. A missing check or failed processing attempt makes the corresponding
report comparison unavailable; the system does not fall back to an older success.
An explicitly selected older successful run remains available.

## Extracted properties and confidence

The property table uses saved `PaperAssessment.facts`, rather than reparsing files or
inventing metadata. It includes page count and exactness/confidence, page size,
columns, margins and confidence, body font and size, title and author block, detected
sections/headings, reference and word counts, detected figures/tables and confidence,
acknowledgements, and LaTeX document class where available. Parser names and saved
parse warnings accompany the table.

Absent/null values are unavailable comparisons. They are not substituted with zero
or interpreted as a measured change. Existing parser defaults, empty strings and
heuristic counts remain parser observations; the table is not a verified bibliographic
author list or proof of section/figure absence. Different file formats expose different
properties. The existing confidence fields and manual verification remain important.

## Text comparison and limits

Both private files are checked against their saved size and SHA-256, and the bytes
passed to the parser are checked again. Existing upload-format validation and archive,
byte, PDF object and page bounds apply before normalized-document extraction. No
LaTeX compilation, includes download, embedded script execution or DOCX rendering is
introduced.

The existing `NormalizedDocument.full_text()` supplies reading-order text. CRLF/CR
line endings normalize to LF. A standard-library line comparison displays added and
removed lines with three context lines. File hashes and the text extractor version
remain distinct: a source comment can change the file while its extracted text stays
identical.

Text comparisons currently allow at most 100,000 characters and 1,500 lines per file,
2,000 characters per line, and 100 separate change groups. Exceeding a limit returns
an explicit unavailable/limit message with no partial diff. The current PDF parser
reads at most 60 pages, so PDFs exceeding that limit cannot receive a complete text
comparison even if the upload page limit is higher. Empty/unextractable documents,
missing or corrupted files and parser failures also produce safe messages while saved
report/property comparisons remain available.

Line numbers refer to extracted text, not source lines or PDF pages. Reading order
can be imperfect, particularly for columns. Source commands, comments, complex math,
images, tables and other content may be omitted or rearranged by normalization.
Scanned PDFs have no OCR. Text is extracted with the current parser implementation;
historical parser text is not persisted. Pinning check IDs preserves report evidence,
but does not freeze text extraction across later parser releases.

A text diff does not establish semantic or visual change. This phase does not add
visual PDF comparison, an embedded PDF viewer, text selection or coordinate anchors.
Earlier revision/page discussion anchors remain on their original revisions and are
never moved automatically.

## API and security

`GET /api/v1/submissions/{submission_id}/revision-comparison` accepts:

| Query parameter | Meaning |
| --- | --- |
| `base_revision_id` | Required immutable base revision of this submission |
| `target_revision_id` | Required immutable target revision of this submission |
| `base_run_id` | Optional exact saved check belonging to the base revision |
| `target_run_id` | Optional exact saved check belonging to the target revision |
| `include_text` | Boolean, defaults to false |

The result has `base`, `target`, `same_file`, `formatting`, `properties` and `text`
sections. Each section distinguishes available, unavailable or not-requested evidence.
Text can also report `limit_exceeded`. Revision and report identifiers are length
bounded. Cross-paper revisions and cross-revision check IDs return 404. An unrelated
user is denied before extraction. Read-only coauthors and assigned reviewers receive
the same comparison access as their existing file/report permissions. Reviewer
revocation or membership removal removes that access. Paper access is checked again
after text extraction in case permission changed while it ran.

The existing session and private/no-store API headers apply. Responses do not include
storage keys, filesystem paths, rules JSON, formal reviews or confidential discussion.
Text-comparison attempts use the existing persistent rate limiter at 60 per user per
hour; a throttled text request does not disable report-only comparison. No paper,
revision, check, issue, activity or notification record is created by comparing.
Rate-limit accounting and server-side error logging remain ordinary operational writes.

## Implementation and verification

| File | Responsibility |
| --- | --- |
| `backend/app/services/revision_diff.py` | Saved property/finding matching and bounded integrity-checked text comparison |
| `backend/app/api/revision_routes.py` | Paper authorization, exact snapshot selection, throttling and comparison endpoint |
| `frontend/src/components/RevisionComparison.jsx` | Revision/report selectors, comparison summaries, properties and text changes |
| `frontend/src/pages/SubmissionDetail.jsx` | Comparison tab and exact saved-report navigation |
| `backend/tests/test_phase5_revision_diff.py` | Comparison evidence, permissions, immutability, limits and compatibility tests |
| `frontend/component-test.mjs` | Real API/DOM comparisons, text hunks and report-link regressions |

Focused verification passed 28 cases, including schema-4 compatibility, real LaTeX,
PDF and DOCX extraction, reverse/same-revision comparisons, source-only changes,
immutable run selection, failure handling, cross-paper access, revocation, throttling
and property/finding confidence semantics. Full backend regression: **282 passed,
8 skipped**; the skips are the existing absent external Springer fixtures. The
production frontend build, complete real-API UI harness and whitespace checks passed.
All checks used isolated temporary data, including separate review participants.

## Activation and remaining work

Phase 5 works on the existing revision schema and needs only the updated backend and
frontend processes. It introduces no migration. The subsequent approved Google-auth
activation now selects `platform-v7.db` and retains the original `platform-v4.db`.

Formal reviews and conference intake were explicitly activated together with Google
authentication; see `GOOGLE_AUTH.md`. Phase 5 added no schema migration. No production deployment
was performed. Native-parser process isolation/timeouts, durable processing jobs,
cached/persisted text snapshots, richer figure/reference matching, visual comparisons,
an embedded annotation viewer and operational retention/pagination remain future work.
