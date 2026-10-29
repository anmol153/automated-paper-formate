/** D2 visual/interaction QA: synthetic API fixtures, no real papers or writes. */
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const { chromium } = await import(process.env.PAPER_BROWSER_MODULE || "playwright-core");
const output = fileURLToPath(new URL("./screenshots/", import.meta.url)); await mkdir(output, { recursive: true });
const base = process.env.PAPER_UI_BASE_URL || "http://127.0.0.1:5174";
const browser = await chromium.launch({ executablePath: process.env.PAPER_BROWSER_PATH || "/usr/bin/chromium", headless: true });
try {
  for (const width of [1440, 1024, 768, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    const page = await context.newPage(); page.setDefaultTimeout(10000);
    const calls = [], unexpected = [], errors = []; let role = "author", failConversation = false, failUpload = false;
    page.on("pageerror", (error) => errors.push(error.message));
    const paper = { submission_id: "paper-42", conference_id: "demo", paper_number: 42, title: "Towards reproducible scientific workflows", abstract: "Reproducibility depends on more than sharing a final result. We present a practical framework for tracking research artifacts, validating document requirements, and preserving the discussion behind each revision. Our evaluation examines how structured collaboration supports a transparent review process.", authors: [{ name: "Alex Researcher", affiliation: "Institute for Research Systems" }, { name: "Sam Chen", affiliation: "University of Example" }], status: "draft", metadata_version: 1, filename: "research-paper.pdf" };
    const revision = (number) => ({ revision_id: `r${number}`, number, filename: `research-paper-v${number}.pdf`, uploaded_at: "2026-10-19T08:00:00Z", uploaded_by: "Author", size_bytes: 248500, sha256: "a".repeat(64), metadata: { title: paper.title, authors: ["Alex Researcher", "Sam Chen"] }, change_summary: number === 1 ? "Initial submission for conference review." : "Reduced page count and clarified the evaluation methodology in Section 4.", template_id: "systems-2026", latest_check: { status: "passed_with_warnings" } });
    const history = { current_revision_id: "r2", revisions: [revision(2), revision(1)], can_upload_revision: true, can_recheck: true };
    const reviewForm = { name: "Conference peer review", recommendations: ["Accept", "Reject", "Major revision"], criteria: [{ id: "quality", label: "Technical quality", kind: "score", minimum: 1, maximum: 5, required: true, visibility: "authors" }, { id: "summary", label: "Review summary", kind: "text", required: true, visibility: "authors" }] }; let ownReview = null;
    const workflow = { revision_id: "r2", status: "draft", eligible: true, reason: "The current revision satisfies the conference’s blocking formatting requirements.", formatting_gate: "block_errors", actions: ["submitted", "withdrawn"], is_chair: false, assignments: [], submission_window: { allowed: true, reason: "Paper submissions are open." } };
    const threads = [{ thread_id: "t1", revision_id: "r1", page_number: 3, visibility: "participants", resolved: false, can_resolve: true, comments: [{ comment_id: "c1", body: "Could you clarify how the evaluation handles missing research artifacts? A short example would help readers reproduce the experiment.", author_id: "Reviewer 1", author_role: "reviewer", created_at: "2026-10-18T14:30:00Z", version: 1, can_edit: false, can_delete: false }] }, { thread_id: "t2", revision_id: "r2", visibility: "participants", resolved: true, can_resolve: true, comments: [{ comment_id: "c2", body: "The updated revision addresses the page-limit warning. Thank you for including a clear change summary.", author_id: "Conference chair", author_role: "chair", created_at: "2026-10-19T09:00:00Z", version: 1, can_edit: false, can_delete: false }] }];
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request(); const path = new URL(request.url()).pathname.replace("/api/v1", ""), method = request.method(); calls.push({ path, method, body: request.postData() }); let data, status = 200;
      if (path === "/auth/me") data = { user_id: role, full_name: "Alex Researcher", email: "alex@example.test" };
      else if (path === "/notifications/count-unread") data = { count: 0 };
      else if (path === "/notifications/feed") data = { items: [], next_cursor: null };
      else if (path === "/submissions/paper-42") data = paper;
      else if (path.endsWith("/workflow")) data = workflow;
      else if (path.endsWith("/collaborators")) data = { submitter_id: "author", collaborators: [], can_manage: role !== "reviewer" };
      else if (path.endsWith("/metadata") && method === "GET") data = { enabled: true, paper_number: 42, can_edit: role === "author", metadata: { title: paper.title, abstract: paper.abstract, authors: paper.authors, version: 1, track_id: null, source: "declared" }, tracks: [], edit_window: {} };
      else if (path.endsWith("/metadata") && method === "PUT") { paper.title = request.postDataJSON().title; data = {}; }
      else if (path.endsWith("/revisions") && method === "GET") data = history;
      else if (path.endsWith("/revisions") && method === "POST") { if (failUpload) { status = 503; data = { detail: "Upload temporarily unavailable" }; } else { data = revision(3); history.revisions.unshift(data); history.current_revision_id = workflow.revision_id = "r3"; } }
      else if (path.endsWith("/checks")) data = [];
      else if (path.endsWith("/check-compliance")) data = {};
      else if (path.endsWith("/discussion")) data = { messages: [] };
      else if (path.endsWith("/conversation") && method === "GET") { if (failConversation) { status = 503; data = { detail: "Discussion temporarily unavailable" }; } else data = threads; }
      else if (path.endsWith("/conversation") && method === "POST") { const body = request.postDataJSON(); data = { thread_id: `t${threads.length + 1}`, ...body, resolved: false, can_resolve: true, comments: [{ ...threads[0].comments[0], comment_id: "new", body: body.body, author_id: "Author", author_role: "author", can_edit: true, can_delete: true }] }; threads.push(data); }
      else if (/\/conversation\/t\d+$/.test(path) && method === "PATCH") { const thread = threads.find((item) => path.endsWith(item.thread_id)); thread.resolved = request.postDataJSON().resolved; data = thread; }
      else if (path.endsWith("/transitions")) { paper.status = workflow.status = request.postDataJSON().target_status; workflow.actions = ["withdrawn"]; data = paper; }
      else if (path.endsWith("/reviews")) data = role === "reviewer" ? { is_chair: false, reviews: ownReview ? [ownReview] : [], assignment_id: "review-assignment", can_review: true, revision_id: history.current_revision_id, own_review: ownReview, configuration: { form_id: "review-form", form: reviewForm, policy: {} } } : { is_chair: false, reviews: [] };
      else if (path.endsWith("/reviews/mine") && method === "PUT") { const body = request.postDataJSON(); ownReview = { ...body, review_id: "review1", reviewer_id: "Reviewer", version: body.expected_version + 1, state: body.submit ? "submitted" : "draft", is_own: true, form: reviewForm }; data = ownReview; }
      else if (path.endsWith("/activity")) data = { events: [], next_before: null };
      else if (path.endsWith("/preview")) { status = 404; data = { detail: "Preview is unavailable for this synthetic fixture" }; }
      else if (path.endsWith("/file")) { await route.fulfill({ contentType: "application/pdf", body: "%PDF-synthetic-fixture" }); return; }
      else { unexpected.push(`${method} ${path}`); status = 404; data = { detail: "No fixture" }; }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    });
    async function capture(name) {
      await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo({ top: 0, behavior: "instant" }); }); await page.mouse.move(0, 0);
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name} overflow at ${width}px`);
      if ([1440, 390].includes(width) || name === "overview" || name === "conversation") await page.screenshot({ path: `${output}${name}-${width}.png`, fullPage: true });
    }
    async function goto(query = "") { await page.goto(`${base}/submissions/paper-42${query}`); await page.getByRole("button", { name: "Account menu", exact: true }).first().waitFor(); await page.getByRole("heading", { name: paper.title, exact: true }).waitFor(); }
    const nav = () => page.locator(".pf-paper-navigation");
    await goto(); await page.locator('[aria-label="Submission description"]').waitFor(); await page.getByRole("article").first().waitFor(); await capture("paper-landing");
    assert.equal(await page.getByRole("navigation", { name: "Submission sections", exact: true }).getByRole("link").count(), 4);
    const firstReply = page.locator(".pf-thread-reply").first(); assert.equal(await firstReply.getAttribute("open"), null);
    await page.getByRole("button", { name: "Reply to this comment", exact: true }).first().click(); assert.notEqual(await firstReply.getAttribute("open"), null);
    await goto("?tab=overview"); await page.getByRole("heading", { name: "Ready for the next review step", exact: true }).waitFor(); await capture("overview");
    await page.getByText("Edit paper details", { exact: true }).click(); await page.getByRole("textbox", { name: "Paper title", exact: true }).fill(paper.title + " — revised"); await page.getByRole("button", { name: "Save paper details", exact: true }).click(); await page.getByText("Paper details saved.", { exact: true }).waitFor();
    await page.getByRole("combobox", { name: "Action", exact: true }).selectOption("submitted"); await page.getByRole("button", { name: "Apply action", exact: true }).click(); await page.locator(".pf-paper-header .pf-state").filter({ hasText: "Submitted" }).waitFor();
    await nav().getByRole("link", { name: "Conversation", exact: true }).click(); await page.getByText("Please clarify", { exact: false }).count(); await page.getByRole("article").first().waitFor(); await capture("conversation");
    const filters = page.getByRole("group", { name: "Filter discussions", exact: true });
    await filters.getByRole("button", { name: /^Resolved/ }).click(); assert.equal(await page.getByRole("article").count(), 1);
    await filters.getByRole("button", { name: /^All/ }).click(); assert.equal(await page.getByRole("article").count(), 2);
    if (width <= 768) {
      const targets = await page.locator(".pf-discussion-filters button, .pf-paper-actions button, .pf-paper-sidebar button").evaluateAll((nodes) => nodes.map((node) => ({ label: node.textContent, height: node.getBoundingClientRect().height })));
      for (const target of targets) assert.ok(target.height >= 44, `Mobile target ${target.label} is ${target.height}px`);
    }
    await nav().getByRole("link", { name: "Conversation", exact: true }).focus(); assert.equal(await page.evaluate(() => document.activeElement.getAttribute("aria-current")), "page");
    await page.getByRole("button", { name: "Resolve thread", exact: true }).first().click(); await page.getByRole("article", { name: "Resolved discussion", exact: true }).first().waitFor(); await page.getByRole("button", { name: "Reopen thread", exact: true }).first().click();
    const composer = page.locator(".pf-conversation-composer"); await composer.getByRole("textbox", { name: "Comment", exact: true }).fill("We have clarified the missing-artifact case in the updated evaluation."); await composer.locator(".pf-composer-settings > summary").click(); await composer.getByRole("combobox", { name: "Document reference", exact: true }).selectOption("r1"); await composer.getByRole("spinbutton", { name: "Page number (optional)", exact: true }).fill("3"); await composer.getByRole("button", { name: "Post comment", exact: true }).click(); await page.getByText("We have clarified the missing-artifact case in the updated evaluation.", { exact: true }).waitFor();
    const anchor = calls.find((call) => call.path.endsWith("/conversation") && call.method === "POST"); assert.equal(JSON.parse(anchor.body).revision_id, "r1");
    await goto("?tab=conversation&revision=r1&page=3&run=older&compare_base=r1"); await page.getByText(/Earlier upload/).waitFor(); await capture("historical");
    await nav().getByRole("link", { name: "Overview", exact: true }).click(); assert.equal(new URL(page.url()).searchParams.get("run"), "older"); await page.getByRole("button", { name: "View current revision", exact: true }).click(); assert.equal(new URL(page.url()).searchParams.get("revision"), "r2"); assert.equal(new URL(page.url()).searchParams.has("run"), false);
    await page.getByRole("button", { name: "Upload revision", exact: true }).click(); const downloadPromise = page.waitForEvent("download"); await page.getByRole("button", { name: "Download research-paper-v2.pdf", exact: true }).click(); assert.equal((await downloadPromise).suggestedFilename(), "research-paper-v2.pdf");
    await page.getByLabel("Revised paper", { exact: true }).setInputFiles({ name: "revision.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-synthetic") }); await page.getByRole("textbox", { name: "Change summary", exact: true }).fill("Clarified evaluation and reduced page count.");
    failUpload = true; await page.getByRole("button", { name: "Upload new revision", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "Upload temporarily unavailable" }).waitFor(); failUpload = false; await page.getByRole("button", { name: "Upload new revision", exact: true }).click(); await page.getByRole("heading", { name: "Formatting checks · Revision 3", exact: true }).waitFor(); assert.equal(new URL(page.url()).searchParams.get("revision"), "r3");
    const uploads = calls.filter((call) => call.path.endsWith("/revisions") && call.method === "POST"); assert.equal(uploads.length, 2); const requestKey = (body) => body.match(/name="request_key"\r\n\r\n([^\r]+)/)[1]; assert.equal(requestKey(uploads[0].body), requestKey(uploads[1].body));
    await nav().getByRole("link", { name: "Reviews", exact: true }).click(); await page.getByText(/No reviews are visible/).waitFor();
    await nav().getByRole("link", { name: "Activity", exact: true }).click(); await page.getByText("No collaboration events recorded yet.", { exact: true }).waitFor();
    await page.getByRole("button", { name: "View document", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "Preview is unavailable for this synthetic fixture" }).waitFor(); await page.getByRole("button", { name: "Retry PDF preview", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "Preview is unavailable for this synthetic fixture" }).waitFor(); await capture("document-fallback");
    failConversation = true; await goto("?tab=conversation"); await page.getByRole("alert").filter({ hasText: "Discussion temporarily unavailable" }).waitFor(); await capture("conversation-error"); failConversation = false; await page.getByRole("button", { name: "Retry conversation", exact: true }).click(); await page.getByRole("article").first().waitFor();
    workflow.is_chair = true; role = "chair"; workflow.assignments = [{ assignment_id: "a1", reviewer_id: "Reviewer account", status: "accepted" }]; await goto("?tab=conversation"); await composer.locator(".pf-composer-settings > summary").click(); await composer.getByRole("combobox", { name: "Visibility", exact: true }).selectOption("chairs"); await page.getByText("This discussion will be visible to chairs only.", { exact: true }).waitFor(); await capture("chair-conversation");
    workflow.is_chair = false; workflow.actions = []; history.can_upload_revision = history.can_recheck = false; role = "reviewer"; paper.authors = [];
    for (const thread of threads) { thread.can_resolve = false; for (const comment of thread.comments) comment.can_edit = comment.can_delete = false; }
    await goto("?tab=conversation"); assert.equal(await page.getByRole("button", { name: "Upload revision", exact: true }).count(), 0); assert.equal(await page.getByRole("heading", { name: "Reviewer assignments", exact: true }).count(), 0); assert.equal(await composer.getByRole("combobox", { name: "Visibility", exact: true }).count(), 0); assert.equal(await page.getByRole("button", { name: "Edit", exact: true }).count(), 0); await capture("reviewer-conversation");
    await page.getByRole("button", { name: "Switch to dark mode", exact: true }).click(); await capture("conversation-dark");
    paper.status = workflow.status = "under_review"; await goto("?tab=reviews"); await page.getByRole("heading", { name: "Your review · Conference peer review", exact: true }).waitFor(); await capture("review-form-dark");
    await page.getByRole("button", { name: "Switch to light mode", exact: true }).click(); await capture("review-form");
    await page.getByRole("combobox", { name: "Overall recommendation", exact: true }).selectOption("Accept");
    await page.getByRole("spinbutton", { name: /Technical quality/ }).fill("4"); await page.getByRole("textbox", { name: /Review summary/ }).fill("The evaluation is reproducible and the methodology is clearly explained.");
    await page.getByRole("textbox", { name: "Confidential comments for chairs", exact: true }).fill("Private reviewer note for the chair."); await page.getByRole("button", { name: "Save private draft", exact: true }).click();
    await page.getByText(/Version 1 · draft/).first().waitFor(); assert.equal(ownReview.revision_id, history.current_revision_id); assert.equal(ownReview.submit, false); assert.equal(ownReview.answers.quality, 4);
    await page.getByRole("combobox", { name: "Viewing revision", exact: true }).selectOption("r1"); await page.getByText("You are viewing an earlier paper revision. Select the current revision before writing a review.", { exact: true }).waitFor(); assert.equal(await page.getByRole("button", { name: "Save private draft", exact: true }).isDisabled(), true);
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []); console.log(`OK ${width}px: overview, metadata, status, threads/anchors, revision links, download, upload retry/idempotency, checks/reviews/activity, roles, errors and dark mode`); await context.close();
  }
} finally { await browser.close(); }
