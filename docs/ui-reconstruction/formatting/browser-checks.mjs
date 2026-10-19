import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { emptyRuleSet } from "../../../frontend/src/lib/ruleOptions.js";
// Test-only fixtures: all API requests are intercepted, including uploads/deletes.
const { chromium } = await import(process.env.PAPER_BROWSER_MODULE || "playwright-core");
const base = process.env.PAPER_UI_BASE_URL || "http://127.0.0.1:5174";
const output = fileURLToPath(new URL("./screenshots/", import.meta.url)); await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.PAPER_BROWSER_PATH || "/usr/bin/chromium", headless: true });
const check = { id: "page-limit", category: "page", name: "Maximum page count", status: "failed", severity: "blocking", expected: 8, actual: 10, advice: "Reduce the document to the configured page limit.", confidence: "high" };
const passedCheck = { id: "title", category: "structure", name: "Document title", status: "passed", severity: "warning", expected: "Present", actual: "Present", confidence: "high" };
const paper = { filename: "research-paper.pdf", format: "pdf", verdict: "rejected", score: 50, passed: 1, failed: 1, missing: 0, results: [check, passedCheck], metadata: { title: "Towards reproducible scientific workflows", authors: ["Alex Researcher", "Sam Chen"] }, action_required: "Resolve the blocking page-limit issue." };
const batch = { template_name: "Research Systems Rules", source: "files", accepted: 1, needs_review: 0, rejected: 1, papers: [paper, { ...paper, filename: "short-paper.tex", verdict: "accepted", score: 100, failed: 0, passed: 1, action_required: null, results: [passedCheck] }] };
const single = { ...paper, filename: "research-paper.pdf", paper_format: "pdf", score: 50, results: [check, passedCheck] };
try {
  for (const width of [1440, 1024, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    const page = await context.newPage(); page.setDefaultTimeout(10000);
    page.on("dialog", (dialog) => dialog.accept());
    let templates = [{ ...emptyRuleSet(), template_id: "rules", name: "Research Systems Rules" }];
    let reports = [{ filename: "batch.json", paper_title: "Batch formatting report", authors: ["Alex Researcher"], template_name: "Research Systems Rules", format: "pdf", verdict: "rejected", score: 50, updated_at: "2026-10-19T12:00:00Z" }, { filename: "single.json", paper_title: "Single document comparison", format: "pdf", verdict: "accepted", score: 100, updated_at: "2026-10-18T12:00:00Z" }];
    let failReports = false, failDelete = false, failDiff = false; const calls = [], errors = [], unexpected = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request(); const path = new URL(request.url()).pathname.replace("/api/v1", ""); const method = request.method();
      calls.push({ path, method, body: request.postData() }); let status = 200, data;
      if (path === "/auth/me") data = { user_id: "qa", full_name: "Alex Researcher", email: "alex@example.test" };
      else if (path === "/notifications/count-unread") data = { count: 0 };
      else if (path === "/notifications/feed") data = { items: [], next_cursor: null };
      else if (path === "/templates" && method === "GET") data = { templates };
      else if (path === "/templates" && method === "POST") { data = { ...request.postDataJSON(), template_id: "new-rules" }; templates.push(data); }
      else if (path === "/templates/import") data = { ...emptyRuleSet(), name: "Imported venue rules", template_id: "" };
      else if (path.startsWith("/templates/")) { const id = path.split("/").at(-1); if (method === "DELETE") { templates = templates.filter((item) => item.template_id !== id); data = {}; } else if (method === "PUT") { data = { ...request.postDataJSON(), template_id: id }; templates = templates.map((item) => item.template_id === id ? data : item); } else data = templates.find((item) => item.template_id === id); }
      else if (path === "/conferences/") data = [{ conference_id: "demo", name: "Research Systems Conference" }];
      else if (path === "/conferences/demo") data = { conference_id: "demo", name: "Research Systems Conference", members: [{ user_id: "qa", role: "owner" }] };
      else if (path === "/conferences/demo/templates") data = [["version-new", "New rules", "2026-10-19T12:00:00Z"], ["version-old", "Earlier rules", "2026-10-18T12:00:00Z"]];
      else if (path === "/conferences/demo/templates/diff") { if (failDiff) { status = 503; data = { detail: "Comparison temporarily unavailable" }; } else data = { diff: { pages: { changed: { max_pages: [8, 10] }, added: {}, removed: {}, unchanged: {} }, sections: { changed: {}, added: { required: ["Abstract"] }, removed: {}, unchanged: {} }, _meta: { name: ["Earlier rules", "New rules"] } } }; }
      else if (path.startsWith("/conferences/demo/templates/")) data = { ...templates[0], template_id: path.split("/").at(-1) };
      else if (path === "/drive/status") data = { configured: false, mode: "disabled" };
      else if (path === "/submissions") data = batch;
      else if (path === "/compare") data = single;
      else if (path === "/reports") { if (failReports) { status = 503; data = { detail: "Report history unavailable" }; } else data = { reports }; }
      else if (path.startsWith("/reports/") && method === "DELETE") { if (failDelete) { status = 503; data = { detail: "Report deletion unavailable" }; } else { reports = reports.filter((item) => item.filename !== path.split("/").at(-1)); data = {}; } }
      else if (path.startsWith("/reports/")) data = path.endsWith("batch.json") ? batch : single;
      else { unexpected.push(`${method} ${path}`); status = 404; data = { detail: "No fixture" }; }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    });
    async function capture(name) { await page.mouse.move(0, 0); assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name} overflow at ${width}px`); if (width === 1440 || width === 390) await page.screenshot({ path: `${output}${name}-${width}.png`, fullPage: true }); }
    // Auth resolution keys the workspace by account; interact after it settles.
    async function goto(path) { await page.goto(base + path); await page.getByRole("button", { name: "Account menu", exact: true }).first().waitFor(); }
    await page.goto(base + "/submit"); await page.getByRole("combobox", { name: /Select template/ }).waitFor(); await page.waitForFunction(() => document.querySelector('select').value === 'rules'); await capture("check-papers");
    await page.getByRole("radio", { name: "Google Drive folder", exact: true }).click(); await page.getByText("Google Drive is not connected", { exact: true }).waitFor(); await capture("drive-unavailable"); await page.getByRole("radio", { name: "Upload files", exact: true }).click();
    await page.locator('input[type="file"]').setInputFiles([{ name: "research-paper.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-synthetic-QA") }, { name: "short-paper.tex", mimeType: "text/plain", buffer: Buffer.from("Synthetic LaTeX QA fixture") }]);
    await page.getByRole("button", { name: "Check 2 papers", exact: true }).click(); await page.getByRole("heading", { name: "Formatting results", exact: true }).waitFor(); await page.getByText("Maximum page count", { exact: true }).first().waitFor(); await capture("batch-results");
    await page.locator(".pf-formatting-paper").first().getByText("Show all 2 checks", { exact: true }).click(); await capture("formatting-findings");
    assert.ok(calls.find((call) => call.path === "/submissions").body.includes('name="template_id"'));
    await goto("/compare"); const inputs = page.locator('input[type="file"]'); await inputs.nth(0).setInputFiles({ name: "template.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: Buffer.from("Synthetic template") }); await inputs.nth(1).setInputFiles({ name: "research-paper.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-synthetic") }); await capture("compare-documents");
    await page.getByRole("button", { name: "Compare documents", exact: true }).click(); await page.getByRole("heading", { name: "Overall compliance: 50%", exact: true }).waitFor(); await capture("single-result"); assert.ok(calls.find((call) => call.path === "/compare").body.includes('name="template"'));
    await page.goto(base + "/setup"); await page.getByRole("button", { name: "Load", exact: true }).click(); await page.getByPlaceholder("e.g., IEEE Conference Template").fill("Updated research rules"); await page.getByRole("button", { name: "Save changes", exact: true }).click(); await page.getByText('Saved "Updated research rules". Authors will be checked against these rules.', { exact: true }).waitFor(); await capture("template-setup");
    await page.locator('input[type="file"]').setInputFiles({ name: "template.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: Buffer.from("Synthetic template") }); await page.getByRole("button", { name: "Import rules", exact: true }).click(); await page.getByRole("button", { name: "Save template", exact: true }).click(); await page.getByText('Saved "Imported venue rules". Authors will be checked against these rules.', { exact: true }).waitFor(); assert.ok(calls.some((call) => call.path === "/templates" && call.method === "POST"));
    await page.goto(base + "/reports"); await page.getByRole("button", { name: "Batch formatting report", exact: true }).waitFor(); await capture("saved-reports");
    await page.getByRole("searchbox", { name: "Search reports", exact: true }).fill("missing"); await page.getByRole("heading", { name: "No matching reports", exact: true }).waitFor(); await page.getByRole("button", { name: "Clear report filters", exact: true }).click();
    await page.getByRole("combobox", { name: "Filter report result", exact: true }).selectOption("accepted"); assert.equal(await page.locator(".pf-format-report-row").count(), 1); await page.getByRole("combobox", { name: "Filter report result", exact: true }).selectOption("");
    failDelete = true; await page.getByRole("button", { name: "Delete report Single document comparison", exact: true }).click(); await page.getByRole("alert").filter({ hasText: "Report deletion unavailable" }).waitFor(); assert.equal(await page.locator(".pf-format-report-row").count(), 2); failDelete = false; await page.getByRole("button", { name: "Delete report Single document comparison", exact: true }).click(); await page.waitForFunction(() => document.querySelectorAll('.pf-format-report-row').length === 1);
    await page.getByRole("button", { name: "Batch formatting report", exact: true }).focus(); await page.keyboard.press("Enter"); await page.getByRole("heading", { name: "Formatting results", exact: true }).waitFor(); assert.equal(new URL(page.url()).pathname, "/results");
    failReports = true; await page.goto(base + "/reports"); await page.getByRole("alert").filter({ hasText: "Report history unavailable" }).waitFor(); failReports = false; await page.getByRole("button", { name: "Retry reports", exact: true }).click(); await page.getByRole("button", { name: "Batch formatting report", exact: true }).waitFor();
    await page.getByRole("button", { name: "Switch to dark mode", exact: true }).click(); await capture("saved-reports-dark");
    await page.goto(base + "/results"); await page.getByRole("heading", { name: "No report yet", exact: true }).waitFor(); await capture("no-report");
    await goto("/conferences/demo/latest"); await page.getByText("View published rules", { exact: true }).click(); await page.getByPlaceholder("e.g., IEEE Conference Template").waitFor(); await capture("conference-templates");
    failDiff = true; await goto("/conferences/demo/diff?old=version-old&new=version-new"); await page.getByRole("alert").filter({ hasText: "Comparison temporarily unavailable" }).waitFor(); failDiff = false; await page.getByRole("button", { name: "Retry comparison", exact: true }).click(); await page.getByRole("heading", { name: "Pages", exact: false }).waitFor(); await capture("template-comparison");
    assert.ok(calls.some((call) => call.path === "/conferences/demo/templates/diff" && JSON.parse(call.body).old_template_id === "version-old"));
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []);
    console.log(`OK ${width}px: upload, Drive fallback, comparison, reports/checks, template import/save, search, keyboard open and delete/retry`);
    await context.close();
  }
} finally { await browser.close(); }
