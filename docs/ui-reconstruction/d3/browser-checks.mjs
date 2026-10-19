/** D3 visual QA. Every API request is intercepted; no real accounts or writes. */
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const { chromium } = await import(process.env.PAPER_BROWSER_MODULE || "playwright-core");
const output = fileURLToPath(new URL("./screenshots/", import.meta.url)); await mkdir(output, { recursive: true });
const base = process.env.PAPER_UI_BASE_URL || "http://127.0.0.1:5174";
const browser = await chromium.launch({ executablePath: process.env.PAPER_BROWSER_PATH || "/usr/bin/chromium", headless: true });
const stamp = "2026-10-19T08:00:00Z";
try {
  for (const width of [1440, 1024, 768, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    const page = await context.newPage(); page.setDefaultTimeout(12000);
    const unexpected = [], errors = [], calls = []; let chair = false, failReports = false, failComments = false, failPost = false, denyPatch = false;
    page.on("pageerror", (error) => errors.push(error.message));
    const results = [
      { id: "page-limit", name: "Page limit", category: "page", status: "failed", severity: "blocking", expected: "At most 8 pages", actual: "10 pages", confidence: "high", advice: "Reduce the paper to the conference page limit, keeping the required sections.", evidence: "The PDF contains 10 pages." },
      { id: "margins", name: "Page margins", category: "layout", status: "passed", severity: "warning", expected: "At least 20 mm", actual: "20 mm", confidence: "high" },
      { id: "spacing", name: "Paragraph spacing", category: "paragraph", status: "not_applicable", severity: "warning", expected: "Single spacing", actual: null, confidence: "low", advice: "This property cannot be measured reliably for this file type." },
      { id: "title", name: "Required title", category: "document", status: "missing", severity: "warning", expected: "A declared document title", actual: null, advice: "Include a title in the source document." },
      { id: "policy", name: "Allowed file format", category: "policy", status: "passed", severity: "blocking", expected: "PDF", actual: "PDF", confidence: "high" },
    ];
    const assessment = { filename: "research-paper-v1.pdf", format: "pdf", verdict: "rejected", score: 50, passed: 2, failed: 1, missing: 1, not_applicable: 1, results, metadata: { title: "Towards reproducible scientific workflows", authors: [] } };
    const runs = [{ run_id: "run2", revision_id: "r1", sequence: 2, status: "unable_to_validate", created_at: stamp, error: "This validation run could not parse the saved document. Previous reports remain available.", assessment: null, issues: [], engine_version: "1" }, { run_id: "run1", revision_id: "r1", sequence: 1, status: "failed", created_at: stamp, assessment, issues: [{ issue_id: "i1", rule_id: "page-limit" }], engine_version: "1" }];
    const history = { current_revision_id: "r2", can_upload_revision: true, can_recheck: true, revisions: [2, 1].map((number) => ({ revision_id: `r${number}`, number, filename: `research-paper-v${number}.pdf`, uploaded_at: stamp, uploaded_by: "Author", size_bytes: 250000, template_id: "conference-template-v1", latest_check: { status: "failed" } })) };
    const issues = [{ issue_id: "i1", submission_id: "paper", title: "Page limit exceeded", description: "The paper exceeds the conference’s maximum page count.", category: "page", severity: "blocking", status: "open", expected: "8 pages", actual: "10 pages", advice: "Shorten the evaluation or move supporting material to an allowed appendix.", evidence: "10 pages extracted from the PDF.", revision_id: "r1", check_run_id: "run1", check_result_id: "page-limit", assignee_id: null, created_at: stamp, updated_at: stamp }, { issue_id: "i2", submission_id: "paper", title: "Author metadata missing", description: "Author metadata was unavailable in this upload.", category: "document", severity: "warning", status: "resolved", check_result_id: "authors", revision_id: "r2", check_run_id: "run3", created_at: stamp, updated_at: stamp }];
    const comments = [{ comment_id: "c1", author_id: "Reviewer", text: "Please keep the methodology section and shorten the supporting examples.", created_at: stamp }];
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request(); const path = new URL(request.url()).pathname.replace("/api/v1", ""), method = request.method(); calls.push({ path, method, body: request.postData() }); let data, status = 200;
      if (path === "/auth/me") data = { user_id: chair ? "chair" : "author", full_name: "Demo Researcher", email: "researcher@example.test" };
      else if (path === "/notifications/count-unread") data = { count: 0 };
      else if (path === "/notifications/feed") data = { items: [], next_cursor: null };
      else if (path === "/submissions/paper") data = { submission_id: "paper", conference_id: "demo", paper_number: 42, title: assessment.metadata.title, status: "changes_requested", authors: [], filename: assessment.filename };
      else if (path.endsWith("/workflow")) data = { is_chair: chair, status: "changes_requested", eligible: false, reason: "Blocking formatting issues remain.", assignments: [], actions: [] };
      else if (path.endsWith("/revisions")) data = history;
      else if (path.endsWith("/checks")) { if (failReports) { status = 503; data = { detail: "Saved reports temporarily unavailable" }; } else data = path.includes("/r1/") ? runs : []; }
      else if (path.endsWith("/check-compliance")) { await new Promise((resolve) => setTimeout(resolve, 400)); data = runs[0]; }
      else if (path === "/submissions/paper/issues") data = issues;
      else if (path === "/issues/i1/comments" && method === "GET") { if (failComments) { status = 503; data = { detail: "Issue comments temporarily unavailable" }; } else data = comments; }
      else if (path === "/issues/i1/comments" && method === "POST") { if (failPost) { status = 503; data = { detail: "Could not save this comment" }; } else { data = { comment_id: "c2", author_id: "author", text: request.postDataJSON().text, created_at: stamp }; comments.push(data); } }
      else if (path === "/issues/i1" && method === "GET") data = issues[0];
      else if (path === "/issues/i1" && method === "PATCH") { if (denyPatch) { status = 403; data = { detail: "Issue editing permission required" }; } else { Object.assign(issues[0], request.postDataJSON()); data = issues[0]; } }
      else { unexpected.push(`${method} ${path}`); status = 404; data = { detail: "Missing fixture" }; }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    });
    async function goto(path) { await page.goto(base + path); await page.getByRole("button", { name: "Account menu", exact: true }).first().waitFor(); }
    async function capture(name) {
      await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo({ top: 0, behavior: "instant" }); }); await page.mouse.move(0, 0);
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name} overflow at ${width}px`);
      if ([1440, 390].includes(width) || ["checks", "issues"].includes(name)) await page.screenshot({ path: `${output}${name}-${width}.png`, fullPage: true });
    }
    await goto("/submissions/paper?tab=checks&revision=r1&run=run1"); await page.locator(".pf-check-summary").waitFor();
    await page.locator(".pf-finding > summary").filter({ hasText: "Page limit" }).click(); await capture("checks");
    const suite = page.locator(".pf-check-suite").first(); await suite.locator(":scope > summary").focus(); await page.keyboard.press("Enter"); assert.equal(await suite.getAttribute("open"), null); await page.keyboard.press("Enter"); assert.notEqual(await suite.getAttribute("open"), null);
    assert.match(await page.locator(".pf-check-totals").textContent(), /2 passed.*1 failed.*1 missing.*1 not evaluated/);
    await page.getByRole("combobox", { name: "Check status", exact: true }).selectOption("attention"); assert.equal(await page.locator(".pf-finding").count(), 2);
    await page.getByRole("searchbox", { name: "Search checks", exact: true }).fill("page-limit"); assert.equal(await page.locator(".pf-finding").count(), 1);
    await page.locator(".pf-finding-body").getByRole("link", { name: "Open tracked issue →", exact: true }).click(); await page.getByRole("heading", { name: "Page limit exceeded", exact: true }).waitFor(); await page.getByText(comments[0].text, { exact: true }).waitFor(); await capture("issue-detail");
    assert.equal(await page.getByRole("textbox", { name: "Assignee account ID", exact: true }).count(), 0);
    const draft = page.getByRole("textbox", { name: "Issue comment", exact: true }); await draft.fill("We have reduced the paper to eight pages."); failPost = true; await page.getByRole("button", { name: "Add comment", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "Could not save" }).waitFor(); assert.equal(await draft.inputValue(), "We have reduced the paper to eight pages."); failPost = false; await page.getByRole("button", { name: "Add comment", exact: true }).click(); await page.getByText("Comment added.", { exact: true }).waitFor(); assert.equal(await draft.inputValue(), "");
    denyPatch = true; await page.getByRole("combobox", { name: "Status", exact: true }).selectOption("resolved"); await page.getByRole("button", { name: "Save changes", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "permission required" }).waitFor(); assert.equal(await page.getByRole("combobox", { name: "Status", exact: true }).inputValue(), "resolved"); denyPatch = false; await page.getByRole("button", { name: "Save changes", exact: true }).click(); await page.getByText("Issue updated.", { exact: true }).waitFor(); assert.deepEqual(JSON.parse(calls.filter((call) => call.method === "PATCH").at(-1).body), { status: "resolved" });
    const origin = page.getByRole("link", { name: "View original revision and formatting report →", exact: true }); assert.match(await origin.getAttribute("href"), /revision=r1&tab=checks&run=run1/);
    await page.getByRole("link", { name: "All issues", exact: true }).click(); await page.locator(".pf-issue-list li").first().waitFor(); await capture("issues");
    const issueLink = page.getByRole("link", { name: "Page limit exceeded", exact: true }); await issueLink.focus(); await page.keyboard.press("Enter"); await page.getByRole("heading", { name: "Page limit exceeded", exact: true }).waitFor();
    await goto("/issues/paper?revision=r1&run=run1"); await page.getByRole("heading", { name: "1 matching issues", exact: true }).waitFor(); await page.getByRole("button", { name: "Show all revisions", exact: true }).click(); await page.getByRole("heading", { name: "2 matching issues", exact: true }).waitFor(); await page.getByRole("searchbox", { name: "Search issues", exact: true }).fill("unmatched"); await page.getByRole("heading", { name: "No issues match these filters", exact: true }).waitFor(); await capture("issues-filter-empty");
    chair = true; await goto("/issues/paper?issue=i1"); const assignee = page.getByRole("textbox", { name: "Assignee account ID", exact: true }); await assignee.fill("author-account"); await page.getByRole("button", { name: "Save changes", exact: true }).click(); await page.getByText("Issue updated.", { exact: true }).waitFor(); assert.equal(JSON.parse(calls.filter((call) => call.method === "PATCH").at(-1).body).assignee_id, "author-account"); await capture("chair-issue");
    failComments = true; await goto("/issues/paper?issue=i1"); await page.getByRole("alert").filter({ hasText: "comments temporarily unavailable" }).waitFor(); failComments = false; await page.getByRole("button", { name: "Retry issue comments", exact: true }).click(); await page.getByText(comments[0].text, { exact: true }).waitFor();
    await goto("/submissions/paper?tab=checks&revision=r1&run=run2"); await page.getByText(/This validation run could not parse/).waitFor(); assert.equal(await page.locator(".pf-check-suites").count(), 0); await capture("unable-to-validate");
    await page.getByRole("combobox", { name: "Saved report", exact: true }).selectOption("run1"); await page.locator(".pf-check-suites").waitFor(); assert.equal(new URL(page.url()).searchParams.get("run"), "run1");
    await page.getByRole("button", { name: "Run checks again", exact: true }).click(); await page.getByRole("status").filter({ hasText: "Processing this revision" }).waitFor(); assert.equal(JSON.parse(calls.find((call) => call.method === "POST" && call.path.endsWith("/check-compliance")).body).revision_id, "r1"); await page.getByRole("button", { name: "Run checks again", exact: true }).waitFor();
    failReports = true; await goto("/submissions/paper?tab=checks&revision=r1"); await page.getByRole("alert").filter({ hasText: "Saved reports temporarily unavailable" }).waitFor(); await capture("checks-load-error"); failReports = false; await page.getByRole("button", { name: "Retry saved reports", exact: true }).click(); await page.locator(".pf-check-summary").waitFor();
    await goto("/submissions/paper?tab=checks&revision=r1&run=unknown"); await page.getByRole("heading", { name: "Saved report unavailable", exact: true }).waitFor(); assert.equal(await page.locator(".pf-check-summary").count(), 0);
    await page.getByRole("link", { name: "View latest saved report", exact: true }).click(); await page.locator(".pf-check-summary").waitFor(); await page.getByRole("combobox", { name: "Saved report", exact: true }).selectOption("run1");
    await page.getByRole("button", { name: "Switch to dark mode", exact: true }).click(); await capture("checks-dark");
    if (width <= 768) { const heights = await page.locator(".pf-checks button,.pf-checks select,.pf-checks summary,.pf-checks a").evaluateAll((nodes) => nodes.filter((node) => node.checkVisibility()).map((node) => node.getBoundingClientRect().height)); for (const height of heights) assert.ok(height >= 44, `Mobile check target is ${height}px`); }
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []); console.log(`OK ${width}px: saved runs, categories, filters, exact origins, comments/retry, permission errors, assignments, check retry, keyboard navigation, dark theme and overflow`); await context.close();
  }
} finally { await browser.close(); }
