# Paper Format Compliance System

Upload a **PDF template** and a **PDF research paper**; the backend parses both into a shared
normalized JSON representation, extracts the template's formatting rules, and returns a
compliance report: what matches, what differs, which required sections are missing.

```text
Overall Compliance: 82%
✓ 32 requirements matched   ✗ 6 formatting issues   ⚠ 2 required elements missing
```

## Architecture

```text
React (Vite + Tailwind) ──► FastAPI ──► PyMuPDF parser (PDF → NormalizedDocument)
                                │
                          Template Analyzer (rules extraction)
                                │
                          Comparison Engine (document / typography /
                                            paragraph / structure)
                                ▼
                       Compliance Report JSON
```

- `backend/app/parsing/pdf_parser.py` — PDF bytes → normalized JSON: page size, margins,
  orientation, column detection, font families/sizes, bold/italic flags, alignment inference,
  line-spacing/indent estimation. Formatting comes from the PDF text model; regex is used only
  to classify blocks (title/authors/abstract/keywords/headings).
- `backend/app/parsing/structure.py` + `template_analyzer.py` — block classification and rule
  extraction, shared by every parser.
- `backend/app/comparator/` — independent check modules producing passed/failed/missing results.
- The comparison engine knows nothing about PDFs: Google Docs / DOCX / LaTeX parsers can be
  added later by emitting the same `NormalizedDocument` (`app/google/` holds an earlier
  Docs-API client kept for that purpose).

## Quick start

### Backend

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

Endpoints:

| Method | Path              | Input                                                        |
| ------ | ----------------- | ------------------------------------------------------------ |
| GET    | `/api/v1/health`  | —                                                            |
| POST   | `/api/v1/parse`   | multipart `file` (PDF) → normalized JSON                     |
| POST   | `/api/v1/compare` | multipart `template` + `paper` PDFs, or form field `demo=true` |

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

Drop two PDFs and hit Compare, or click **Try demo data** to see the pipeline run on built-in
sample documents without any files.

## Notes & limitations (V1)

- Text-based PDFs only; scanned/image-only PDFs are rejected with a clear error.
- Margins are estimated from content extents (headers/footers can skew them).
- Column detection uses a midline-crossing heuristic tuned for classic two-column layouts.
- Alignment (justified/left/right/center), line spacing and first-line indents are inferred
  from line geometry, so both documents are measured with the same yardstick.
- Score = passed / total × 100 (missing counts against the score).
- Not yet implemented: DOCX/LaTeX input, auto-fix, multiple templates, LLM assistance.

## Tests

```bash
.venv/bin/pytest backend/tests -q
```
