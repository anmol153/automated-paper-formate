# Sign-in redesign

`/login` now uses a focused authentication shell with the Paper-Format brand,
theme control, home link and documentation footer. The management sidebar is
absent on that route. Desktop uses a restrained introduction alongside a 420 px
form card; mobile shows the form directly. Shared tokens provide neutral surfaces,
blue actions, clear input boundaries, error states and consistent spacing.

Email/password sign-in, account creation, Google sign-in and invitation callbacks
retain their existing APIs. Fields disable during submission. The password has
a labelled Show/Hide control that resets to hidden when switching form modes.
Registration retains its minimum length and autocomplete behavior. Errors preserve
input for retry. The Google chooser uses its supported width option to fit the
available card width; no credentials, OAuth configuration or provider protocol changed.

Invitation sign-in reuses just the form card inside the invitation page. Signing
in there retains the token and does not accept the invitation automatically.
No unsupported password-reset or other fake account controls were added.

Validation:

- Management suite: 22 scenarios passed, including sign-in to the dashboard and
  password visibility/account-creation behavior.
- Invitation suite: 11 scenarios passed, including embedded registration.
- Browser journeys passed at 1440, 768, 390 and 320 px: sign-in errors/retry,
  registration, Google retry, dark theme and invitation callback. No runtime page
  errors or horizontal overflow were observed.
- Production build passed. Existing Vite bundle-size advisory remains.

Browser QA uses intercepted synthetic API data and a mock Google chooser. It does
not prove live backend persistence or Google provider availability and does not
create real accounts. Reproduce using existing Playwright tooling:

```bash
PAPER_UI_BASE_URL=http://127.0.0.1:5174 \
PAPER_BROWSER_MODULE=/absolute/path/to/playwright-core/index.mjs \
  node docs/ui-reconstruction/login/browser-checks.mjs
```

| State | Desktop | Mobile |
|---|---|---|
| Sign-in | [1440 px](screenshots/sign-in-1440.png) | [390 px](screenshots/sign-in-390.png) |
| Error | [1440 px](screenshots/sign-in-error-1440.png) | [390 px](screenshots/sign-in-error-390.png) |
| Account creation | [1440 px](screenshots/create-account-1440.png) | [390 px](screenshots/create-account-390.png) |
| Google error | [1440 px](screenshots/google-error-1440.png) | [390 px](screenshots/google-error-390.png) |
| Dark theme | [1440 px](screenshots/sign-in-dark-1440.png) | [390 px](screenshots/sign-in-dark-390.png) |
| Invitation sign-in | [1440 px](screenshots/invitation-sign-in-1440.png) | [390 px](screenshots/invitation-sign-in-390.png) |

Captures use synthetic identities. Additional 320 px captures are in `screenshots/`.
