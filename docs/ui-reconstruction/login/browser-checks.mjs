import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
// Existing tooling only. All API responses and the Google chooser are synthetic.
const { chromium } = await import(process.env.PAPER_BROWSER_MODULE || "playwright-core");
const base = process.env.PAPER_UI_BASE_URL || "http://127.0.0.1:5174";
const output = fileURLToPath(new URL("./screenshots/", import.meta.url)); await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.PAPER_BROWSER_PATH || "/usr/bin/chromium", headless: true });
try {
  for (const width of [1440, 768, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    await context.addInitScript(() => {
      let callback;
      window.google = { accounts: { id: { initialize: (options) => { callback = options.callback; }, renderButton: (container, options) => { const button = document.createElement("button"); button.type = "button"; button.textContent = "Continue with Google"; button.style.width = `${options.width}px`; button.onclick = () => callback({ credential: "synthetic-google-credential" }); container.appendChild(button); } } } };
    });
    const page = await context.newPage(); page.setDefaultTimeout(10000);
    let user = null, failLogin = true, googleEnabled = false, registrations = 0, accepts = 0;
    const errors = [], unexpected = []; page.on("pageerror", (err) => errors.push(err.message));
    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname.replace("/api/v1", ""); let status = 200, data;
      if (path === "/auth/me") { if (!user) { status = 401; data = { detail: "Sign in" }; } else data = user; }
      else if (path === "/auth/register") { registrations++; data = {}; }
      else if (path === "/auth/login") { if (failLogin) { status = 401; data = { detail: "Incorrect email or password" }; } else { user = { user_id: "qa", full_name: "Alex Researcher", email: "alex@example.test" }; data = {}; } }
      else if (path === "/auth/google/config") data = { enabled: googleEnabled, client_id: "synthetic-client" };
      else if (path === "/auth/google/challenge") data = { challenge_id: "synthetic-challenge", nonce: "synthetic-nonce", client_id: "synthetic-client" };
      else if (path === "/auth/google/complete") { status = 401; data = { detail: "Google could not verify this sign-in. Try again." }; }
      else if (path === "/notifications/count-unread") data = { count: 0 };
      else if (path === "/notifications/feed") data = { items: [], next_cursor: null };
      else if (path === "/conferences/") data = [];
      else if (path === "/reviewer/workspace") data = { assignments: [], conflicts: [] };
      else if (path === "/invitations/inspect") data = { conference_id: "demo", conference_name: "Research Systems Conference", role: "author", status: "pending", expires_at: 1900600000 };
      else if (path === "/invitations/accept") { accepts++; data = {}; }
      else { unexpected.push(path); status = 404; data = { detail: "No fixture" }; }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    });
    async function capture(name) { await page.mouse.move(0, 0); assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name} overflows at ${width}`); if (width === 1440 || width === 390 || width === 320) await page.screenshot({ path: `${output}${name}-${width}.png`, fullPage: true }); }
    await page.goto(base + "/login"); await page.getByText("Google sign-in is currently unavailable. You can use email and password.", { exact: true }).waitFor(); await capture("sign-in");
    assert.equal(await page.locator(".pf-sidebar").count(), 0);
    await page.getByRole("textbox", { name: "Email", exact: true }).fill("alex@example.test"); await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
    await page.getByRole("button", { name: "Show password", exact: true }).click(); assert.equal(await page.locator('input[autocomplete="current-password"]').getAttribute("type"), "text"); await page.getByRole("button", { name: "Hide password", exact: true }).click();
    await page.getByRole("button", { name: "Sign in", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "Incorrect email" }).waitFor(); assert.equal(await page.getByRole("textbox", { name: "Email", exact: true }).inputValue(), "alex@example.test"); await capture("sign-in-error");
    await page.getByRole("button", { name: "Create an account", exact: true }).click(); await page.getByRole("textbox", { name: "Full name", exact: true }).fill("Alex Researcher"); await capture("create-account");
    assert.equal(await page.locator('input[autocomplete="new-password"]').getAttribute("minlength"), "8");
    failLogin = false; await page.getByRole("button", { name: "Create account", exact: true }).click(); await page.getByRole("heading", { name: "Welcome back, Alex.", exact: true }).waitFor(); assert.equal(registrations, 1);
    user = null; googleEnabled = true; await page.goto(base + "/login"); await page.getByRole("button", { name: "Continue with Google", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "Google could not verify" }).waitFor(); await capture("google-error");
    await page.getByRole("button", { name: "Retry Google sign-in", exact: true }).click(); await page.getByRole("button", { name: "Continue with Google", exact: true }).waitFor();
    await page.getByRole("button", { name: "Switch to dark mode", exact: true }).click(); await capture("sign-in-dark");
    googleEnabled = false; await page.goto(base + "/invitations#token=" + "q".repeat(43)); await page.getByRole("heading", { name: "Join a conference", exact: true }).waitFor(); await capture("invitation-sign-in");
    await page.getByRole("textbox", { name: "Email", exact: true }).fill("alex@example.test"); await page.getByLabel("Password", { exact: true }).fill("synthetic-password"); await page.getByRole("button", { name: "Sign in", exact: true }).click(); await page.getByRole("heading", { name: "Research Systems Conference", exact: true }).waitFor(); assert.equal(new URL(page.url()).hash, "#token=" + "q".repeat(43)); assert.equal(accepts, 0);
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []);
    console.log(`OK ${width}px: sign-in, errors, registration, Google retry, dark theme and invitation callback`);
    await context.close();
  }
} finally { await browser.close(); }
