/** Synthetic browser QA; all API traffic is intercepted before the backend. */
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const { chromium } = await import(process.env.PAPER_BROWSER_MODULE || "playwright-core");
const base = process.env.PAPER_UI_BASE_URL || "http://127.0.0.1:5174";
const directory = fileURLToPath(new URL("./screenshots/", import.meta.url));
await mkdir(directory, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.PAPER_BROWSER_PATH || "/usr/bin/chromium", headless: true });
try {
  for (const width of [1440, 1024, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 844 }, reducedMotion: "reduce" });
    const page = await context.newPage(); page.setDefaultTimeout(10000);
    let signedIn = true, failLogout = false, accepts = 0;
    const errors = [], unexpected = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request(); const path = new URL(request.url()).pathname.replace("/api/v1", "");
      let status = 200, data;
      if (path === "/auth/me") { if (!signedIn) { status = 401; data = { detail: "Sign in" }; } else data = { user_id: "qa", full_name: "Alex Researcher", email: "alex@example.test" }; }
      else if (path === "/auth/logout") { if (failLogout) { status = 503; data = { detail: "Sign-out temporarily unavailable" }; } else { signedIn = false; data = {}; } }
      else if (path === "/auth/google/config") data = { enabled: false };
      else if (path === "/auth/google/connection") data = { connected: true, email_at_link: "alex@example.test", linked_at: "2026-10-01T12:00:00Z" };
      else if (path === "/notifications/count-unread") data = { count: 0 };
      else if (path === "/notifications/feed") data = { items: [], next_cursor: null };
      else if (path === "/invitations/inspect") data = { conference_id: "demo", conference_name: "Research Systems Conference", role: "reviewer", status: "pending", expires_at: 1900600000 };
      else if (path === "/invitations/accept") { accepts++; data = {}; }
      else if (path === "/reviewer/workspace") data = { assignments: [{ assignment_id: "a", submission_id: "paper-a", title: "Reproducible scientific workflows", paper_number: 12, review_state: "not_started", deadline: "2030-05-01T12:00:00Z" }, { assignment_id: "b", submission_id: "paper-b", title: "Reliable research infrastructure", paper_number: 18, review_state: "draft", deadline: "2025-01-01T12:00:00Z" }, { assignment_id: "c", submission_id: "paper-c", title: "Open science collaboration", review_state: "not_started", deadline: null }], conflicts: [] };
      else { unexpected.push(path); status = 404; data = { detail: "No QA fixture" }; }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    });
    const root = () => page.locator(width >= 1024 ? ".pf-sidebar-account" : ".pf-header-account");
    const trigger = () => root().getByRole("button", { name: "Account menu", exact: true });
    const menu = () => page.getByRole("menu", { name: "Account options", exact: true });
    async function open() { await trigger().click(); await menu().waitFor(); }
    async function capture(name) {
      await page.mouse.move(0, 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name} overflows at ${width}px`);
      if (await menu().count()) {
        const box = await menu().boundingBox(); assert.ok(box.x >= 0 && box.y >= 0 && box.x + box.width <= width && box.y + box.height <= 844, "Menu stays in the viewport");
      }
      // Viewport-anchored overlays must not be captured by resizing a long page.
      if (width === 1440 || width === 390) await page.screenshot({ path: `${directory}${name}-${width}.png`, fullPage: !(await menu().count()) });
    }
    await page.goto(base + "/results"); await trigger().waitFor(); await open();
    assert.deepEqual(await menu().getByRole("menuitem").allTextContents(), ["Settings", "My Invitations", "My Schedule", "Docs", "Sign out"]);
    await capture("account-menu");
    await page.keyboard.press("End"); assert.equal(await menu().getByRole("menuitem", { name: "Sign out", exact: true }).evaluate((node) => node === document.activeElement), true);
    await page.keyboard.press("ArrowDown"); assert.equal(await menu().getByRole("menuitem", { name: "Settings", exact: true }).evaluate((node) => node === document.activeElement), true);
    await page.keyboard.press("Escape"); assert.equal(await trigger().evaluate((node) => node === document.activeElement), true);
    await open(); await page.locator("main").click({ position: { x: 20, y: 20 } }); assert.equal(await menu().count(), 0);
    await open(); await page.keyboard.press("Tab"); assert.equal(await menu().count(), 0);
    await open(); await menu().getByRole("menuitem", { name: "Settings", exact: true }).click(); await page.getByRole("heading", { name: "Account settings", exact: true }).waitFor(); assert.equal(await menu().count(), 0);
    await open(); await menu().getByRole("menuitem", { name: "My Invitations", exact: true }).click(); await page.getByRole("heading", { name: "My invitations", exact: true }).waitFor(); await capture("my-invitations");
    await page.getByRole("textbox", { name: "Invitation link", exact: true }).fill("https://other.example/invitations#token=" + "q".repeat(43)); await page.getByRole("button", { name: "Open invitation →", exact: true }).click(); await page.locator('[aria-invalid="true"]').waitFor(); assert.equal(new URL(page.url()).pathname, "/my-invitations");
    await page.getByRole("textbox", { name: "Invitation link", exact: true }).fill(`${base}/invitations#token=${"q".repeat(43)}`); await page.getByRole("button", { name: "Open invitation →", exact: true }).click(); await page.getByRole("heading", { name: "Research Systems Conference", exact: true }).waitFor(); assert.equal(accepts, 0);
    await open(); await menu().getByRole("menuitem", { name: "My Schedule", exact: true }).click(); await page.getByRole("heading", { name: "Review deadlines", exact: true }).waitFor(); await page.getByText("Overdue", { exact: true }).waitFor(); await capture("my-schedule");
    await open(); await menu().getByRole("menuitem", { name: "Docs", exact: true }).click(); await page.getByRole("heading", { name: "Docs", exact: true }).waitFor(); await capture("docs");
    if (width >= 1280) {
      await page.getByRole("button", { name: "Collapse navigation", exact: true }).click(); await open(); await capture("account-menu-collapsed"); await page.keyboard.press("Escape");
    }
    if (width < 1024) {
      await page.getByRole("button", { name: "Open navigation", exact: true }).click();
      const drawerTrigger = page.locator("dialog .pf-account-trigger"); await drawerTrigger.click(); await menu().waitFor(); await page.waitForFunction(() => !!document.activeElement.closest('[role="menu"]')); await capture("account-menu-drawer");
      await page.keyboard.press("Escape"); assert.equal(await page.locator("dialog").isVisible(), true); assert.equal(await drawerTrigger.evaluate((node) => node === document.activeElement), true);
      await drawerTrigger.click(); await menu().getByRole("menuitem", { name: "My Schedule", exact: true }).click(); await page.getByRole("heading", { name: "My schedule", exact: true }).waitFor(); assert.equal(await page.locator("dialog").isVisible(), false);
    }
    await open(); failLogout = true; await menu().getByRole("menuitem", { name: "Sign out", exact: true }).click(); await menu().getByRole("alert").waitFor(); assert.equal(signedIn, true);
    failLogout = false; await menu().getByRole("menuitem", { name: "Sign out", exact: true }).click(); await trigger().waitFor({ state: "detached" }); assert.equal(signedIn, false);
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []);
    console.log(`OK ${width}px: account menu, keyboard, destinations, mobile drawer and sign-out retry`);
    await context.close();
  }
} finally { await browser.close(); }
