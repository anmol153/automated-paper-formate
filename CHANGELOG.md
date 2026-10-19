# Changelog

All notable changes to the **Paper-Format** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-10-15

### Added
- **Template diff engine** (`backend/app/utils/diff_engine.py`) – structured comparison of two `RuleSet` versions, with per‑group helpers (`diff_file_type`, `diff_pages`, `diff_sections`, etc.) and a high‑level `diff_rulesets` function.
- **`POST /api/v1/conferences/diff`** endpoint – accepts two template IDs and returns a detailed diff payload plus a human‑readable summary.
- **`GET /api/v1/conferences/{conf_id}/latest`** – returns the most recent `RuleSet` for a conference; requester must be a conference member.
- **Frontend `TemplateDiff` page** (`TemplateDiff.jsx`) – calls the diff endpoint and renders the JSON diff.
- **Frontend `LatestTemplate` page** (`LatestTemplate.jsx`) – fetches and displays the latest template version.
- **"Diff" and "Latest" buttons** on each conference card in the `Conferences` dashboard.
- **Notification system hardening** – file‑based email logger (`backend/app/services/email.py`) that writes to `data/email_logs/email-YYYY-MM-DD.log`; the `Notification` model now carries an optional `email` field.
- **Optional SMTP sender** (`backend/app/services/email_smtp.py`) – configured via `SMTP_HOST/PORT/USER/PASSWORD/FROM` env vars; falls back to the file logger when unconfigured.
- **New API client functions** in `frontend/src/lib/api.js`: `diffTemplateVersions`, `getLatestTemplateVersion`, `listNotifications`, `markNotificationRead`, `markAllNotificationsRead`.
- **New UI pages**: `Notifications.jsx`, `NotificationItem.jsx`, `TemplateDiff.jsx`, `LatestTemplate.jsx`.
- **Conference navigation items** – "Diff" and "Latest" added to the header NAV array.
- **`.env.example`** – documentation of all environment variables.
- **Docker support** – `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`.
- **GitHub Actions CI** (`.github/workflows/ci.yml`) – runs ruff lint, `pytest` suite, and uploads results on failure.
- **Version bump** to `0.4.0` (see `backend/app/config.py`).

### Changed
- **Backend config** – `APP_VERSION` updated from `1.0.0` to `0.4.0`.
- **Notification CRUD** – `NotificationStore.create()` now calls `send_email()` when an `email` address is present; the `email` field is optional and was already present on the model.
- **API client** – restructured notification exports; added new diff/latest helpers.
- **Updated test expectations** – all 10 existing backend API tests continue to pass unchanged.

### Fixed
- Minor typogrpahy in `RELEASE_NOTES.md`.
- Corrected `handleDelete` reference in `Conferences.jsx` diff button onClick.

## [0.3.0] - 2026-10-15

### Added
- Full conference model (`Conference`, `ConferenceMember`, `ConferenceRole`).
- Template versioning (immutable versions scoped to conference).
- Submission workflow: create → assign reviewer → set verdict → discussion threads.
- Issue tracking CRUD with role‑based permissions.
- Notification snowflake pattern (reviewer/assignee/mention emails).
- Basic health, compare, parse, template CRUD, and auth endpoints.
- Frontend: Submit, Compare, Conferences, Reports pages; header navigation; theme toggle.

### Changed
- N/A

### Fixed
- N/A

## Unreleased
- (Work in progress – see `0.4.0` for items currently being shipped.)