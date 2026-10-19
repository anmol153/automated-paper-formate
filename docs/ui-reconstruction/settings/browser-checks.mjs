/** Synthetic API replay for UI QA. Every API request is intercepted locally. */
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const { chromium } = await import(process.env.PAPER_BROWSER_MODULE || "playwright-core");
const base = process.env.PAPER_UI_BASE_URL || "http://127.0.0.1:5174";
const destination = fileURLToPath(new URL("./screenshots/", import.meta.url));
await mkdir(destination, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.PAPER_BROWSER_PATH || "/usr/bin/chromium", headless: true });
const token = "q".repeat(43);
try {
  for (const width of [1440, 1024, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    const page = await context.newPage(); page.setDefaultTimeout(10000);
    let actor = "chair", failCreate = false, failInspect = false, removed = false, conflict = null;
    const conference = { conference_id: "demo", name: "Research Systems Conference 2027", description: "A forum for reliable systems, open research and scientific collaboration." };
    let config = { enabled: true, can_configure: true, version: 1, settings: { abbreviation: "RSC 2027", research_scope: "Reliable systems and reproducible scientific workflows.", website: "https://example.org", lifecycle_status: "setup", submissions_open_at: null, submissions_close_at: null, revisions_close_at: null, require_title: true, require_abstract: true, require_authors: false, require_track: false }, tracks: [{ track_id: "main", name: "Main research track", description: "Original systems research", active: true, version: 1 }], submission_window: { allowed: false } };
    let invitations = [{ invitation_id: "existing", recipient_email: "reviewer@example.test", role: "reviewer", status: "accepted", created_at: 1792000000, expires_at: 1900600000, accepted_at: 1792100000 }];
    let notifications = [{ notification_id: "n1", title: "A paper is ready for your review", body: "Paper #12 has been assigned to you. Open the paper to read its latest revision.", type: "reviewer_assigned", related_id: "paper-one", read: false, created_at: "2026-10-18T12:00:00Z" }, { notification_id: "n2", title: "Welcome to the conference", body: "You now have access to Research Systems Conference 2027.", type: "member_added", related_id: "demo", read: true, created_at: "2026-10-17T12:00:00Z" }];
    const errors = []; const unhandled = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request(); const url = new URL(request.url()); const path = url.pathname.replace("/api/v1", "");
      const method = request.method(); const payload = request.postDataJSON(); let status = 200; let data;
      if (path === "/auth/me") { if (!actor) { status = 401; data = { detail: "Sign in" }; } else data = { user_id: actor, full_name: "Alex Researcher", email: "alex@example.test" }; }
      else if (path === "/auth/google/config") data = { enabled: false };
      else if (path === "/auth/google/connection") data = { connected: true, email_at_link: "alex@example.test", linked_at: "2026-10-01T12:00:00Z" };
      else if (path === "/conferences/demo") { if (method === "PATCH") Object.assign(conference, payload); data = { ...conference, members: actor === "chair" ? [{ user_id: "chair", role: "owner" }] : [] }; }
      else if (path === "/conferences/demo/settings") { if (method === "PUT") config = { ...config, settings: payload.settings, version: config.version + 1 }; data = { ...config, can_configure: actor === "chair" }; }
      else if (path === "/conferences/demo/tracks" && method === "POST") { const track = { ...payload, track_id: "new-track", version: 1 }; config.tracks.push(track); data = track; }
      else if (path === "/conferences/demo/invitations" && method === "POST") { if (failCreate) { status = 429; data = { detail: "Too many invitations. Try again." }; } else { const record = { invitation_id: "new", recipient_email: payload.email, role: payload.role, status: "pending", created_at: 1792200000, expires_at: 1900600000 }; invitations.unshift(record); data = { invitation: record, token }; } }
      else if (path === "/conferences/demo/invitations/new" && method === "DELETE") { invitations = invitations.map((item) => item.invitation_id === "new" ? { ...item, status: "revoked" } : item); data = invitations[0]; }
      else if (path === "/conferences/demo/invitations") data = { enabled: true, invitations, next_cursor: null };
      else if (path === "/invitations/inspect") { if (failInspect) { status = 404; data = { detail: "Invitation unavailable for this account" }; } else data = { invitation_id: "demo-invite", conference_id: "demo", conference_name: conference.name, role: "reviewer", status: "pending", expires_at: 1900600000 }; }
      else if (path === "/invitations/accept") data = { conference_id: "demo", conference_name: conference.name, membership_role: "reviewer", status: "accepted" };
      else if (path === "/notifications/count-unread") data = { count: notifications.filter((item) => !item.read).length };
      else if (path === "/notifications/feed") data = { items: notifications.filter((item) => url.searchParams.get("unread_only") !== "true" || !item.read), next_cursor: null };
      else if (path.startsWith("/notifications/") && method === "PATCH") { notifications = notifications.map((item) => path.endsWith("/read-all") || path.endsWith(`/${item.notification_id}`) ? { ...item, read: true } : item); data = {}; }
      else if (path === "/reviewer/workspace") data = { assignments: [{ assignment_id: "a", submission_id: "paper-one", paper_number: 12, title: "Towards reproducible scientific workflows", filename: "research-paper.pdf", status: "under_review", review_state: "not_started", deadline: "2027-05-01T12:00:00Z" }, { assignment_id: "b", submission_id: "paper-two", paper_number: 18, title: "Open collaboration in research systems", filename: "collaboration.pdf", status: "under_review", review_state: "submitted", deadline: "2027-05-01T12:00:00Z" }].filter((item) => !removed || item.assignment_id !== "a"), conflicts: conflict ? [conflict] : [] };
      else if (path === "/reviewer/assignments/a/conflict") { removed = true; conflict = { conflict_id: "c1", submission_id: "paper-one", reason: payload.reason, version: 1 }; data = conflict; }
      else if (path === "/reviewer/conflicts/c1/withdraw") { conflict = null; data = {}; }
      else { unhandled.push(`${method} ${path}`); status = 404; data = { detail: "No test fixture for this API" }; }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    });
    async function capture(name) {
      await page.mouse.move(0, 0); await page.evaluate(() => document.fonts.ready);
      await page.waitForFunction(() => getComputedStyle(document.querySelector(".pf-management")).fontSize === "14px");
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name} overflows at ${width}px`);
      if (width === 1440 || width === 390) await page.screenshot({ path: `${destination}${name}-${width}.png`, fullPage: true });
    }
    await page.goto(base + "/settings"); await page.getByRole("heading", { name: "Google account connected" }).waitFor(); await capture("account-settings");
    await page.getByRole("button", { name: "Copy account ID", exact: true }).click(); await page.getByRole("status").filter({ hasText: /copied|copy it manually/ }).waitFor();
    await page.locator("#appearance").getByRole("button", { name: "Switch to dark mode" }).click(); await capture("account-settings-dark");
    await page.locator("#appearance").getByRole("button", { name: "Switch to light mode" }).click();
    await page.goto(base + "/conferences/demo?tab=settings"); await page.getByRole("group", { name: "Submission schedule", exact: true }).waitFor(); await capture("conference-settings");
    await page.getByLabel("Abbreviation", { exact: true }).fill("RSC"); await page.getByRole("button", { name: "Save conference settings", exact: true }).click(); await page.getByRole("status").filter({ hasText: "Conference settings saved." }).waitFor(); assert.equal(config.settings.abbreviation, "RSC");
    await page.getByRole("textbox", { name: "New track name", exact: true }).fill("Short papers"); await page.getByRole("button", { name: "Create track", exact: true }).click(); await page.waitForFunction(() => [...document.querySelectorAll('input')].some((node) => node.value === "Short papers"));
    await page.getByRole("navigation", { name: "Conference sections" }).getByRole("link", { name: "Invitations", exact: true }).click(); await page.getByRole("heading", { name: "Invite participants", exact: true }).waitFor(); await page.getByRole("searchbox", { name: "Search loaded invitations" }).waitFor(); await capture("conference-invitations");
    await page.getByRole("textbox", { name: "Recipient email", exact: true }).fill("new-author@example.test"); failCreate = true;
    await page.getByRole("button", { name: "Create invitation link", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "Too many invitations" }).waitFor(); assert.equal(await page.getByRole("textbox", { name: "Recipient email", exact: true }).inputValue(), "new-author@example.test");
    failCreate = false; await page.getByRole("button", { name: "Create invitation link", exact: true }).click(); await page.getByLabel("Private invitation link", { exact: true }).waitFor(); await capture("invitation-created");
    assert.equal(new URL(await page.getByLabel("Private invitation link", { exact: true }).inputValue()).search, "");
    await page.getByRole("button", { name: "Copy invitation link", exact: true }).click(); await page.getByRole("status").filter({ hasText: /Invitation link copied|copy it manually/ }).waitFor();
    await page.getByRole("button", { name: "Revoke invitation for new-author@example.test", exact: true }).click(); await page.getByLabel("Private invitation link", { exact: true }).waitFor({ state: "detached" });
    await page.getByRole("searchbox", { name: "Search loaded invitations" }).fill("revoked"); assert.equal(await page.locator(".pf-invitation-row").count(), 1);
    await page.goto(base + "/notifications"); await page.getByRole("link", { name: "A paper is ready for your review", exact: true }).waitFor(); await capture("notifications");
    await page.getByLabel("Unread only", { exact: true }).check(); await page.waitForFunction(() => document.querySelectorAll('.pf-notification-history > li').length === 1);
    await page.getByRole("button", { name: "Mark A paper is ready for your review as read", exact: true }).click(); await page.getByRole("heading", { name: "No unread notifications.", exact: true }).waitFor();
    await page.goto(base + "/reviewer"); await page.getByRole("link", { name: "Towards reproducible scientific workflows", exact: true }).waitFor(); await capture("reviewer-workspace");
    await page.getByRole("combobox", { name: "Filter by review progress", exact: true }).selectOption("submitted"); assert.equal(await page.locator(".pf-assignment-row").count(), 1);
    await page.getByRole("combobox", { name: "Filter by review progress", exact: true }).selectOption("");
    await page.locator(".pf-assignment-row").first().locator("summary").click(); await page.locator(".pf-assignment-row").first().getByRole("textbox", { name: "Confidential reason for chairs", exact: true }).fill("I collaborate with one of the authors."); await page.getByRole("button", { name: "Declare conflict and remove my assignment", exact: true }).first().click();
    await page.getByRole("heading", { name: "Your active conflict declarations", exact: true }).waitFor(); assert.equal(await page.locator(".pf-assignment-row").count(), 1); await capture("reviewer-conflict");
    await page.getByRole("textbox", { name: "Reason to withdraw this declaration", exact: true }).fill("Recorded in error."); await page.getByRole("button", { name: "Withdraw declaration", exact: true }).click(); await page.getByRole("heading", { name: "Your active conflict declarations", exact: true }).waitFor({ state: "detached" }); assert.equal(await page.locator(".pf-assignment-row").count(), 1);
    actor = "author"; await page.goto(base + "/conferences/demo?tab=invitations"); await page.getByRole("heading", { name: "Chair access required", exact: true }).waitFor(); assert.equal(await page.locator('input[type="email"]').count(), 0);
    await page.goto(base + "/invitations"); await page.getByRole("alert").filter({ hasText: "complete invitation link" }).waitFor(); await capture("invitation-invalid");
    failInspect = true; await page.goto(base + "/invitations#token=" + token); await page.getByRole("alert").filter({ hasText: "unavailable for this account" }).waitFor(); assert.equal(await page.getByRole("heading", { name: conference.name, exact: true }).count(), 0); await capture("invitation-unavailable");
    failInspect = false; await page.getByRole("button", { name: "Check invitation again", exact: true }).click(); await page.getByRole("button", { name: "Accept invitation", exact: true }).waitFor(); await capture("invitation-accept");
    await page.getByRole("button", { name: "Accept invitation", exact: true }).click(); await page.getByRole("heading", { name: "Invitation accepted", exact: true }).waitFor(); assert.equal(new URL(page.url()).hash, ""); await capture("invitation-accepted");
    actor = null; await page.goto(base + "/settings"); await page.locator("main").getByRole("link", { name: "Sign in", exact: true }).waitFor();
    await page.goto(base + "/invitations#token=" + token); await page.getByRole("heading", { name: "Join a conference", exact: true }).waitFor(); await capture("invitation-sign-in");
    assert.deepEqual(errors, []); assert.deepEqual(unhandled, []);
    console.log(`OK ${width}px: settings, track creation, invitations/retry/copy/revoke, permissions, acceptance, notifications and reviewer conflicts`);
    await context.close();
  }
} finally { await browser.close(); }
