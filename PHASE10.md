# Phase 10 — In-app notification center

This phase makes the existing collaboration notifications usable throughout the
application. It reuses the notification table, workflow events, permission checks,
React/Tailwind components and cookie-session system. No dependency installation,
schema migration, configuration change or email delivery is involved.

## User experience

The header has a notification bell with an unread count, including when the count
is zero. Click it for up to five recent unread updates and a link to the full
history at `/notifications`. Click again, press Escape, select a link or click
outside to close it. Escape returns focus to the bell. Links and read controls
are ordinary keyboard-accessible links and buttons.

The bell refreshes every 60 seconds while the tab is visible, when the browser
regains focus, when the tab becomes visible, when opened, and after a read action
elsewhere in the same app tab. It does not use WebSockets or browser notifications.
Polling stops on sign-out/unmount. Previously received information cannot be
remotely erased; access changes are reflected on the next successful refresh.

The history screen offers an unread-only filter, per-item read controls, mark-all,
timestamps, explicit refresh, and batches of 25 older notifications. Refresh,
focus return, filter changes and successful read actions return to the latest
page, as explained on screen. Following a notification does not silently mark it
read. Read counts come from the backend after a successful write; a failed write
does not decrement them. Errors offer retry without replacing the notification
item with a dead end.

Reads are scoped to the signed-in account. Switching accounts or signing out
clears the UI; old fetches are aborted and late responses ignored. Nothing is
saved to browser storage. The header and history synchronize read actions through
an in-memory event scoped to the account. Other browser tabs catch up through
polling or focus refresh.

## Backend and compatibility

`GET /api/v1/notifications/feed` accepts `limit` (1–50, default 25), `unread_only`
and optional `before`. Its response is `{items, next_cursor}`. The cursor represents
a `(created_at, notification_id)` position in descending order and is tied to the
recipient and unread filter. It is validated input, not a credential or an access
grant. Newer arrivals do not shift already loaded pages; refresh sees those arrivals.
Notification dates are retained from their original events.

The store streams rows in chunks of 100. The API applies the existing current-paper,
membership and confidential-review visibility rules **before** filling a page.
Hidden rows cannot consume page slots or cause a cursor to reveal hidden history.
Returned bodies retain the existing generic projection and exclude recipient email.
Counts include only currently accessible unread notifications. Revoked reviewer
assignments and lost chair privileges hide previously delivered notifications from
these APIs and prevent marking them read.

Both read endpoints now recheck visibility inside a shared database transaction.
Mark-all updates only visible rows belonging to the recipient and rolls back the
whole operation if a write fails. Repeating an individual read preserves its original
`read_at`. Existing notification list, unread list, count and read routes remain
compatible. The active schema-8 database remains selected.

Response size and streaming memory are bounded, but authorization still inspects
candidate history rows and counts scan all unread rows for the recipient. This is
not constant-time work. The older compatibility list endpoints remain unpaginated.
Large installations may eventually need indexed visibility queries and retention
policies; this phase does not add a queue or another database.

Important files:

- `backend/app/api/notification_routes.py`: feed, current-access counts and atomic
  read operations.
- `backend/app/storage/notification_store.py`: streaming history and stable ordering.
- `frontend/src/lib/useNotifications.js`: account isolation, cancellation, polling,
  pagination, refresh and read synchronization.
- `frontend/src/components/NotificationDropdown.jsx` and `NotificationItem.jsx`:
  header panel and reusable accessible entries.
- `frontend/src/pages/Notifications.jsx`: full notification history.

This phase consumes notifications already produced by assignments, discussions,
formatting checks, revisions, workflow events and review actions. It does not add
new email delivery, invitation emails, mentions, deadline reminders, notification
preferences or muted subscriptions. Existing optional SMTP modules are unchanged.
Confidential chair notifications remain governed by the existing review rules.

## Test it yourself

1. Open `http://localhost:5173` and sign in. Refresh the page to load the new header.
   The bell remains present even with zero unread updates.
2. Use two browser profiles: chair and author/reviewer. Open an existing paper that
   both participants can access. From one profile, post a participant-visible
   comment. Notifications intentionally exclude the actor who triggered an event.
3. Return focus to the other profile or wait up to a minute in its visible tab.
   Open the bell and follow the update to the authorized paper.
4. Choose **View all notifications**. Try **Unread only**, mark one entry read and
   then mark all read. The header count should agree after refresh. Generating more
   than 25 visible notifications enables **Load older notifications**.
5. Check keyboard navigation, Escape and outside-click closing. Open a membership
   notification: its link should lead to Conferences.
6. Remove a reviewer's assignment as chair, then refresh as that reviewer. The old
   paper notifications and their unread count must disappear. Direct access to the
   paper must still be rejected. Use a test assignment for this check.
7. Sign out and sign into another account. No previous account's notification text
   or count should remain. For an error/retry check, temporarily stop your backend,
   refresh notifications, restart it, then use Refresh again.

## Verification

All tests use disposable copies or mocked API adapters; no test data is written to
the selected local database. From the repository root, with the existing test venv:

```bash
/tmp/paper-format-phase2-venv/bin/python backend/run_isolated_tests.py -q
/tmp/paper-format-phase2-venv/bin/python backend/run_isolated_tests.py backend/tests/test_phase10_notifications.py -q
/tmp/paper-format-phase2-venv/bin/python backend/run_ui_checks.py
```

From `frontend/`:

```bash
npm run test:notifications
npm run build
```

Verified: the full backend run passed **393 tests with 8 optional-fixture skips**.
The final focused suite passed **17 tests**, including two confidentiality/CSRF
cases added after that full run. All **12 notification UI scenarios** passed.
The expanded real-API harness passed, including persisted read state, authorized
notification history, header opening and unread counts, alongside earlier platform
flows. The production frontend build passed. Existing deprecation warnings remain.
Vite reports a bundle-size advisory for the 500.20 kB JavaScript chunk (144.28 kB
gzip); loading optimization remains separate work. Local backend and Vite-proxy
health checks returned 200, the new feed rejected anonymous requests with 401 on
both paths, and the `/notifications` frontend route returned 200.
JSDOM interaction checks do not replace manual visual, screen-reader or browser
layout testing. No production deployment was performed.
