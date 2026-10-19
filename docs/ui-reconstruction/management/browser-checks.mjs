/** Browser-only synthetic API fixtures. No request reaches the real backend. */
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const { chromium } = await import(process.env.PAPER_BROWSER_MODULE || "playwright-core");
const destination = fileURLToPath(new URL("./screenshots/", import.meta.url));
await mkdir(destination, { recursive: true });
const base = process.env.PAPER_UI_BASE_URL || "http://localhost:5173";
const browser = await chromium.launch({ executablePath: process.env.PAPER_BROWSER_PATH || "/usr/bin/chromium", headless: true });
try {
  for (const width of [1440, 1024, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    let conference = { conference_id: "demo", name: "Research Systems Conference 2027", description: "A forum for researchers building the next generation of reliable, open and collaborative systems.", members: [{ user_id: "qa-chair", role: "owner" }] };
    let failCreate = false;
    const config = { enabled: true, can_configure: true, version: 1, settings: { abbreviation: "RSC 2027", research_scope: "Reliable systems, open science and research collaboration.", website: "https://example.org", lifecycle_status: "setup", submissions_open_at: null, submissions_close_at: null, revisions_close_at: null, require_title: true, require_abstract: false, require_authors: false, require_track: false }, tracks: [], submission_window: { allowed: false } };
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request(); const path = new URL(request.url()).pathname.replace("/api/v1", "");
      const payload = request.postDataJSON(); let data; let status = 200;
      if (path === "/auth/me") data = { user_id: "qa-chair", full_name: "Alex Researcher", email: "alex@example.test" };
      else if (path === "/auth/google/config") data = { enabled: false };
      else if (path === "/notifications/count-unread") data = { count: 0 };
      else if (path === "/conferences/" && request.method() === "POST") { if (failCreate) { status = 503; data = { detail: "Creation unavailable. Please try again." }; } else { conference = { ...conference, ...payload }; status = 201; data = conference; } }
      else if (path === "/conferences/") data = [conference, { conference_id: "language", name: "Language and Learning Workshop", description: "New methods for language understanding and scientific discovery." }];
      else if (path === "/conferences/demo") { if (payload) conference = { ...conference, ...payload }; data = conference; }
      else if (path === "/conferences/demo/settings") data = config;
      else if (path === "/conferences/demo/templates" || path === "/templates") data = [];
      else if (path === "/conferences/demo/submissions") data = [];
      else if (path === "/conferences/demo/invitations") data = { invitations: [], next_cursor: null, enabled: true };
      else if (path === "/conferences/demo/workflow") data = { formatting_gate: "allow_issues", can_configure: true };
      else if (path === "/conferences/demo/review-configuration") data = { form: { recommendations: ["Accept", "Reject"], criteria: [] }, policy: { deadline: null, minimum_reviews: 2 }, can_configure: true };
      else if (path === "/conferences/demo/review-progress") data = { minimum_reviews: 2, papers: [] };
      else if (path === "/reviewer/workspace") data = { assignments: [{ assignment_id: "review-one", submission_id: "paper-one", paper_number: 12, title: "Towards reproducible scientific workflows", review_state: "not_started", deadline: "2027-05-01T12:00:00Z" }], conflicts: [] };
      else { status = 404; data = { detail: `Unimplemented test fixture: ${path}` }; }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    });
    const errors = []; page.on("pageerror", (error) => errors.push(error.message));
    async function capture(name) {
      await page.mouse.move(0, 0);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForFunction(() => getComputedStyle(document.querySelector(".pf-management")).fontSize === "14px");
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name}: horizontal overflow at ${width}px`);
      if (width === 1440 || width === 390) await page.screenshot({ path: `${destination}${name}-${width}.png`, fullPage: true });
    }
    await page.goto(base + "/"); await page.getByRole("heading", { name: /A better home/ }).waitFor(); await capture("home");
    await page.getByRole("link", { name: "Open dashboard →", exact: true }).click(); await page.getByRole("heading", { name: /Welcome back/ }).waitFor(); await page.getByText("Towards reproducible scientific workflows", { exact: true }).waitFor(); await capture("dashboard");
    await page.goto(base + "/conferences"); await page.getByRole("heading", { name: "Research Systems Conference 2027" }).waitFor(); await capture("conferences");
    await page.getByRole("searchbox", { name: "Search conferences" }).fill("language"); assert.equal(await page.locator("main .pf-conference-row").count(), 1);
    await page.getByRole("searchbox", { name: "Search conferences" }).fill("no match"); await page.getByRole("button", { name: "Clear search" }).click(); assert.equal(await page.locator("main .pf-conference-row").count(), 2);
    await page.locator("main").getByRole("link", { name: "+ Create conference", exact: true }).click(); await page.getByRole("heading", { name: "Conference details", exact: true }).waitFor(); await capture("create-conference");
    await page.getByLabel("Conference name").fill("New Research Conference"); await page.getByLabel("Description", { exact: true }).fill("Synthetic browser QA conference, stored only in this fixture.");
    failCreate = true; await page.getByRole("button", { name: "Create conference", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "Creation unavailable" }).waitFor(); assert.equal(await page.getByLabel("Conference name").inputValue(), "New Research Conference");
    failCreate = false; await page.getByRole("button", { name: "Create conference", exact: true }).click(); await page.getByText("Your conference is created.", { exact: true }).waitFor(); await capture("conference-workspace");
    await page.getByRole("button", { name: "Continue setup →", exact: true }).click(); await page.getByRole("heading", { name: "Conference identity", exact: true }).waitFor(); await capture("conference-settings");
    await page.getByRole("navigation", { name: "Conference sections" }).getByRole("link", { name: "People", exact: true }).click(); await page.getByRole("heading", { name: "Conference people", exact: true }).waitFor(); await capture("conference-people");
    await page.getByRole("navigation", { name: "Conference sections" }).getByRole("link", { name: "Templates", exact: true }).click(); await page.getByText("Configure a template", { exact: true }).click(); await page.getByRole("button", { name: "Start blank template", exact: true }).waitFor(); await capture("conference-templates");
    await page.getByRole("navigation", { name: "Conference sections" }).getByRole("link", { name: "Reviews", exact: true }).click(); await page.getByRole("heading", { name: "Chair review dashboard", exact: true }).waitFor(); await capture("conference-reviews");
    await page.goto(base + "/conferences/demo/submissions"); await page.getByRole("heading", { name: "Papers you can access", exact: true }).waitFor(); assert.equal(await page.locator('#new-submission').count(), 0); await capture("conference-papers");
    await page.goto(base + "/conferences/demo/submit"); await page.getByRole("heading", { name: "Submit a paper", exact: true }).waitFor(); await capture("conference-submit");
    assert.equal(await page.locator('#new-submission input[type="file"]').isDisabled(), true, "Missing template keeps uploads disabled");
    await page.getByRole("button", { name: "Switch to dark mode", exact: true }).click(); await capture("conference-papers-dark");
    assert.deepEqual(errors, [], "Browser runtime errors");
    console.log(`OK ${width}px: home, dashboard, search, create/retry, configuration tabs, paper upload gate and dark theme`);
    await context.close();
  }
} finally { await browser.close(); }
