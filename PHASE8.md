# Phase 8: document-centered review

This phase adds a Document tab to the existing paper workspace. It combines a
protected PDF preview with the existing revision/page-anchored discussion model.
It uses the current React application, native browser PDF viewer, private revision
storage and threaded collaboration APIs. No application dependencies, schema changes,
live database migrations or external document services were introduced.

## Document workspace

Open a submission and choose **Document**, or follow:

```
/submissions/{id}?tab=document&revision={revision_id}&page=2
```

The selected immutable revision supplies the filename, file and comments. Historical
revisions have a clear earlier-version notice. The page selector controls both the
PDF's requested page and the page discussion beside it. The PDF file is fetched once
per mounted viewer, not again for every page change. The browser's PDF plugin may
scroll independently: scrolling inside it does not update the comment page selection.
The UI explicitly explains this limitation.

The response contains an exact page count measured from the validated PDF. Saved
formatting-report layout facts can also supply an exact limit while the preview is
loading. Estimated DOCX/LaTeX page counts do not become exact bounds. Invalid or
out-of-range page links show an error and disable posting; they are never silently
clamped to another page. New revision selections clear the previous page query.

Preview uses a local browser blob URL with `application/pdf`, not a public file URL
or an external viewer. Leaving the Document tab, changing revision, changing chair
capability, or signing out unmounts the viewer and revokes its blob URL. A pending
preview fetch is aborted and late responses are ignored. Browser PDF support and
page-fragment handling vary, so the original authorized download remains available.

DOCX/LaTeX files and PDFs over 25 MB use the download fallback. There is no office
conversion, LaTeX compilation, OCR, raster renderer or visual diff in this phase.
The viewer does not upload the paper to Google or another third-party service.

## Revision- and page-linked discussion

The sidebar filters the existing authorized conversation response to threads on
the exact selected revision and page. It reuses the same reply, edit, deletion,
resolution, identity-redaction, notification and optimistic-concurrency behavior as
the Conversation tab. No second annotation store or duplicate issue engine exists.
General and revision-only threads remain in Conversation, available through the
sidebar's link to all permitted discussions.

Posting explicitly sends `revision_id` and `page_number`. Separate page drafts are
held in component memory while the user remains in that Document tab. Switching pages
does not move a draft to another page. Leaving the tab/revision or changing chair
capability discards its unsent drafts. There is no draft autosave or browser-storage
persistence. Posted threads stay on their original revision after another upload.

Existing conversation revision links now open the original Document tab/page.
**Copy page link** creates a stable workspace link with a manual-copy fallback;
it contains no session credential and grants no access to its recipient.

Confidential chair posting uses the existing backend paper-level chair capability,
including chair recusal. Workspace loading now fetches that capability directly,
so links to Document or Conversation work without first visiting Overview. A failed
capability lookup defaults to no confidential-posting controls. Backend authorization
continues to govern all reads and writes. A private draft is never silently converted
to participant-visible content when the chair capability changes.

Formatting findings still do not carry reliable page coordinates in the current
report model. No location, selected-text anchor, highlight or bounding box is inferred
or invented from a finding. Those remain later work.

## Protected preview API

New endpoint:

```
GET /api/v1/submissions/{submission_id}/revisions/{revision_id}/preview
```

The endpoint:

1. Authenticates and checks the current submission read permission.
2. Resolves the revision within that submission, rejecting cross-paper revision IDs.
3. Applies a per-account limit of 60 preview requests per hour.
4. Rejects files above 25 MB, verifies the private file's size/hash, and performs a
   bounded read. It verifies the hash of the bytes actually read as well.
5. Reuses document validation and the configured PDF page/object/resource limits.
   Non-PDF content is rejected. A conservative scan of MuPDF's parsed objects also
   rejects nested/escaped JavaScript and Launch action names, including actions in
   retained files that may predate upload validation. Some interactive PDFs may need
   download instead of inline preview. This is validation, not PDF sanitization.
6. Checks submission access again after validation, preventing a reviewer whose
   assignment was revoked during processing from receiving the bytes.
7. Audits `revision.previewed` with the exact revision and returns an inline
   `application/pdf` response, `Cache-Control: private, no-store`, `nosniff`, and
   `X-Paper-Page-Count`.

The existing download endpoint retains its original attachment behavior and all
file/revision/report snapshots remain immutable. Preview validation runs in the
existing thread pool without a new queue or persisted render files. It does not
change formatting scores or formal reviews. Original paper author identities inside
the PDF are not anonymized; this phase does not implement double-blind documents.
Previously delivered/downloaded bytes cannot be remotely erased, and this phase
does not introduce real-time access revocation or a parser isolation service.

## Manual check

1. Use separate chair, author and reviewer browser profiles. Complete the Phase 7
   conference/template/member setup and upload a PDF, such as `samples/paper.pdf`.
2. Open its Document tab. Confirm the filename/revision, preview and measured page
   count. Enter a page with Comment page before writing feedback.
3. Post a page comment, reply, edit it and resolve its thread. Confirm the same
   discussion appears in Conversation and its revision link returns to this page.
4. For a multi-page PDF, type a draft on page 1, change to page 2, and return to
   page 1. The draft remains on page 1. Posting must retain that page/revision.
5. Copy the page link and open it as another authorized participant. An unrelated
   account must fail to load the submission; the link does not grant access.
6. As an unconflicted chair, post a confidential page thread. Authors and assigned
   reviewers must not see it or its posting control. Direct Document links should
   offer the chair control without first opening Overview.
7. Upload a later revision using the existing revision-request workflow. Open an
   older comment link: it must show the old revision and original page. Selecting a
   new revision resets the selected page instead of relocating old feedback.
8. Try a page above the measured PDF count: posting and the misleading preview
   are disabled. Try a DOCX/LaTeX source: download/discussion is offered without
   claiming that it was rendered to PDF. A large PDF offers the size fallback.

Restart the backend for the new endpoint, then refresh the frontend. There is no
database activation step.

## Verification

- **36 backend checks passed** across Phase 8, collaboration and Phase 7 onboarding.
  They cover unauthenticated/unrelated access, assigned/revoked reviewer access,
  private response headers, exact bytes/page counts, old files and page anchors,
  confidential threads, cross-paper revision IDs, non-PDF/oversized/integrity failures,
  rate limiting, revocation during validation, and direct/inline/escaped PDF actions.
- **11 document UI scenarios passed** using an isolated API adapter: page/draft
  separation, exact anchor payloads, sidebar filtering, invalid links, source/size
  fallback, JSON blob errors/retry, aborting old loads, preventing private-draft
  disclosure, copy fallback, edit/reply/resolve actions and blob cleanup.
- The expanded **real-API component harness passed**, including authenticated PDF
  loading, direct-link chair capabilities, author confidentiality, historical source
  anchors and existing formatting/review/revision/onboarding regressions. The backend
  and files used a temporary directory and the server shut down afterward.
- Production frontend build and whitespace checks passed. The UI harness uses
  JSDOM; actual browser PDF pixels, plugin behavior and accessibility inside the
  native viewer still require the manual browser checks above.

Commands from the repository root, with the existing backend environment active:

```bash
COOKIE_SECURE=true GOOGLE_OAUTH_CLIENT_ID= PYTHONPATH=backend python -m pytest \
  backend/tests/test_phase8_document_review.py backend/tests/test_phase3_collaboration.py \
  backend/tests/test_phase7_onboarding.py -q
```

Frontend checks:

```bash
cd frontend
npm run test:document
npm run build
# Point this at an isolated disposable backend, not production:
API_BASE=http://127.0.0.1:8017/api/v1 npm run test:components
```
