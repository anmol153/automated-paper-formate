/** D2 integration tests. Axios is isolated; no local backend or database is used. */
import assert from "node:assert/strict";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";
import { JSDOM } from "jsdom";
import { AxiosError } from "axios";
const dom = new JSDOM("<!doctype html><body></body>", { url: "http://localhost:5173/", pretendToBeVisual: true });
for (const key of ["window", "document", "navigator", "localStorage", "HTMLElement", "Element", "Node", "Event", "FormData", "MouseEvent", "getComputedStyle", "requestAnimationFrame", "cancelAnimationFrame"]) Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const React = await import("react"); const { act } = React;
const { createRoot } = await import("react-dom/client");
const { MemoryRouter, Routes, Route, useLocation } = await import("react-router-dom");
const server = await createServer({ configFile: false, root: ".", appType: "custom", plugins: [react()], server: { middlewareMode: true, hmr: false }, define: { "import.meta.env.VITE_API_BASE": JSON.stringify("http://api.test/api/v1") }, ssr: { external: ["react", "react-dom", "react-dom/client", "react-router-dom"] } });
const { api } = await server.ssrLoadModule("./src/lib/api.js");
const { AuthProvider } = await server.ssrLoadModule("./src/context/AuthContext.jsx");
const SubmissionDetail = (await server.ssrLoadModule("./src/pages/SubmissionDetail.jsx")).default;
const PaperConversation = (await server.ssrLoadModule("./src/components/PaperConversation.jsx")).default;
let calls, role, history, paper, workflow, threads, failConversation, failWorkflow, failUpload, failRecheck;
const revision = (id, number) => ({ revision_id: id, number, filename: `paper-${number}.pdf`, size_bytes: 500, sha256: "abc123", uploaded_at: "2026-10-19T08:00:00Z", uploaded_by: "Author", metadata: { title: "Reproducible research workflows", authors: ["Alex Researcher"] }, latest_check: { status: "passed_with_warnings" }, change_summary: `Revision ${number} change summary`, template_id: "template-1" });
function reset() {
  calls = []; role = "author"; failConversation = failWorkflow = failUpload = failRecheck = false;
  // Deliberately unsorted: the current pointer, rather than array order, is authoritative.
  history = { revisions: [revision("r1", 1), revision("r2", 2)], current_revision_id: "r2", can_upload_revision: true, can_recheck: true };
  paper = { submission_id: "paper", conference_id: "demo", paper_number: 42, title: "Reproducible research workflows", abstract: "A practical approach to reproducible scientific collaboration.", authors: [{ name: "Alex Researcher", affiliation: "Research Institute" }], status: "draft", metadata_version: 1, filename: "paper.pdf" };
  workflow = { status: "draft", revision_id: "r2", eligible: true, reason: "Formatting requirements satisfied.", formatting_gate: "block_errors", actions: ["submitted"], is_chair: false, assignments: [], submission_window: { allowed: true, reason: "Submission window is open." } };
  threads = [{ thread_id: "t1", revision_id: "r1", page_number: 2, visibility: "participants", resolved: false, can_resolve: true, comments: [{ comment_id: "c1", body: "Please clarify this method.", author_id: "Reviewer", author_role: "reviewer", created_at: "2026-10-19T08:00:00Z", version: 1, can_edit: true, can_delete: true }] }];
}
function reject(config, detail) { throw new AxiosError(detail, "ERR_BAD_RESPONSE", config, null, { config, status: 503, data: { detail }, headers: {} }); }
api.defaults.adapter = async (config) => {
  calls.push(config); const path = config.url, method = config.method; let data;
  const body = () => JSON.parse(config.data);
  if (path === "/auth/me") data = { user_id: role, full_name: "Test account" };
  else if (path === "/submissions/paper") data = paper;
  else if (path.endsWith("/workflow")) { if (failWorkflow) reject(config, "Workflow unavailable"); data = workflow; }
  else if (path.endsWith("/collaborators")) data = { submitter_id: "author", collaborators: [], can_manage: role === "author" };
  else if (path.endsWith("/metadata") && method === "get") data = { enabled: true, paper_number: 42, can_edit: role === "author", metadata: { title: paper.title, abstract: paper.abstract, authors: paper.authors, track_id: null, version: 1, source: "declared" }, tracks: [], edit_window: {} };
  else if (path.endsWith("/metadata") && method === "put") { data = {}; }
  else if (path.endsWith("/revisions") && method === "get") data = history;
  else if (path.endsWith("/revisions") && method === "post") { if (failUpload) reject(config, "Upload unavailable"); history.revisions.push(revision("r3", 3)); history.current_revision_id = "r3"; data = history.revisions.at(-1); }
  else if (path.endsWith("/checks") && method === "get") data = [];
  else if (path.endsWith("/check-compliance") && method === "post") { if (failRecheck) reject(config, "Check unavailable"); data = {}; }
  else if (path.endsWith("/discussion")) data = { messages: [] };
  else if (path.endsWith("/conversation") && method === "get") { if (failConversation) reject(config, "Conversation unavailable"); data = threads; }
  else if (path.endsWith("/conversation") && method === "post") { const payload = body(); threads.push({ ...threads[0], thread_id: "t2", ...payload, comments: [{ ...threads[0].comments[0], body: payload.body }] }); data = threads.at(-1); }
  else if (path.endsWith("/comments") && method === "post") { threads[0].comments.push({ ...threads[0].comments[0], comment_id: "c2", ...body() }); data = threads[0]; }
  else if (path.endsWith("/comments/c1") && method === "patch") { threads[0].comments[0].body = body().body; data = {}; }
  else if (path.endsWith("/comments/c1") && method === "delete") { threads[0].comments[0].deleted_at = "2026-10-19T09:00:00Z"; data = {}; }
  else if (path.endsWith("/conversation/t1") && method === "patch") { threads[0].resolved = body().resolved; data = {}; }
  else if (path.endsWith("/transitions")) { paper.status = workflow.status = body().target_status; workflow.actions = []; data = paper; }
  else if (path.endsWith("/reviews")) data = { is_chair: false, reviews: [] };
  else throw new Error(`Unexpected ${method} ${path}`);
  return { data: structuredClone(data), config, headers: {}, status: 200, statusText: "OK" };
};
async function flush() { for (let i = 0; i < 5; i++) await act(async () => { await new Promise((resolve) => setTimeout(resolve, 5)); }); }
async function mount(query = "") {
  const container = document.createElement("div"); document.body.appendChild(container); const root = createRoot(container); let location;
  function Probe() { location = useLocation(); return null; }
  await act(async () => root.render(React.createElement(AuthProvider, null, React.createElement(MemoryRouter, { initialEntries: [`/submissions/paper${query}`] }, React.createElement(Routes, null, React.createElement(Route, { path: "/submissions/:submissionId", element: React.createElement(SubmissionDetail) })), React.createElement(Probe))))); await flush();
  return { container, location: () => location, close: async () => { await act(async () => root.unmount()); container.remove(); } };
}
const button = (view, label) => { const node = [...view.container.querySelectorAll("button")].find((node) => node.textContent === label); assert.ok(node, `Missing button ${label}`); return node; };
async function click(view, label) { await act(async () => button(view, label).click()); await flush(); }
async function tab(view, label) { const link = [...view.container.querySelectorAll(".pf-paper-tabs a")].find((node) => node.textContent === label); assert.ok(link); await act(async () => link.click()); await flush(); }
async function text(element, value) { const proto = element.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype; await act(async () => { Object.getOwnPropertyDescriptor(proto, "value").set.call(element, value); element.dispatchEvent(new window.Event("input", { bubbles: true })); }); await flush(); }
async function choose(element, value) { await act(async () => { element.value = value; element.dispatchEvent(new window.Event("change", { bubbles: true })); }); await flush(); }
let passed = 0;
async function test(name, run) { reset(); await run(); passed++; console.log(`OK ${name}`); }
try {
  await test("header uses current revision pointer; overview shows abstract, readiness and authors", async () => {
    const view = await mount(); try { assert.match(view.container.querySelector("header").textContent, /Current revision 2/); assert.match(view.container.textContent, /Ready for the next review step/); assert.match(view.container.querySelector("aside").textContent, /Alex Researcher/); assert.match(view.container.textContent, /A practical approach/); assert.ok(!view.container.querySelector("aside").textContent.includes("Reviewer assignments")); } finally { await view.close(); }
  });
  await test("section links preserve historical revision, run, page and comparison query", async () => {
    const view = await mount("?revision=r1&run=run1&page=2&compare_base=r1"); try { await tab(view, "Conversation"); const query = new URLSearchParams(view.location().search); for (const [key, value] of Object.entries({ revision: "r1", run: "run1", page: "2", compare_base: "r1", tab: "conversation" })) assert.equal(query.get(key), value); assert.match(view.container.textContent, /Earlier upload/); assert.match(view.container.querySelector('article a').getAttribute("href"), /revision=r1&tab=document&page=2/); } finally { await view.close(); }
  });
  await test("revision changes clear stale report/page, preserve tab/compare context and return to current", async () => {
    const view = await mount("?tab=conversation&revision=r1&run=run1&page=2&compare_base=r1"); try { await click(view, "View current revision"); let query = new URLSearchParams(view.location().search); assert.equal(query.get("revision"), "r2"); assert.equal(query.get("tab"), "conversation"); assert.equal(query.get("compare_base"), "r1"); assert.ok(!query.has("page") && !query.has("run")); await choose(view.container.querySelector(".pf-revision-context select"), "r1"); assert.match(view.container.textContent, /Earlier upload/); } finally { await view.close(); }
  });
  await test("reviewers have no upload/decision/identity controls beyond server permissions", async () => {
    role = "reviewer"; history.can_upload_revision = false; workflow.actions = []; threads[0].can_resolve = false; threads[0].comments[0].can_edit = threads[0].comments[0].can_delete = false; paper.authors = [];
    const view = await mount("?tab=conversation"); try { const content = view.container.textContent; for (const label of ["Upload revision", "Apply action", "Reviewer assignments", "Resolve thread", "Delete"]) assert.ok(!content.includes(label)); assert.ok(!view.container.querySelector('select option[value="chairs"]')); assert.match(content, /No author details available/); } finally { await view.close(); }
  });
  await test("conversation load failure is recoverable without a fake empty state", async () => {
    failConversation = true; const view = await mount("?tab=conversation"); try { assert.match(view.container.textContent, /Conversation unavailable/); assert.ok(!view.container.textContent.includes("No discussions yet")); failConversation = false; await click(view, "Retry conversation"); assert.ok(!view.container.querySelector('[role="alert"]')); assert.match(view.container.textContent, /Please clarify this method/); } finally { await view.close(); }
  });
  await test("chair posts confidential discussion anchored to an earlier immutable revision", async () => {
    workflow.is_chair = true; const view = await mount("?tab=conversation"); try { const composer = view.container.querySelector(".pf-conversation-composer"); await text(composer.querySelector("textarea"), "Chair follow-up"); await choose(composer.querySelectorAll("select")[0], "r1"); await text(composer.querySelector('input[type="number"]'), "3"); await choose(composer.querySelectorAll("select")[1], "chairs"); await click(view, "Post comment"); const sent = calls.find((call) => call.method === "post" && call.url.endsWith("/conversation")); assert.deepEqual(JSON.parse(sent.data), { body: "Chair follow-up", revision_id: "r1", page_number: 3, visibility: "chairs" }); } finally { await view.close(); }
  });
  await test("reply, edit and resolve/reopen keep existing API version and parent contracts", async () => {
    const view = await mount("?tab=conversation"); try { await click(view, "Reply to this comment"); await text(view.container.querySelector("article form textarea"), "A threaded response"); await click(view, "Post reply"); assert.equal(JSON.parse(calls.find((call) => call.url.endsWith("/comments") && call.method === "post").data).parent_comment_id, "c1"); await act(async () => [...view.container.querySelectorAll("article button")].find((node) => node.textContent === "Edit").click()); await flush(); await text(view.container.querySelector("article textarea"), "Updated feedback"); await click(view, "Save comment"); assert.equal(JSON.parse(calls.find((call) => call.method === "patch" && call.url.endsWith("/comments/c1")).data).expected_version, 1); await click(view, "Resolve thread"); assert.match(view.container.querySelector("article").getAttribute("aria-label"), /^Resolved/); await click(view, "Reopen thread"); assert.equal(threads[0].resolved, false); } finally { await view.close(); }
  });
  await test("current workflow transitions retain status/revision concurrency guards", async () => {
    const view = await mount("?revision=r1"); try { await choose(view.container.querySelector(".pf-paper-workflow select"), "submitted"); await click(view, "Apply action"); assert.deepEqual(JSON.parse(calls.find((call) => call.url.endsWith("/transitions")).data), { target_status: "submitted", expected_status: "draft", expected_revision_id: "r2", reason: "" }); assert.match(view.container.querySelector("header").textContent, /Submitted/); } finally { await view.close(); }
  });
  await test("workflow failure has an explicit retry and never reports ready", async () => {
    failWorkflow = true; const view = await mount(); try { assert.match(view.container.textContent, /Workflow summary unavailable/); assert.ok(!view.container.textContent.includes("Ready for the next")); failWorkflow = false; await click(view, "Reload workflow"); assert.match(view.container.textContent, /Ready for the next review step/); assert.ok(!view.container.querySelector('[role="alert"]')); } finally { await view.close(); }
  });
  await test("closed submission windows override formatting readiness and disable submission", async () => {
    workflow.submission_window = { allowed: false, reason: "Submission deadline has passed." }; const view = await mount(); try { assert.match(view.container.textContent, /Submission window closed/); await choose(view.container.querySelector(".pf-paper-workflow select"), "submitted"); assert.equal(button(view, "Apply action").disabled, true); assert.ok(!view.container.textContent.includes("Ready for the next review step")); } finally { await view.close(); }
  });
  await test("chair assignments and empty conversation have explicit, distinct states", async () => {
    workflow.is_chair = true; workflow.assignments = [{ assignment_id: "a1", reviewer_id: "chair-visible-reviewer", status: "accepted" }]; threads = []; const view = await mount("?tab=conversation"); try { assert.match(view.container.querySelector("aside").textContent, /chair-visible-reviewer/); assert.match(view.container.textContent, /No discussions yet/); assert.ok(view.container.querySelector('option[value="chairs"]')); } finally { await view.close(); }
  });
  await test("a confidential draft is cleared when chair visibility is removed", async () => {
    const container = document.createElement("div"); document.body.appendChild(container); const root = createRoot(container);
    const render = async (isChair) => { await act(async () => root.render(React.createElement(MemoryRouter, null, React.createElement(PaperConversation, { submissionId: "paper", revisions: history.revisions, currentRevisionId: "r2", isChair })))); await flush(); };
    try { await render(true); const composer = container.querySelector(".pf-conversation-composer"); await choose(composer.querySelectorAll("select")[1], "chairs"); await text(composer.querySelector("textarea"), "Private draft for chairs"); await render(false); assert.equal(composer.querySelector("textarea").value, ""); assert.ok(!composer.querySelector('option[value="chairs"]')); assert.ok(!calls.some((call) => call.method === "post")); } finally { await act(async () => root.unmount()); container.remove(); }
  });
  await test("unknown and legacy revisions retain safe unavailable/reconciliation states", async () => {
    let view = await mount("?revision=missing"); try { assert.match(view.container.textContent, /This revision is unavailable/); assert.ok(!view.container.querySelector("iframe")); } finally { await view.close(); }
    history.revisions = []; history.current_revision_id = null; history.can_upload_revision = false; view = await mount(); try { assert.match(view.container.textContent, /legacy paper has no revision history/); assert.equal(view.container.querySelector(".pf-revision-context"), null); } finally { await view.close(); }
  });
  await test("recheck failure stays visible and retry calls the existing revision endpoint", async () => {
    failRecheck = true; const view = await mount("?tab=checks&revision=r1"); try { await click(view, "Run checks again"); assert.match(view.container.textContent, /Check unavailable/); failRecheck = false; await click(view, "Run checks again"); assert.ok(!view.container.querySelector('[role="alert"]')); const sent = calls.filter((call) => call.method === "post" && call.url === "/submissions/paper/check-compliance"); assert.equal(sent.length, 2); assert.equal(JSON.parse(sent[0].data).revision_id, "r1"); } finally { await view.close(); }
  });
  await test("metadata editing preserves current revision and version concurrency guards", async () => {
    const view = await mount("?revision=r1"); try { const editor = view.container.querySelector(".pf-paper-metadata-editor"); assert.equal(editor.open, false); await act(async () => editor.querySelector("summary").click()); await text(editor.querySelector("input"), "Updated title"); await click(view, "Save paper details"); const sent = JSON.parse(calls.find((call) => call.url.endsWith("/metadata") && call.method === "put").data); assert.equal(sent.title, "Updated title"); assert.equal(sent.expected_revision_id, "r2"); assert.equal(sent.expected_version, 1); } finally { await view.close(); }
  });
  console.log(`${passed} D2 paper workspace scenarios passed.`);
} finally { await server.close(); dom.window.close(); }
