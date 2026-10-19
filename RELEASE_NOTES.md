# Paper-Format Release Notes – Phase 3 Implementation

## Summary
This release completes the Phase 3 work, building on the Phase 2 foundation that established conferences, templates, submissions, reviews, and discussion threads.

## New Features

### 1. Diff Engine for Template Version Comparison
- **`backend/app/utils/diff_engine.py`** – Computes structured diffs between two `RuleSet` versions, highlighting changes at the top-level and nested rule-group level (file_type, pages, sections, anonymisation, typography, paragraph, decision, publisher).
- **`backend/app/api/template_routes.py`** – Added `POST /api/v1/conferences/diff` endpoint that accepts two template IDs and returns a diff payload with a human-readable summary.
- The diff is fully typed and includes per-group comparison functions (`diff_file_type`, `diff_pages`, `diff_sections`, etc.) and a `summary_diff` helper for UI tooltips.

### 2. Notification System Hardening – Email Snowflake Pattern
- **`backend/app/services/email.py`** – New email delivery service that logs notifications to `data/email_logs/email-YYYY-MM-DD.log` when an email address is present on the notification. Designed to integrate with SMTP/transactional services (SendGrid, Postmark) downstream.
- **`backend/app/storage/notification_store.py`** – `NotificationStore.create()` now calls `send_email()` after inserting a notification if an `email` field is provided. This completes the snowflake pattern first sketched in earlier phases (review assignment, issue assignment, discussion mentions all pass the reviewer's/assignee's/member's email).
- The `Notification` model already had an optional `email: Optional[str]` field – now it's actively used.

### 3. Notifications Page (Frontend)
- **`frontend/src/pages/Notifications.jsx`** – New page listing all notifications for the authenticated user, with unread/badges, mark-as-read per-item, mark-all-read, and navigation to the related submission/issue.
- **`frontend/src/components/NotificationItem.jsx`** – Reusable list item component showing title, body, type-specific badge, and a "Mark as read" button.
- **`frontend/src/lib/api.js`** – Added `listNotifications()`, `markNotificationRead()`, and `markAllNotificationsRead()` functions.
- **`frontend/src/App.jsx`** – Added `/notifications` route and a "Notifications" navigation item in the header (new icon in the NAV array).

## API Endpoints Added

| Endpoint | Description |
|---|---|
| `POST /api/v1/conferences/diff` | Diff two template versions for a conference |
| `GET /notifications` | List all notifications for the current user |
| `PATCH /notifications/{id}` | Mark a single notification as read |
| `PATCH /notifications/read-all` | Mark all notifications as read |

## Behavioral Changes
- Reviewer assignment now captures the reviewer's email and triggers email delivery (logged).
- Issue assignment now captures the assignee's email and triggers email delivery.
- Discussion mentions now capture each conference member's email (non-author only) and trigger email delivery.
- All notifications carry an optional `email` field for the snowflake pattern.

## Test Compatibility
- All existing **10 backend API tests** continue to pass unchanged.
- The new diff endpoint and notification services have not broken any existing functionality.
- Frontend builds successfully with Vite.

## Migration / Backward Compatibility
- No database schema migrations required – new tables/columns are additive only.
- The email service logs to a file; replacing with a real SMTP transport only requires swapping the `send_email` implementation or the `EmailSender` subclass.
- The diff engine produces a pure data structure; no UI changes are forced.

## Next Steps (Optional)
- Replace the file‑based email logger with an actual SendGrid/Postmark integration.
- Add a notification badge count to the header next to the bell icon.
- Wire the diff UI into the conference management page for side‑by‑side template comparison.