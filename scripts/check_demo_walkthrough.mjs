/** Read-only walkthrough QA against the real local demo; only signs in/out. */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
const state = JSON.parse(await readFile(new URL("../backend/data/demo-walkthrough.json", import.meta.url), "utf8"));
const { chromium } = await import(process.env.PAPER_BROWSER_MODULE || "playwright-core");
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", headless: true });
const base = state.ui_base;
try {
  for (const role of ["chair", "author", "reviewer"]) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage(); page.setDefaultTimeout(15000);
    const errors = []; page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(base + "/login");
    await page.getByRole("textbox", { name: "Email", exact: true }).fill(state.accounts[role].email);
    await page.getByLabel("Password", { exact: true }).fill(state.accounts[role].password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL("**/dashboard");
    const paper = state.papers.workspace.id;
    await page.goto(`${base}/submissions/${paper}?tab=conversation`);
    await page.getByRole("heading", { name: state.papers.workspace.title, exact: true }).waitFor();
    await page.getByText("The revised paper now fits the page limit. Could you expand the explanation of missing artifacts in Section 3?", { exact: true }).waitFor();
    const confidential = page.getByText("Demo chair-only note: coordinate reviewers here. This thread must not appear for the author or reviewer account.", { exact: true });
    if (role === "chair") await confidential.waitFor(); else assert.equal(await confidential.count(), 0);
    const sections = page.getByRole("navigation", { name: "Submission sections", exact: true });
    await sections.getByRole("link", { name: "Document", exact: true }).click();
    await page.getByRole("combobox", { name: /Viewing revision/ }).waitFor();
    await page.locator("iframe").waitFor();
    assert.match(await page.locator("iframe").getAttribute("src"), /^blob:/);
    assert.match(await page.locator("iframe").getAttribute("title"), /revision 2, page 1/);
    await sections.getByRole("link", { name: "Reviews", exact: true }).click();
    await page.getByRole("heading", { name: "Formal reviews", exact: true }).waitFor();
    if (role === "reviewer") await page.getByRole("button", { name: "Save private draft", exact: true }).waitFor();
    if (role === "author") {
      await page.getByText(/No reviews are visible to you yet/).waitFor();
      await page.goto(`${base}/submissions/${state.papers.accepted.id}?tab=reviews`);
      await page.getByRole("heading", { name: /Conference decision: accepted/ }).waitFor();
      await page.getByText("Clear motivation and useful revision history.", { exact: true }).waitFor();
      assert.equal(await page.getByText("Synthetic confidential review note for chairs. Not visible to authors.", { exact: true }).count(), 0);
    }
    assert.deepEqual(errors, []);
    console.log(`OK real ${role} browser login, paper access, private PDF preview, reviews and confidential visibility`);
    await context.close();
  }
} finally { await browser.close(); }
