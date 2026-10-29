/** Chair /reviewer regression and screenshots; every API is a synthetic fixture. */
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const { chromium } = await import(process.env.PAPER_BROWSER_MODULE || "playwright-core");
const output = fileURLToPath(new URL("./screenshots/", import.meta.url)); await mkdir(output, { recursive: true });
const base = process.env.PAPER_UI_BASE_URL || "http://127.0.0.1:5174";
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", headless: true });
try {
  for (const width of [1440, 1024, 768, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    const page = await context.newPage(); page.setDefaultTimeout(10000);
    const calls = [], unexpected = [], errors = []; let role = "chair", failAssignment = false, failProgress = false;
    page.on("pageerror", (error) => errors.push(error.message));
    const papers = [
      { submission_id: "paper-one", paper_number: 1, title: "Reproducible workflows for academic collaboration", filename: "research.pdf", status: "submitted", assignments: [], submitted: 0, missing: 0 },
      { submission_id: "paper-two", paper_number: 2, title: "A reproducible evaluation of document requirements", filename: "evaluation.pdf", status: "under_review", assignments: [{ assignment_id: "a1", reviewer_id: "reviewer-existing", eligible: true, status: "accepted", review_state: "draft" }], submitted: 0, missing: 1 },
      { submission_id: "paper-three", paper_number: 3, title: "Author draft for an upcoming research submission", filename: "draft.pdf", status: "draft", assignments: [], submitted: 0, missing: 0 },
    ];
    const revision = { revision_id: "revision-1", number: 1, filename: "research.pdf", uploaded_at: "2026-10-30T01:00:00Z", uploaded_by: "Author", size_bytes: 500, latest_check: { status: "passed" } };
    const configuration = { form_id: "form-1", policy: { minimum_reviews: 1, reviewer_identities: "hidden", allow_edit_submitted: false }, form: { name: "Research review", recommendations: ["Accept", "Reject"], criteria: [{ id: "quality", label: "Technical quality", kind: "score", minimum: 1, maximum: 5, required: true, visibility: "authors" }] } };
    let ownReview = null;
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request(), method = request.method(); const path = new URL(request.url()).pathname.replace("/api/v1", ""); calls.push({ method, path, body: request.postData() }); let data, status = 200;
      if (path === "/auth/me") data = { user_id: role, full_name: "Demo Chair", email: "chair@example.test" };
      else if (path === "/notifications/count-unread") data = { count: 0 };
      else if (path === "/notifications/feed") data = { items: [], next_cursor: null };
      else if (path === "/reviewer/workspace") data = { assignments: role === "reviewer" ? [{ assignment_id: "a1", submission_id: "paper-two", paper_number: 2, title: papers[1].title, status: "under_review", review_state: "draft", deadline: null }] : papers.flatMap((paper) => paper.assignments.filter((assignment) => assignment.reviewer_id === role).map((assignment) => ({ ...assignment, submission_id: paper.submission_id, paper_number: paper.paper_number, title: paper.title, status: paper.status, deadline: null }))), conflicts: [] };
      else if (path === "/conferences/") data = [{ conference_id: "demo", name: "Research Systems Conference", description: "Synthetic chair assignment demonstration" }, { conference_id: "other", name: "A different conference" }];
      else if (path === "/conferences/demo") data = { conference_id: "demo", name: "Research Systems Conference", members: role === "chair" ? [{ user_id: "chair", role: "owner" }, { user_id: "reviewer-existing", role: "reviewer" }, { user_id: "reviewer-new", role: "reviewer" }] : [] };
      else if (path === "/conferences/other") { status = 404; data = { detail: "Conference not found" }; }
      else if (path === "/conferences/demo/review-progress" && role === "chair") { if (failProgress) { status = 503; data = { detail: "Conference review progress unavailable" }; } else data = { papers, minimum_reviews: 1 }; }
      else if (path === "/submissions/paper-one/review" && method === "POST" && role === "chair") { if (failAssignment) { status = 409; data = { detail: "A conflict or formatting requirement prevents this assignment" }; } else { data = { assignment_id: request.postDataJSON() === "chair" ? "chair-assignment" : "a2", reviewer_id: request.postDataJSON(), eligible: true, status: "pending", review_state: "not_started" }; papers[0].assignments.push(data); papers[0].status = "under_review"; papers[0].missing = 1; } }
      else if (path === "/submissions/paper-one") data = { ...papers[0], conference_id: "demo", authors: [], abstract: "Research abstract", metadata_version: 1 };
      else if (path === "/submissions/paper-one/revisions") data = { revisions: [revision], current_revision_id: revision.revision_id, can_upload_revision: false, can_recheck: true };
      else if (path === "/submissions/paper-one/workflow") data = { status: papers[0].status, revision_id: revision.revision_id, is_chair: true, eligible: true, formatting_gate: "allow_issues", actions: [], assignments: papers[0].assignments };
      else if (path === "/submissions/paper-one/revisions/revision-1/checks") data = [];
      else if (path === "/submissions/paper-one/conflicts") data = [];
      else if (path === "/submissions/paper-one/reviews") data = { is_chair: true, can_review: ownReview?.state !== "submitted", assignment_id: "chair-assignment", revision_id: revision.revision_id, own_review: ownReview, reviews: ownReview ? [ownReview] : [], configuration, progress: { submitted: ownReview?.state === "submitted" ? 1 : 0, missing: 1, assignments: papers[0].assignments } };
      else if (path === "/submissions/paper-one/reviews/mine" && method === "PUT") {
        const payload = request.postDataJSON();
        ownReview = { ...payload, review_id: "chair-review", reviewer_id: "chair", version: payload.expected_version + 1, state: payload.submit ? "submitted" : "draft", is_own: true, form: configuration.form };
        const assignment = papers[0].assignments.find((row) => row.reviewer_id === "chair");
        assignment.review_state = ownReview.state; assignment.status = payload.submit ? "completed" : "accepted";
        data = ownReview;
      }
      else { unexpected.push(`${method} ${path}`); status = 404; data = { detail: "Missing fixture" }; }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    });
    async function capture(name) {
      await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo({ top: 0, behavior: "instant" }); });
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name}: overflow at ${width}px`);
      if ([1440, 390].includes(width)) await page.screenshot({ path: `${output}${name}-${width}.png`, fullPage: true });
    }
    await page.goto(base + "/reviewer"); await page.getByRole("button", { name: "Account menu", exact: true }).first().waitFor();
    await page.getByRole("heading", { name: "Review assignments", exact: true }).waitFor(); await page.locator(".pf-chair-paper").first().waitFor(); assert.equal(await page.locator(".pf-chair-paper").count(), 3);
    await capture("chair-assignments"); assert.equal(await page.getByText("No active review assignments.", { exact: true }).count(), 0);
    await page.getByRole("combobox", { name: "Assignment filter", exact: true }).selectOption("unassigned"); assert.equal(await page.locator(".pf-chair-paper").count(), 1);
    await page.getByRole("searchbox", { name: "Search conference papers", exact: true }).fill("unmatched"); await page.getByRole("heading", { name: "No papers match these filters", exact: true }).waitFor(); await page.getByRole("searchbox", { name: "Search conference papers", exact: true }).fill("");
    await page.locator(".pf-chair-assign-form > summary").click(); await page.getByRole("combobox", { name: "Reviewer for paper 1", exact: true }).selectOption("reviewer-new");
    failAssignment = true; await page.getByRole("button", { name: "Assign reviewer", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "prevents this assignment" }).waitFor(); assert.equal(await page.getByRole("combobox", { name: "Reviewer for paper 1", exact: true }).inputValue(), "reviewer-new");
    failAssignment = false; await page.getByRole("button", { name: "Assign reviewer", exact: true }).click(); await page.getByText("Reviewer assigned. Review progress is being refreshed.", { exact: true }).waitFor(); await page.getByRole("combobox", { name: "Assignment filter", exact: true }).selectOption(""); await page.locator(".pf-chair-paper").first().getByText("reviewer-new", { exact: true }).waitFor();
    assert.equal(JSON.parse(calls.find((call) => call.path === "/submissions/paper-one/review").body), "reviewer-new");
    await page.getByRole("button", { name: "My assigned reviews (0)", exact: true }).click(); await page.getByRole("heading", { name: "No active review assignments.", exact: true }).waitFor(); assert.equal(await page.locator(".pf-chair-paper").count(), 0);
    await page.getByRole("button", { name: "Conference assignments", exact: true }).click(); await page.locator(".pf-chair-paper").first().waitFor();
    failProgress = true; await page.getByRole("button", { name: "Refresh assignments", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "Conference review progress unavailable" }).waitFor(); assert.equal(await page.getByRole("heading", { name: "No accessible submissions yet", exact: true }).count(), 0);
    failProgress = false; await page.getByRole("button", { name: "Retry conference assignments", exact: true }).click(); await page.locator(".pf-chair-paper").first().waitFor();
    await page.getByRole("button", { name: "Switch to dark mode", exact: true }).click(); await capture("chair-assignments-dark");
    const target = page.locator(".pf-chair-paper").first();
    await target.getByRole("button", { name: "Review this paper", exact: true }).click();
    await page.waitForURL("**/submissions/paper-one?tab=reviews");
    const editor = page.locator(".pf-pr-review-editor"); await editor.waitFor();
    assert.equal(JSON.parse(calls.filter((call) => call.path === "/submissions/paper-one/review").at(-1).body), "chair");
    await editor.getByRole("combobox", { name: "Overall recommendation", exact: true }).selectOption("Accept");
    await editor.getByRole("spinbutton", { name: /Technical quality/ }).fill("4");
    await editor.getByRole("textbox", { name: "Confidential comments for chairs", exact: true }).fill("Chair review private notes");
    await editor.getByRole("button", { name: "Save private draft", exact: true }).click();
    await editor.getByText(/Version 1 · draft/).waitFor();
    await capture("chair-own-review");
    await editor.getByRole("button", { name: "Submit formal review", exact: true }).click();
    await editor.getByText(/Version 2 · submitted/).waitFor();
    assert.equal(JSON.parse(calls.filter((call) => call.path.endsWith("/reviews/mine")).at(-1).body).submit, true);
    await page.goto(base + "/reviewer");
    await page.getByRole("button", { name: "My assigned reviews (1)", exact: true }).click();
    await page.locator(".pf-assignment-row").getByRole("link", { name: "View review →", exact: true }).waitFor();
    await page.getByRole("button", { name: "Conference assignments", exact: true }).click();
    await page.locator(".pf-chair-paper").first().getByRole("link", { name: "View my review →", exact: true }).waitFor();
    const previous = calls.length; role = "reviewer"; await page.goto(base + "/reviewer"); await page.getByRole("heading", { name: "Assigned papers", exact: true }).waitFor(); await page.locator(".pf-assignment-row").first().waitFor(); assert.equal(await page.locator(".pf-chair-assignments").count(), 0); assert.ok(!calls.slice(previous).some((call) => call.path.endsWith("/review-progress"))); await capture("reviewer-assignments");
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []); console.log(`OK ${width}px: chair data, role separation, filters, real assignment/retry, personal reviews, progress failures, dark theme, no overflow`); await context.close();
  }
} finally { await browser.close(); }
