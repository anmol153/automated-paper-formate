/** D3: isolated API-contract/interaction tests. Never connects to the real backend. */
import assert from "node:assert/strict";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";
import { JSDOM } from "jsdom";
import { AxiosError } from "axios";
const dom = new JSDOM("<!doctype html><body></body>", { url: "http://localhost:5173/", pretendToBeVisual: true });
for (const key of ["window", "document", "navigator", "localStorage", "HTMLElement", "Element", "Node", "Event", "FormData", "MouseEvent"]) Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const React = await import("react"); const { act } = React;
const { createRoot } = await import("react-dom/client");
const { MemoryRouter, Routes, Route, useLocation, useNavigate } = await import("react-router-dom");
const server = await createServer({ configFile: false, root: ".", appType: "custom", plugins: [react()], server: { middlewareMode: true, hmr: false }, define: { "import.meta.env.VITE_API_BASE": JSON.stringify("http://api.test/api/v1") }, ssr: { external: ["react", "react-dom", "react-dom/client", "react-router-dom"] } });
const { api } = await server.ssrLoadModule("./src/lib/api.js");
const { AuthProvider } = await server.ssrLoadModule("./src/context/AuthContext.jsx");
const Issues = (await server.ssrLoadModule("./src/pages/Issues.jsx")).default;
const PaperChecks = (await server.ssrLoadModule("./src/components/PaperChecks.jsx")).default;
let calls, rows, comments, chair, failList, failComments, failPatch, failPost, failPermission, lateDetail;
const stamp = "2026-10-19T08:00:00Z";
function reset() {
  calls = []; chair = failList = failComments = failPatch = failPost = failPermission = false; lateDetail = null;
  rows = [{ issue_id: "i1", submission_id: "paper", title: "Page limit exceeded", description: "The document exceeds the configured limit.", severity: "blocking", status: "open", category: "page", expected: "8", actual: "10", advice: "Reduce the paper to eight pages.", evidence: "10 pages extracted", check_result_id: "page-limit", revision_id: "r1", check_run_id: "run1", assignee_id: null, created_at: stamp, updated_at: stamp }, { issue_id: "i2", submission_id: "paper", title: "Title metadata missing", description: "Supply a title.", severity: "warning", status: "resolved", category: "document", check_result_id: "title", revision_id: "r2", check_run_id: "run2", created_at: stamp, updated_at: stamp }];
  comments = [{ comment_id: "c1", author_id: "Reviewer", text: "Please shorten the evaluation section.", created_at: stamp }];
}
function reject(config, message, status = 503) { throw new AxiosError(message, "ERR_BAD_RESPONSE", config, null, { config, status, data: { detail: message }, headers: {} }); }
api.defaults.adapter = async (config) => {
  calls.push(config); const path = config.url; let data;
  if (path === "/auth/me") data = { user_id: "author", full_name: "Test author" };
  else if (path.endsWith("/workflow")) { if (failPermission) reject(config, "Permissions unavailable"); data = { is_chair: chair }; }
  else if (path === "/submissions/paper/issues") { if (failList) reject(config, "Issue list unavailable"); data = rows; }
  else if (path.endsWith("/comments") && config.method === "get") { if (failComments) reject(config, "Comments unavailable"); data = comments; }
  else if (path.endsWith("/comments") && config.method === "post") { if (failPost) reject(config, "Comment unavailable"); data = { comment_id: "c2", text: JSON.parse(config.data).text, author_id: "author", created_at: stamp }; comments.push(data); }
  else if (path.startsWith("/issues/") && config.method === "patch") { if (failPatch) reject(config, "Issue editing permission required", 403); const issue = rows.find((row) => path.endsWith(row.issue_id)); Object.assign(issue, JSON.parse(config.data)); data = issue; }
  else if (path.startsWith("/issues/")) { if (lateDetail && path === "/issues/i1") return lateDetail(config); data = rows.find((row) => path.endsWith(row.issue_id)); if (!data) reject(config, "Issue not found", 404); }
  else throw new Error(`Unexpected ${config.method} ${path}`);
  return { data: structuredClone(data), config, headers: {}, status: 200, statusText: "OK" };
};
async function flush() { for (let i = 0; i < 4; i++) await act(async () => { await new Promise((resolve) => setTimeout(resolve, 5)); }); }
async function mount(query = "", checkProps = null) {
  const container = document.createElement("div"); document.body.appendChild(container); const root = createRoot(container); let location, navigate;
  function Probe() { location = useLocation(); navigate = useNavigate(); return null; }
  const page = checkProps ? React.createElement(PaperChecks, checkProps) : React.createElement(Issues);
  await act(async () => root.render(React.createElement(AuthProvider, null, React.createElement(MemoryRouter, { initialEntries: [`/issues/paper${query}`] }, React.createElement(Routes, null, React.createElement(Route, { path: "/issues/:submissionId", element: page })), React.createElement(Probe))))); await flush();
  return { container, location: () => location, navigate: async (path) => { await act(async () => navigate(path)); await flush(); }, close: async () => { await act(async () => root.unmount()); container.remove(); } };
}
const findButton = (view, label) => { const button = [...view.container.querySelectorAll("button")].find((node) => node.textContent === label); assert.ok(button, `Missing ${label}`); return button; };
async function click(view, label) { await act(async () => findButton(view, label).click()); await flush(); }
async function text(node, value) { const proto = node.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype; await act(async () => { Object.getOwnPropertyDescriptor(proto, "value").set.call(node, value); node.dispatchEvent(new window.Event("input", { bubbles: true })); }); await flush(); }
async function choose(node, value) { await act(async () => { node.value = value; node.dispatchEvent(new window.Event("change", { bubbles: true })); }); await flush(); }
function checkProps(extra = {}) {
  const results = [{ id: "page-limit", name: "Page limit", category: "page", status: "failed", severity: "blocking", expected: 8, actual: 10, evidence: "10 pages extracted", advice: "Shorten the paper.", confidence: "high" }, { id: "spacing", name: "Paragraph spacing", category: "paragraph", status: "not_applicable", expected: 1, actual: null, confidence: "low" }, { id: "title", name: "Title", category: "document", status: "missing", severity: "warning" }, { id: "policy", name: "Policy check", category: "policy", status: "passed" }];
  const report = { run_id: "run1", sequence: 1, status: "failed", created_at: stamp, engine_version: "1", assessment: { filename: "paper.pdf", verdict: "rejected", score: 33, results }, issues: [{ issue_id: "i1", rule_id: "page-limit" }] };
  return { submissionId: "paper", revision: { revision_id: "r1", number: 1, filename: "paper.pdf", template_id: "template-v1" }, runs: [report], report, onRunChange: () => {}, onRecheck: () => {}, onRetry: () => {}, ...extra };
}
let passed = 0;
async function test(name, run) { reset(); await run(); passed++; console.log(`OK ${name}`); }
try {
  await test("all report categories render and unmeasured checks stay separate from passed", async () => {
    const view = await mount("", checkProps()); try { const suites = view.container.querySelector(".pf-check-suites"); assert.equal(suites.querySelectorAll(".pf-check-suite").length, 4); assert.match(suites.textContent, /Document metadata/); assert.match(suites.textContent, /policy/); assert.match(view.container.querySelector('[aria-label="Saved check totals"]').textContent, /1 passed.*1 failed.*1 missing.*1 not evaluated/); assert.match(view.container.textContent, /excluded from the compliance score/); } finally { await view.close(); }
  });
  await test("check search and attention filters use saved results without API calls", async () => {
    const view = await mount("", checkProps()); try { await choose(view.container.querySelector(".pf-check-filters select"), "attention"); assert.equal(view.container.querySelectorAll(".pf-finding").length, 2); await text(view.container.querySelector('input[type="search"]'), "page-limit"); assert.equal(view.container.querySelectorAll(".pf-finding").length, 1); assert.match(view.container.querySelector(".pf-finding-body").textContent, /Expected8Actual10/); assert.equal(view.container.querySelector('.pf-finding-body a').getAttribute("href"), "/issues/paper?issue=i1"); assert.equal(calls.filter((call) => call.url !== "/auth/me").length, 0); } finally { await view.close(); }
  });
  await test("failed runs without assessments never inherit earlier successful results", async () => {
    const props = checkProps(); props.report = { ...props.report, status: "unable_to_validate", assessment: null, issues: [], error: "Parser could not validate this document" };
    const view = await mount("", props); try { assert.match(view.container.textContent, /Unable to validate/); assert.match(view.container.textContent, /Parser could not validate/); assert.equal(view.container.querySelector(".pf-check-suites"), null); assert.ok(!view.container.textContent.includes("1 passed")); } finally { await view.close(); }
  });
  await test("load errors and unknown exact runs have distinct recoverable states", async () => {
    let retried = false; let view = await mount("", checkProps({ error: "Saved reports unavailable", onRetry: () => { retried = true; } })); try { assert.match(view.container.querySelector('[role="alert"]').textContent, /Saved reports unavailable/); assert.ok(!view.container.textContent.includes("No saved formatting report")); await click(view, "Retry saved reports"); assert.equal(retried, true); } finally { await view.close(); }
    view = await mount("", checkProps({ report: null, requestedRun: "unknown" })); try { assert.match(view.container.textContent, /requested saved report is unavailable/); assert.equal(view.container.querySelector(".pf-check-summary"), null); } finally { await view.close(); }
  });
  await test("issues list supports keyboard links and exact run/revision filtering", async () => {
    const view = await mount("?revision=r1&run=run1"); try { assert.equal(view.container.querySelectorAll(".pf-issue-list li").length, 1); const link = view.container.querySelector(".pf-issue-title"); assert.match(link.getAttribute("href"), /revision=r1&run=run1&issue=i1/); await click(view, "Show all revisions"); assert.equal(view.container.querySelectorAll(".pf-issue-list li").length, 2); await text(view.container.querySelector('input[type="search"]'), "metadata"); assert.equal(view.container.querySelectorAll(".pf-issue-list li").length, 1); } finally { await view.close(); }
  });
  await test("issue comments use their separate endpoint and original run links are immutable", async () => {
    const view = await mount("?issue=i1"); try { assert.ok(calls.some((call) => call.url === "/issues/i1/comments" && call.method === "get")); assert.match(view.container.textContent, /Please shorten the evaluation/); assert.match(view.container.querySelector(".pf-issue-description a").getAttribute("href"), /revision=r1&tab=checks&run=run1/); assert.equal(view.container.querySelector(".pf-issue-controls input"), null); } finally { await view.close(); }
  });
  await test("non-chair status updates omit assignee and persist only confirmed results", async () => {
    const view = await mount("?issue=i1"); try { await choose(view.container.querySelector(".pf-issue-controls select"), "resolved"); await click(view, "Save changes"); const sent = calls.find((call) => call.method === "patch"); assert.deepEqual(JSON.parse(sent.data), { status: "resolved" }); assert.match(view.container.querySelector(".pf-issue-detail-title").textContent, /Resolved/); assert.match(view.container.textContent, /Issue updated/); } finally { await view.close(); }
  });
  await test("denied issue changes retain draft status without a fake success", async () => {
    failPatch = true; const view = await mount("?issue=i1"); try { await choose(view.container.querySelector(".pf-issue-controls select"), "resolved"); await click(view, "Save changes"); assert.match(view.container.querySelector('[role="alert"]').textContent, /permission required/); assert.equal(view.container.querySelector(".pf-issue-controls select").value, "resolved"); assert.match(view.container.querySelector(".pf-issue-detail-title").textContent, /Open/); assert.ok(!view.container.textContent.includes("Issue updated")); failPatch = false; await click(view, "Save changes"); assert.match(view.container.textContent, /Issue updated/); } finally { await view.close(); }
  });
  await test("chairs can assign an issue through the existing PATCH contract", async () => {
    chair = true; const view = await mount("?issue=i1"); try { await text(view.container.querySelector(".pf-issue-controls input"), "author-account"); await click(view, "Save changes"); assert.deepEqual(JSON.parse(calls.find((call) => call.method === "patch").data), { status: "open", assignee_id: "author-account" }); } finally { await view.close(); }
  });
  await test("comment POST failure retains text and retry appends only a confirmed comment", async () => {
    failPost = true; const view = await mount("?issue=i1"); try { const draft = view.container.querySelector("textarea"); await text(draft, "We have shortened the paper."); await click(view, "Add comment"); assert.equal(draft.value, "We have shortened the paper."); assert.ok(!view.container.textContent.includes("Comment added")); failPost = false; await click(view, "Add comment"); assert.equal(draft.value, ""); assert.match(view.container.querySelector(".pf-issue-comments ol").textContent, /We have shortened/); assert.equal(comments.length, 2); } finally { await view.close(); }
  });
  await test("comment retrieval errors remain distinct from no comments and are retryable", async () => {
    failComments = true; const view = await mount("?issue=i1"); try { assert.match(view.container.textContent, /Comments unavailable/); assert.ok(!view.container.textContent.includes("No comments yet")); failComments = false; await click(view, "Retry issue comments"); assert.match(view.container.textContent, /Please shorten/); } finally { await view.close(); }
  });
  await test("list failure is retryable and never reports a false empty state", async () => {
    failList = true; const view = await mount(); try { assert.match(view.container.textContent, /Issue list unavailable/); assert.ok(!view.container.textContent.includes("No tracked issues")); failList = false; await click(view, "Retry issues"); assert.equal(view.container.querySelectorAll(".pf-issue-list li").length, 2); } finally { await view.close(); }
  });
  await test("late detail responses cannot overwrite a newly selected issue", async () => {
    let finish; lateDetail = (config) => new Promise((resolve) => { finish = () => resolve({ data: structuredClone(rows[0]), config, headers: {}, status: 200 }); });
    const view = await mount("?issue=i1"); try { await view.navigate("/issues/paper?issue=i2"); assert.match(view.container.querySelector(".pf-issue-detail-title").textContent, /Title metadata missing/); await act(async () => finish()); await flush(); assert.match(view.container.querySelector(".pf-issue-detail-title").textContent, /Title metadata missing/); } finally { await view.close(); }
  });
  await test("cross-paper issue URLs never render unrelated issue content", async () => {
    rows[0].submission_id = "other-paper"; const view = await mount("?issue=i1"); try { assert.match(view.container.textContent, /not available in this paper workspace/); assert.equal(view.container.querySelector(".pf-issue-description"), null); assert.ok(!view.container.textContent.includes("Please shorten")); } finally { await view.close(); }
  });
  await test("missing permission data hides assignment controls and offers retry", async () => {
    failPermission = true; const view = await mount("?issue=i1"); try { assert.equal(view.container.querySelector(".pf-issue-controls input"), null); chair = true; failPermission = false; await click(view, "Retry permissions"); assert.ok(view.container.querySelector(".pf-issue-controls input")); } finally { await view.close(); }
  });
  console.log(`${passed} D3 checks/issues scenarios passed.`);
} finally { await server.close(); dom.window.close(); }
