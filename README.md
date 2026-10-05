# Paper Format Compliance System

Check research papers against a venue's formatting rules before review, in batch.

There are two workflows:

- **Authors** (`/submit`) — submit one paper or a whole batch, by uploading files or
  linking a Google Drive folder. Every paper is reported separately with the specific
  things to fix. One unparseable file never blocks the rest of the batch.
- **Conference managers** (`/setup`) — upload the venue's template, let the rules be
  inferred from it, override any of them, and save the result. Authors are then
  checked against those rules.

Papers and templates may be PDF, LaTeX (`.tex`) or Word (`.docx`) in any combination.

```text
paper.pdf   rejected   4 blocking issues   Page size, Margins, Columns, Anonymised submission required
paper.tex   rejected   5 blocking issues   File type accepted, Abstract, Keywords, ...
README.md   rejected   'README.md' is not a recognised format. Supported formats: .pdf, .latex, .docx
```

See [EVALUATION.md](EVALUATION.md) for measured agreement between this system and manual
checking, the bugs that evaluation uncovered, and the known limitations.

## Architecture

```text
React (Vite + Tailwind)
  ├── /setup     manager: import template → RuleEditor → save as RuleSet
  ├── /submit    author: MultiDropZone (many files) or Drive folder link
  └── /results   per-paper verdict, blocking reasons, full check list
        │
        ▼
FastAPI  ──► Parser (PDF / LaTeX / DOCX) → NormalizedDocument
        │         └── content sniffing, so a mislabelled file still parses
        ▼
        PaperFacts  (layout, typography, structure, assets, identity, per-format detail)
        │
        ▼
        Rule engine ──► CheckResult[]  (passed / failed / missing / not_applicable)
        │                  + severity, expected vs actual, evidence, advice, confidence
        ▼
        PaperAssessment → SubmissionReport (verdict + score per paper)
```

- `backend/app/parsing/pdf_parser.py` — PDF bytes → normalized JSON: page size, margins,
  orientation, column detection, font families/sizes, bold/italic flags, alignment inference,
  line-spacing/indent estimation. Formatting comes from the PDF text model; regex is used only
  to classify blocks (title/authors/abstract/keywords/headings).
- `backend/app/parsing/latex_parser.py` — LaTeX source → the same `NormalizedDocument`:
  geometry/documentclass options, font-family packages, `\textbf`/`\textit`, relative size
  commands, alignment environments, `\linespread`, `\parindent`, and structural macros
  (`\title`, `\author`, `\begin{abstract}`, `\begin{keywords}`, `\section`...).
- `backend/app/parsing/docx_parser.py` — Word `.docx` (OOXML, stdlib `zipfile` + ElementTree)
  → the same model: `sectPr` page setup, styles/direct formatting, alignment, spacing and indents.
- `backend/app/parsing/fact_extractor.py` — `build_facts()`: everything the rules need,
  including identity detection (author blocks, emails, affiliations, acknowledgements,
  funding, ORCID, self-citation, document metadata).
- `backend/app/models/rules.py` — `RuleSet`: the configurable publisher template. Every rule
  field is optional, and `None` means "this publisher does not care", which the engine
  reports as `not_applicable` rather than as a failure.
- `backend/app/checks/engine.py` — evaluates a `RuleSet` against `PaperFacts`; produces one
  `CheckResult` per rule with severity, evidence, remediation advice and confidence.
- `backend/app/checks/anonymisation.py` — double-blind checks.
- `backend/app/checks/submission.py` — `assess_paper()` / `assess_batch()`; a bad file becomes a
  rejected assessment with an explanation rather than an exception.
- `backend/app/parsing/rule_inference.py` — infers a `RuleSet` from an uploaded template, plus
  the rule schema and starter presets.
- `backend/app/storage/template_store.py` — SQLite-backed template persistence. A rule set is a
  nested config document, so it is stored as JSON in one column, with `name`, `created_at` and
  `updated_at` beside it for listing and ordering. Runs in WAL mode with a busy timeout, so
  concurrent reads don't block the writer and competing writers wait rather than erroring.
- `backend/app/google/drive_client.py` — Drive folder listing and download, with Google Docs
  export. Degrades to a clear `503` when no credentials are configured.
- `backend/app/evaluation/` — labelled non-compliant corpus and the runner that measures
  detection rate and verdict agreement against it.
- The engine knows nothing about the input format: every parser emits the same
  `NormalizedDocument`, so a template and a paper may be uploaded in different formats.

## Sample files

Ready-to-upload example documents (one journal-style template + one conference-style paper in
each supported format):

| Format | Template | Paper |
| ------ | -------- | ----- |
| PDF    | `samples/template.pdf` | `samples/paper.pdf` |
| LaTeX  | `samples/template.tex` | `samples/paper.tex` |
| DOCX   | `samples/template.docx` | `samples/paper.docx` |

## Quick start

### Backend

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

Endpoints:

| Method | Path                       | Input / output |
| ------ | -------------------------- | -------------- |
| GET    | `/api/v1/health`           | liveness and which parsers are available |
| GET    | `/api/v1/rule-schema`      | the `RuleSet` schema, for building an editor without hardcoding it |
| POST   | `/api/v1/parse`            | multipart `file` → normalized JSON |
| POST   | `/api/v1/compare`          | multipart `template` + `paper`, or `demo=true` → single compliance report |
| GET    | `/api/v1/templates`        | saved templates |
| POST   | `/api/v1/templates/import` | multipart `file` (+ optional `name`) → inferred `RuleSet`, **not persisted** |
| POST   | `/api/v1/templates`        | JSON `RuleSet` → saved template |
| GET    | `/api/v1/templates/{id}`   | one template |
| PUT    | `/api/v1/templates/{id}`   | JSON `RuleSet` → replaces a template |
| DELETE | `/api/v1/templates/{id}`   | deletes a template |
| POST   | `/api/v1/submissions`      | multipart `files` (repeat per paper) + `template_id` or inline `rules` JSON → `SubmissionReport` |
| POST   | `/api/v1/submissions/drive`| `{folder_url, template_id, recursive}` → `SubmissionReport` |
| GET    | `/api/v1/drive/status`     | whether Drive credentials are configured, and how to set them up |
| POST   | `/api/v1/drive/preview`    | `{folder_url, recursive}` → what a folder contains before checking |

`files` must be repeated once per paper in the multipart body, which is what a browser's
`FormData.append("files", file)` per file produces.

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

- `/setup` — import a template, edit the inferred rules, save.
- `/submit` — pick the venue template, then add papers by drop, browse or paste, or paste a
  Drive folder link. Multi-file submission is one request, not one per paper.
- `/compare` — the original two-document template-vs-paper comparison.
- `/results` — one card per paper: verdict, blocking reasons with remediation advice, and the
  full check list including checks that did not apply.

## Google Drive

Optional. Without credentials, uploads work fully and the Drive tab explains what is missing.
To enable it, provide either:

- `backend/credentials/service_account.json` with Drive **read-only** scope, or
- a `GOOGLE_API_KEY` in the environment,

then share the target folder with the service account address. Check
`GET /api/v1/drive/status` to confirm. Google Docs are exported to PDF; other Google-native
formats are skipped and listed by `/drive/preview`.

## Deploy to Vercel (Docker)

A single `Dockerfile.vercel` at the repo root packages both backend and frontend into one
container: the frontend is built with Node, the backend deps are installed into a Python venv,
and the FastAPI server serves `/api/*` plus the built SPA (static assets + `index.html` fallback).

Vercel auto-detects `Dockerfile.vercel`, builds the image, stores it in Vercel Container
Registry, and routes all traffic to it as a Vercel Function. The server listens on `$PORT`
(defaults to 80).

Deploy by pushing to a Vercel-connected Git repository, or from the CLI:

```bash
vercel deploy        # uses ./Dockerfile.vercel automatically
```

Run the same image locally:

```bash
docker build -f Dockerfile.vercel -t paper-format .
docker run --rm -p 8000:80 paper-format
# → http://localhost:8000  (full app + API on one port)
```

Notes:
- Documents are uploaded per-request and processed in memory, so no document storage is needed.
  **Publisher templates are the exception**: they are persisted to a SQLite file, which the
  container's ephemeral filesystem will not keep between invocations. Set `TEMPLATE_DB_PATH` to a
  mounted volume (or point it at a networked database via a driver change) before running this on
  Vercel, or every redeploy and every scale-from-zero loses the configured venues.
- Vercel scales container functions to zero after ~5 min idle (30 s in preview), so the first
  request after idle pays a cold-start cost.
- No `vercel.json` or framework detection is required; the container serves everything.

## Notes & limitations

- Text-based PDFs only; scanned/image-only PDFs are rejected with a clear error.
- Margins are estimated from content extents in PDFs (headers/footers can skew them). LaTeX and
  DOCX margins come from the document setup (`geometry` / `sectPr`).
- PDF column detection uses a midline-crossing heuristic tuned for classic two-column layouts;
  LaTeX/DOCX columns are read from `twocolumn` / `multicols` / `w:cols`.
- **Page counts are exact only for PDFs.** LaTeX and DOCX are not paginated until rendered, so
  the count is an estimate and `page.limit` is enforced against it with
  `pages.estimate_tolerance_pages` of slack. `page_count_exact` is reported so the UI can say so.
- Content sniffing overrides a misleading extension, but only on strong signals (`%PDF-`, the
  `PK` zip header, `\documentclass`, `\begin{document}`). Prose *about* LaTeX is not a manuscript.
- Severity is assigned per rule, not per venue: typography, reference count and abstract length
  are warnings; anonymisation and structure are blocking. A venue that wants a wrong font to be
  fatal sets `decision.reject_if_any_warning = true` rather than a per-rule toggle.
- An unparseable file short-circuits to a rejected assessment, so it reports "not a recognised
  format" rather than the more specific "this template accepts .pdf, .tex, .docx".
- Template storage is a single SQLite file, `backend/data/templates.db` by default. Override
  the location with `TEMPLATE_DB_PATH` to put it on a mounted volume — **required** on a
  platform with an ephemeral filesystem such as Vercel, where the default path is wiped
  between invocations. Note that SQLite in WAL mode keeps recent commits in a `-wal` sidecar
  next to the database, so a backup or volume snapshot must include `templates.db`, `-wal`
  and `-shm` together; copying only `templates.db` can lose the last writes. Multiple
  app instances need a shared database (Postgres, or a single-writer SQLite volume) since
  each instance otherwise has its own file.
- Not implemented: auto-fix, per-rule severity overrides beyond the decision rule, LLM assistance.

## Tests

```bash
.venv/bin/pytest backend/tests -q
```

Includes the evaluation corpus invariants (`test_evaluation_corpus.py`), which assert that the
compliant baseline stays clean, that every planted flaw is detected, and that over-reporting does
not grow beyond the two documented metadata fields.

### Frontend

```bash
# start the backend first: it is what the component test asserts against
cd backend && ../.venv/bin/python -m uvicorn app.main:app --port 8000 --app-dir backend &

cd frontend
npm run test:components   # mounts every page in a DOM against real API responses
npm run build             # production bundle
```

`test:components` defaults to `localhost:8000`; override with `API_BASE`:

```bash
API_BASE=http://localhost:8010/api/v1 npm run test:components
```

`test:components` builds a real batch report by uploading the sample files to
`/api/v1/submissions`, then asserts that each filename, blocking reason, remediation
advice and the checks disclosure actually reach the DOM — so a report-shaped rendering
bug fails the test rather than shipping.

### Evaluation

```bash
cd backend && ../.venv/bin/python -m app.evaluation.runner
```

Runs the labelled corpus through the same `assess_paper()` the API uses, reports detection rate
and verdict agreement, and exits non-zero if agreement drops below 100% or the clean baseline
reports anything — so it can be wired into CI. Results and findings: [EVALUATION.md](EVALUATION.md).
```
