/** Revision/page UI behavior and blob lifetime; PDF pixels need a real browser. */
import assert from "node:assert/strict";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";
import { JSDOM } from "jsdom";
import { AxiosError } from "axios";

const dom = new JSDOM("<!doctype html><body></body>", { url: "http://localhost:5173/", pretendToBeVisual: true });
for (const key of ["window", "document", "navigator", "HTMLElement", "Element", "Node", "Event", "MouseEvent", "getComputedStyle", "requestAnimationFrame", "cancelAnimationFrame"]) {
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const React = await import("react");
const { act } = React;
const { createRoot } = await import("react-dom/client");
const { MemoryRouter } = await import("react-router-dom");
const server = await createServer({ configFile: false, root: ".", appType: "custom", plugins: [react()],
  server: { middlewareMode: true, hmr: false },
  define: { "import.meta.env.VITE_API_BASE": JSON.stringify("http://api.test/api/v1") },
  ssr: { external: ["react", "react-dom", "react-dom/client", "react-router-dom"] },
});
const { api } = await server.ssrLoadModule("./src/lib/api.js");
const DocumentReview = (await server.ssrLoadModule("./src/components/DocumentReview.jsx")).default;
const revisions = [{ revision_id: "r2", number: 2, filename: "second.pdf", size_bytes: 500 }, { revision_id: "r1", number: 1, filename: "first.pdf", size_bytes: 500 }];
let calls, threads, previewFailure, delayed, createdUrls, revokedUrls;
const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL;
URL.createObjectURL = (blob) => { assert.equal(blob.type, "application/pdf"); const value = `blob:test-${createdUrls.length + 1}`; createdUrls.push(value); return value; };
URL.revokeObjectURL = (value) => revokedUrls.push(value);
const rootComment = (body, id = "comment-1") => ({ comment_id: id, body, author_id: "Reviewer", author_role: "reviewer", created_at: new Date().toISOString(), version: 1, can_edit: true, can_delete: true });
const makeThread = (id, revision, page, body) => ({ thread_id: id, revision_id: revision, page_number: page, visibility: "participants", resolved: false, can_resolve: true, comments: [rootComment(body)] });
function reset() {
  calls = []; threads = []; previewFailure = false; delayed = new Map(); createdUrls = []; revokedUrls = [];
}
const response = (config, data, headers = {}) => ({ data, headers, config, status: 200, statusText: "OK" });
api.defaults.adapter = async (config) => {
  const method = config.method.toUpperCase(), url = config.url;
  calls.push(config);
  if (url.endsWith("/preview")) {
    if (previewFailure) throw new AxiosError("HTTP error", "ERR_BAD_RESPONSE", config, null, { config, status: 404, headers: {}, data: new Blob([JSON.stringify({ detail: "Revision access is unavailable" })], { type: "application/json" }) });
    const revision = url.split("/").at(-2);
    if (delayed.has(revision)) return new Promise((resolve) => { delayed.set(revision, () => resolve(response(config, new Blob(["%PDF-delayed"]), { "x-paper-page-count": "2" }))); });
    return response(config, new Blob(["%PDF-test"]), { "x-paper-page-count": "2" });
  }
  if (url.endsWith("/conversation") && method === "GET") return response(config, structuredClone(threads));
  if (url.endsWith("/conversation") && method === "POST") {
    const data = JSON.parse(config.data);
    const thread = makeThread(`new-${threads.length}`, data.revision_id, data.page_number, data.body);
    thread.visibility = data.visibility;
    threads.push(thread);
    return response(config, structuredClone(thread));
  }
  const thread = threads.find((row) => url.includes(`/conversation/${row.thread_id}`));
  if (thread && method === "POST" && url.endsWith("/comments")) {
    const data = JSON.parse(config.data);
    thread.comments.push({ ...rootComment(data.body, `reply-${thread.comments.length}`), parent_comment_id: data.parent_comment_id });
    return response(config, structuredClone(thread));
  }
  if (thread && method === "PATCH") {
    const data = JSON.parse(config.data);
    if (url.includes("/comments/")) { thread.comments[0].body = data.body; thread.comments[0].version++; }
    else thread.resolved = data.resolved;
    return response(config, structuredClone(thread));
  }
  throw new Error(`Unexpected request ${method} ${url}`);
};
async function flush() { for (let i = 0; i < 5; i++) await act(async () => { await new Promise((resolve) => setTimeout(resolve, 5)); }); }
function button(container, label) { const found = [...container.querySelectorAll("button")].find((node) => node.textContent === label); assert.ok(found, `Missing ${label}`); return found; }
async function click(container, label) { await act(async () => button(container, label).click()); await flush(); }
async function text(element, value) {
  const prototype = element.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, "value").set.call(element, value);
    element.dispatchEvent(new window.Event("input", { bubbles: true }));
  });
  await flush();
}
async function choose(element, value) { await act(async () => { element.value = value; element.dispatchEvent(new window.Event("change", { bubbles: true })); }); await flush(); }
async function mount(overrides = {}) {
  let props = { submissionId: "paper", revision: revisions[1], revisions, currentRevisionId: "r2", isChair: true, ...overrides };
  const container = document.createElement("div"); document.body.appendChild(container);
  const root = createRoot(container);
  function Harness({ options }) {
    const [page, setPage] = React.useState(options.initialPage ?? "1");
    return React.createElement(DocumentReview, { ...options, pageNumber: page, onPageChange: setPage });
  }
  async function render() { await act(async () => root.render(React.createElement(MemoryRouter, null, React.createElement(Harness, { options: props })))); await flush(); }
  await render();
  return { container, update: async (next) => { props = { ...props, ...next }; await render(); }, close: async () => { await act(async () => root.unmount()); container.remove(); assert.deepEqual([...revokedUrls].sort(), [...createdUrls].sort(), "Every created preview blob must be revoked"); } };
}
let passed = 0;
async function test(name, run) { reset(); await run(); passed++; console.log(`OK ${name}`); }
try {
  await test("protected preview is local, revision-specific, and cleaned up on exit", async () => {
    const page = await mount();
    try {
      const frame = page.container.querySelector("iframe");
      assert.equal(frame.getAttribute("src"), "blob:test-1#page=1");
      assert.match(frame.title, /revision 1, page 1/);
      assert.ok(calls.some((call) => call.url === "/submissions/paper/revisions/r1/preview" && call.responseType === "blob"));
      assert.match(page.container.textContent, /earlier version/);
    } finally { await page.close(); }
  });
  await test("page navigation keeps separate drafts and posts to the selected immutable anchor", async () => {
    const page = await mount();
    try {
      const composer = () => [...page.container.querySelectorAll("textarea")].at(-1);
      await text(composer(), "First-page feedback");
      await click(page.container, "Next page"); assert.equal(composer().value, "");
      await text(composer(), "Second-page draft");
      await click(page.container, "Previous page"); assert.equal(composer().value, "First-page feedback");
      await click(page.container, "Post page comment");
      const sent = calls.find((call) => call.method === "post" && call.url.endsWith("/conversation"));
      assert.deepEqual(JSON.parse(sent.data), { body: "First-page feedback", visibility: "participants", revision_id: "r1", page_number: 1 });
      assert.match(page.container.textContent, /First-page feedback/);
      await click(page.container, "Next page"); assert.equal(composer().value, "Second-page draft");
    } finally { await page.close(); }
  });
  await test("discussion sidebar excludes other pages, revisions, and general threads", async () => {
    threads = [makeThread("a", "r1", 1, "This page only"), makeThread("b", "r1", 2, "Other page"), makeThread("c", "r2", 1, "Other revision"), makeThread("d", null, null, "General topic")];
    const page = await mount();
    try {
      const sidebar = page.container.querySelector("aside").textContent;
      assert.match(sidebar, /This page only/); assert.doesNotMatch(sidebar, /Other page|Other revision|General topic/);
      const anchor = [...page.container.querySelectorAll("a")].find((link) => link.textContent.includes("Revision 1"));
      assert.equal(anchor.getAttribute("href"), "/submissions/paper?revision=r1&tab=document&page=1");
    } finally { await page.close(); }
  });
  await test("invalid historical page links are not silently clamped", async () => {
    const page = await mount({ initialPage: "3" });
    try {
      assert.match(page.container.textContent, /invalid or outside this document/);
      assert.equal(page.container.querySelector('input[type="number"]').value, "3");
      assert.equal(page.container.querySelector("iframe"), null);
      assert.ok(button(page.container, "Post page comment").disabled);
    } finally { await page.close(); }
  });
  await test("non-PDF fallback does not fetch or invent an exact page count", async () => {
    const page = await mount({ revision: { ...revisions[1], filename: "source.tex" }, initialPage: "10", layout: { page_count: 2, page_count_exact: false } });
    try {
      assert.match(page.container.textContent, /Inline preview supports PDF/);
      assert.match(page.container.textContent, /An exact page count is not available/);
      assert.ok(!calls.some((call) => call.url.endsWith("/preview")));
      assert.equal(page.container.querySelector("textarea").disabled, false);
    } finally { await page.close(); }
  });
  await test("oversized files use a download fallback without loading preview bytes", async () => {
    const page = await mount({ revision: { ...revisions[1], size_bytes: 25 * 1024 * 1024 + 1 } });
    try { assert.match(page.container.textContent, /larger than the 25 MB preview limit/); assert.ok(!calls.some((call) => call.url.endsWith("/preview"))); }
    finally { await page.close(); }
  });
  await test("JSON blob errors show useful messages and preview can be retried", async () => {
    previewFailure = true;
    const page = await mount();
    try {
      assert.match(page.container.textContent, /Revision access is unavailable/); assert.equal(page.container.querySelector("iframe"), null);
      previewFailure = false; await click(page.container, "Retry PDF preview"); assert.ok(page.container.querySelector("iframe"));
    } finally { await page.close(); }
  });
  await test("changing revisions aborts the old preview and ignores a late response", async () => {
    delayed.set("r1", null);
    const page = await mount();
    try {
      const oldRequest = calls.find((call) => call.url.includes("r1/preview"));
      const finishOld = delayed.get("r1");
      await page.update({ revision: revisions[0] }); assert.equal(oldRequest.signal.aborted, true);
      await act(async () => finishOld()); await flush();
      assert.match(page.container.querySelector("iframe").title, /revision 2/);
      assert.equal(createdUrls.length, 1);
    } finally { await page.close(); }
  });
  await test("chair-only drafts are not carried into participant visibility after a role change", async () => {
    const page = await mount();
    try {
      await choose(page.container.querySelector("aside select"), "chairs");
      await text(page.container.querySelector("textarea"), "Confidential draft");
      await page.update({ isChair: false });
      assert.equal(page.container.querySelector("aside select"), null);
      assert.equal(page.container.querySelector("textarea").value, "");
      assert.ok(button(page.container, "Post page comment").disabled);
      assert.ok(!calls.some((call) => call.method === "post"));
    } finally { await page.close(); }
  });
  await test("page links contain only the original revision/page and support manual copying", async () => {
    let copied;
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async (value) => { copied = value; } } });
    const page = await mount();
    try {
      await click(page.container, "Next page"); await click(page.container, "Copy page link");
      assert.equal(copied, "http://localhost:5173/submissions/paper?tab=document&revision=r1&page=2");
      navigator.clipboard.writeText = async () => { throw new Error("Denied"); };
      await click(page.container, "Copy page link"); assert.match(page.container.textContent, /Copy the page link from the field/);
      assert.equal(page.container.querySelector("input[readonly]").value, copied);
    } finally { await page.close(); }
  });
  await test("page threads reuse edit, reply and resolution actions without moving anchors", async () => {
    threads = [makeThread("a", "r1", 1, "Original comment")];
    const page = await mount();
    try {
      await click(page.container, "Edit");
      const edit = [...page.container.querySelectorAll("label")].find((node) => node.textContent.startsWith("Edit comment")).querySelector("textarea");
      await text(edit, "Edited comment"); await click(page.container, "Save comment");
      assert.match(page.container.textContent, /Edited comment/);
      await click(page.container, "Reply to this comment");
      const reply = [...page.container.querySelectorAll("label")].find((node) => node.textContent === "Reply").querySelector("textarea");
      await text(reply, "Reply text"); await click(page.container, "Post reply");
      assert.equal(threads[0].comments[1].parent_comment_id, "comment-1");
      await click(page.container, "Resolve thread"); assert.equal(threads[0].resolved, true);
      assert.equal(threads[0].revision_id, "r1"); assert.equal(threads[0].page_number, 1);
    } finally { await page.close(); }
  });
  console.log(`${passed} document review scenarios passed.`);
} finally { URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; await server.close(); dom.window.close(); }
