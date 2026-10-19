# Paper-Format — Project Progress Update

**Updated:** 19 October 2026  
**Project:** Conference paper submission, formatting validation, collaboration and peer review

## Project objective

Extend the existing research-paper formatting checker into a conference review platform. Papers now have a collaboration workspace inspired by GitHub Pull Requests, while the original parser, formatting engine and standalone checking workflow are retained.

## Functionality implemented

| Area | Progress |
|---|---|
| Paper formatting | Upload PDF, DOCX and LaTeX papers individually or in batches. Parse supported document properties and check them against selected formatting rules. |
| Templates | Import templates, infer and edit rules, save templates, publish conference-specific versions and compare rule changes. |
| Checks and reports | Show compliance scores, failed checks, severity, expected/actual values and correction guidance where available. Display saved reports and revision-specific check history. |
| Conference management | Create conferences; configure descriptions, scope, tracks, submission requirements, allowed formats, page limits, deadlines and review policies. |
| Accounts and roles | Email/password registration and sign-in, account settings, sign-out and conference-specific chair, author and reviewer access. Co-authors can receive separate paper permissions. |
| Conference submissions | Record paper numbers, title, abstract, authors and track. Search/filter accessible papers. The submission form has a separate page from the paper listing. |
| Paper workspace | Overview, Conversation, Document, Formatting Checks, Files and Revisions, Compare Revisions, Reviews and Activity sections, with access to tracked issues. |
| Revision history | Preserve original files and subsequent uploads, revision numbers, upload details, change summaries, file hashes and associated reports. |
| Revision comparison | Compare extracted text, available document properties and formatting findings; identify resolved, new and remaining findings. |
| Document review | Authorized PDF previews, page-linked comments and revision-specific discussion anchors. DOCX/LaTeX files remain downloadable for review. |
| Discussions and issues | Threaded comments, replies, editing/deletion, resolve/reopen actions and tracked formatting issues. Earlier feedback stays attached to its original revision. |
| Formal reviews | Configurable criteria, scores, recommendations, private drafts, submitted reviews, confidential chair comments and controlled release to authors. |
| Reviewer and chair workflow | Assign/revoke reviewers, track review progress, declare/manage conflicts, request revisions and record acceptance/rejection decisions. Lifecycle transitions enforce permissions and configured requirements. |
| Invitations and notifications | Create, inspect, accept, expire and revoke private invitation links. In-app notifications include unread counts, history and read controls. |
| Personal workspace | Dashboard, profile/settings, My Invitations, reviewer deadline schedule, documentation and a bottom-left account menu. |
| Interface redesign | PaperFox-inspired conference pages and forms; GitHub-inspired paper workspace. Shared styling, light/dark themes, mobile layouts and loading/error states. |
| Security and reliability | Backend authorization, cookie sessions, CSRF/origin protection, login throttling, upload validation, private file access, integrity checks and audit history. |
| Development support | React/Vite frontend, FastAPI backend and SQLite persistence, with automated checks and container/CI configuration. |

## Integrations and demonstration

- **Google sign-in/account linking:** implemented; availability depends on OAuth configuration. It is not configured on the currently checked local backend.
- **Google Drive import:** existing integration retained; requires the appropriate Google credentials and permissions.
- **Working demo:** a separate conference with chair, author and reviewer accounts, five sample papers, actual formatting reports, two-version PDF history, discussions and reviews. Papers demonstrate draft, submitted, under review, changes requested and accepted states.

## Validation completed

The redesigned paper workspace passed 75 frontend test scenarios and browser checks at desktop, tablet and mobile widths. The production frontend build passed. Real local demo checks also verified all three account sign-ins, authorized PDF previews, review access and confidential-content filtering. Additional regression checks cover the latest separation of the submission form and paper listing.

## Remaining work

- Continue the detailed UI refinement of Formatting Checks, Issues, revision comparison and review screens.
- Configure and verify external Google services in the target deployment; add production email/invitation delivery if required.
- Complete broader user acceptance testing, deployment preparation and performance/accessibility review.
- Consider optional visual PDF comparison and richer text/bounding-box annotations. Current comparison and page comments do not provide these capabilities.

**Current position:** The core submission-to-review workflow is implemented and demonstrable locally. Further work focuses on interface refinement, external-service configuration and production readiness.
