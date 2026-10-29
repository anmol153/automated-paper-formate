/** Phase 7 UI interactions with an isolated API adapter; no live user data. */
import assert from "node:assert/strict";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";
import { JSDOM } from "jsdom";
import { AxiosError } from "axios";

const dom = new JSDOM("<!doctype html><body></body>", { url: "http://localhost:5173/", pretendToBeVisual: true });
for (const key of ["window", "document", "navigator", "localStorage", "HTMLElement", "Element", "Node", "Event", "MouseEvent", "getComputedStyle", "requestAnimationFrame", "cancelAnimationFrame"]) {
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const React = await import("react");
const { act } = React;
const { createRoot } = await import("react-dom/client");
const { MemoryRouter, Routes, Route } = await import("react-router-dom");
const server = await createServer({
  configFile: false, root: ".", appType: "custom", plugins: [react()],
  server: { middlewareMode: true, hmr: false },
  define: { "import.meta.env.VITE_API_BASE": JSON.stringify("http://api.test/api/v1") },
  ssr: { external: ["react", "react-dom", "react-dom/client", "react-router-dom"] },
});
const client = await server.ssrLoadModule("./src/lib/api.js");
const { emptyRuleSet } = await server.ssrLoadModule("./src/lib/ruleOptions.js");
const { AuthProvider } = await server.ssrLoadModule("./src/context/AuthContext.jsx");
let role, versions, snapshots, calls, failHistory, failPublish, failImport, failDirectory, submissionWindow, conferenceSettings, failSettings, failSubmission;
let library;
function reset(actor = "chair") {
  role = actor; versions = []; snapshots = new Map(); calls = [];
  failHistory = false; failPublish = false; failImport = false; failDirectory = false;
  submissionWindow = { allowed: true };
  conferenceSettings = { enabled: false, settings: {}, tracks: [] };
  failSettings = false; failSubmission = false;
  library = { ...emptyRuleSet(), template_id: "library", name: "Saved venue rules" };
}
function fail(config, detail, status = 503) {
  throw new AxiosError(detail, "ERR_BAD_RESPONSE", config, null, { status, data: { detail }, headers: {}, config });
}
function addVersion(rules) {
  const id = `version-${versions.length + 1}`;
  const snapshot = structuredClone({ ...rules, template_id: id });
  snapshots.set(id, snapshot);
  versions.unshift([id, id, new Date(1700000000000 + versions.length * 1000).toISOString()]);
  return snapshot;
}
client.api.defaults.adapter = async (config) => {
  const method = config.method.toUpperCase();
  const url = config.url;
  calls.push({ method, url, data: config.data });
  let data;
  if (url === "/auth/me") data = { user_id: role, full_name: role, email: `${role}@example.test` };
  else if (url === "/auth/google/connection") data = { connected: false };
  else if (url === "/auth/google/config") data = { enabled: false };
  else if (url === "/templates") data = { templates: [library], count: 1 };
  else if (url === "/templates/library") data = library;
  else if (url === "/templates/import") {
    if (failImport) fail(config, "Could not parse template");
    data = { ...library, name: "Imported template rules", template_id: "" };
  } else if (url === "/conferences/") {
    if (failDirectory) fail(config, "Conference directory unavailable");
    data = method === "POST" ? { conference_id: "c", ...JSON.parse(config.data) } : [{ conference_id: "c", name: "Test Conference" }];
  } else if (url === "/conferences/c") data = { conference_id: "c", name: "Test Conference", members: role === "chair" ? [{ user_id: "chair", role: "owner" }] : [] };
  else if (url === "/conferences/c/submissions") {
    if (method === "POST") {
      if (failSubmission) fail(config, "The submission deadline has passed.", 409);
      throw new Error("Unexpected successful upload in this scenario");
    }
    data = [];
  }
  else if (url === "/conferences/c/settings") {
    if (failSettings) fail(config, "Conference membership required", 403);
    data = { ...conferenceSettings, submission_window: submissionWindow };
  }
  else if (url === "/conferences/c/workflow") data = { formatting_gate: "allow_issues", can_configure: Boolean(conferenceSettings.can_configure) };
  else if (url === "/conferences/c/review-configuration") data = { form: { recommendations: ["Accept"], criteria: [] }, policy: { deadline: null, minimum_reviews: 1 }, can_configure: Boolean(conferenceSettings.can_configure) };
  else if (url === "/conferences/c/review-progress") fail(config, "Chair only", 403);
  else if (url === "/conferences/c/templates" && method === "GET") {
    if (failHistory) fail(config, "History temporarily unavailable");
    data = versions;
  } else if (url === "/conferences/c/templates" && method === "POST") {
    if (failPublish) fail(config, "Publication rejected", 403);
    data = addVersion(JSON.parse(config.data));
  } else if (url.startsWith("/conferences/c/templates/")) {
    data = snapshots.get(url.split("/").at(-1));
    if (!data) fail(config, "Version not found", 404);
  } else throw new Error(`Unexpected API request: ${method} ${url}`);
  return { data: structuredClone(data), status: 200, statusText: "OK", headers: {}, config };
};
async function flush() {
  for (let i = 0; i < 5; i++) await act(async () => { await new Promise((resolve) => setTimeout(resolve, 5)); });
}
async function mount(path, props = {}, { authenticated = false, route = "/", pattern = route, withTemplatePage = false } = {}) {
  const Component = (await server.ssrLoadModule(path)).default;
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const TemplatePage = withTemplatePage ? (await server.ssrLoadModule("./src/pages/LatestTemplate.jsx")).default : null;
  let tree = React.createElement(MemoryRouter, { initialEntries: [route] }, React.createElement(Routes, null,
    React.createElement(Route, { path: pattern, element: React.createElement(Component, props) }),
    TemplatePage && React.createElement(Route, { path: "/conferences/:confId/latest", element: React.createElement(TemplatePage) })));
  if (authenticated) tree = React.createElement(AuthProvider, null, tree);
  await act(async () => root.render(tree));
  await flush();
  return { container, close: async () => { await act(async () => root.unmount()); container.remove(); } };
}
function button(container, name) {
  const found = [...container.querySelectorAll("button")].find((node) => node.textContent === name);
  assert.ok(found, `Button missing: ${name}`);
  return found;
}
async function click(container, name) { await act(async () => button(container, name).click()); await flush(); }
async function clickLink(container, name) {
  const link = [...container.querySelectorAll("a")].find((node) => node.textContent === name);
  assert.ok(link, `Link missing: ${name}`);
  await act(async () => link.click()); await flush();
}
async function select(element, value) {
  await act(async () => { element.value = value; element.dispatchEvent(new window.Event("change", { bubbles: true })); });
  await flush();
}
function field(container, label) {
  const node = [...container.querySelectorAll("label[for]")].find((node) => node.textContent.replace(/\s*\*$/, "") === label);
  assert.ok(node, `Field missing: ${label}`);
  return document.getElementById(node.htmlFor);
}
async function fillField(container, label, value) {
  const node = field(container, label);
  const prototype = node.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : node.tagName === "SELECT" ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, "value").set.call(node, value);
    node.dispatchEvent(new window.Event(node.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
  await flush();
}
async function choosePaper(container) {
  const input = field(container, "Paper file (PDF, DOCX or LaTeX)");
  const file = new window.File(["paper contents"], "paper.pdf", { type: "application/pdf" });
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  await act(async () => input.dispatchEvent(new window.Event("change", { bubbles: true })));
  await flush();
  return file;
}
async function loadLibrary(container) {
  if (!container.querySelector('[aria-label="Configure template"]')) await clickLink(container, "Configure a template");
  const selectNode = [...container.querySelectorAll("select")].find((node) => node.parentElement.textContent.startsWith("Saved standalone template"));
  await select(selectNode, "library"); await click(container, "Load saved rules");
}
const manager = "./src/components/ConferenceTemplates.jsx";
let passed = 0;
async function test(name, run) {
  reset(); await run(); passed++; console.log(`OK ${name}`);
}
try {
  await test("chair publishes saved rules, retains earlier snapshots, and can browse history", async () => {
    let availability;
    const page = await mount(manager, { confId: "c", canPublish: true, onAvailabilityChange: (status) => { availability = status; } });
    try {
      assert.equal(availability, "missing");
      await loadLibrary(page.container);
      await click(page.container, "Publish template version");
      assert.equal(availability, "ready"); assert.equal(versions.length, 1);
      const first = structuredClone(snapshots.get("version-1"));
      await clickLink(page.container, "Configure a template");
      await click(page.container, "Copy viewed version for editing");
      await click(page.container, "Publish template version");
      assert.equal(versions.length, 2); assert.deepEqual(snapshots.get("version-1"), first);
      assert.equal(library.template_id, "library");
      await clickLink(page.container, "Compare versions");
      const comparison = [...page.container.querySelectorAll("a")].find((node) => node.textContent.includes("Compare the two latest"));
      assert.equal(comparison?.getAttribute("href"), "/conferences/c/diff?old=version-1&new=version-2");
      await clickLink(page.container, "View published rules");
      await select(page.container.querySelector("select"), "version-1");
      assert.match(page.container.textContent, /Viewing a previous version/);
    } finally { await page.close(); }
  });
  await test("authors see published rules without publication controls or library access", async () => {
    addVersion(library); role = "author";
    const page = await mount(manager, { confId: "c", canPublish: false });
    try {
      assert.match(page.container.textContent, /Saved venue rules/);
      assert.doesNotMatch(page.container.textContent, /Configure a template|Publish template version/);
      assert.ok([...page.container.querySelectorAll("input, textarea, button")].every((node) => node.disabled));
      assert.ok(!calls.some((call) => call.url === "/templates"));
    } finally { await page.close(); }
  });
  await test("published rules are a read-only document and configuration and comparison have separate URLs", async () => {
    addVersion(library);
    const page = await mount(manager, { confId: "c", canPublish: true });
    try {
      const summary = page.container.querySelector('[aria-label="Published template rules"]');
      assert.ok(summary); assert.equal(summary.querySelectorAll("input, select, textarea, button").length, 0);
      assert.match(summary.textContent, /Read only/);
      assert.equal(page.container.querySelector('[aria-label="Configure template"]'), null);
      assert.ok(!calls.some((call) => call.url === "/templates"));
      await clickLink(page.container, "Configure a template");
      assert.ok(page.container.querySelector('[aria-label="Configure template"]'));
      assert.equal(page.container.querySelector('[aria-label="Published template rules"]'), null);
      await clickLink(page.container, "Compare versions");
      assert.equal(page.container.querySelector('[aria-label="Configure template"]'), null);
      assert.match(page.container.textContent, /Publish at least two versions/);
      assert.ok([...page.container.querySelectorAll("a")].find((a) => a.textContent === "View published rules").getAttribute("href").includes("templateView=published"));
    } finally { await page.close(); }
  });
  await test("empty author view explains the missing template", async () => {
    const page = await mount(manager, { confId: "c", canPublish: false });
    try { assert.match(page.container.textContent, /Ask a conference chair/); } finally { await page.close(); }
  });
  await test("history failures keep uploads unavailable until a successful reload", async () => {
    failHistory = true; let availability;
    const page = await mount(manager, { confId: "c", canPublish: true, onAvailabilityChange: (status) => { availability = status; } });
    try {
      assert.equal(availability, "error"); assert.match(page.container.textContent, /History temporarily unavailable/);
      failHistory = false; addVersion(library); await click(page.container, "Reload templates");
      assert.equal(availability, "ready");
    } finally { await page.close(); }
  });
  await test("a rejected publication retains editable rules for retry", async () => {
    const page = await mount(manager, { confId: "c", canPublish: true });
    try {
      await loadLibrary(page.container); failPublish = true;
      await click(page.container, "Publish template version");
      assert.match(page.container.textContent, /Publication rejected/); assert.equal(versions.length, 0);
      assert.ok(button(page.container, "Publish template version"));
      failPublish = false; await click(page.container, "Publish template version"); assert.equal(versions.length, 1);
    } finally { await page.close(); }
  });
  await test("a blank template needs a name and can be discarded without publishing", async () => {
    const page = await mount(manager, { confId: "c", canPublish: true });
    try {
      await clickLink(page.container, "Configure a template");
      await click(page.container, "Start blank template");
      assert.ok(button(page.container, "Publish template version").disabled);
      await click(page.container, "Discard unpublished changes");
      assert.ok(!calls.some((call) => call.method === "POST"));
    } finally { await page.close(); }
  });
  await test("template import previews rules and parse errors preserve the draft", async () => {
    const page = await mount(manager, { confId: "c", canPublish: true });
    try {
      await clickLink(page.container, "Configure a template");
      const input = page.container.querySelector('input[type="file"]');
      const blob = new Blob(["template contents"], { type: "application/pdf" });
      Object.defineProperty(blob, "name", { value: "template.pdf" });
      Object.defineProperty(input, "files", { value: [blob] });
      await act(async () => input.dispatchEvent(new window.Event("change", { bubbles: true })));
      await click(page.container, "Import template rules");
      assert.ok([...page.container.querySelectorAll("input")].some((node) => node.value === "Imported template rules"));
      assert.equal(versions.length, 0);
      failImport = true; await click(page.container, "Import template rules");
      assert.match(page.container.textContent, /Could not parse template/);
      assert.ok(button(page.container, "Publish template version"));
    } finally { await page.close(); }
  });
  await test("account ID can be copied and has a manual fallback", async () => {
    let copied;
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async (text) => { copied = text; } } });
    const page = await mount("./src/pages/Account.jsx", {}, { authenticated: true });
    try {
      await click(page.container, "Copy account ID"); assert.equal(copied, "chair");
      assert.match(page.container.textContent, /Account ID copied/);
      navigator.clipboard.writeText = async () => { throw new Error("Clipboard unavailable"); };
      await click(page.container, "Copy account ID"); assert.match(page.container.textContent, /copy it manually/);
      assert.equal(page.container.querySelector("input[readonly]").value, "chair");
    } finally { await page.close(); }
  });
  await test("conference chooser links to the selected conference submission form", async () => {
    const page = await mount("./src/components/ConferenceChooser.jsx");
    try {
      await select(page.container.querySelector("select"), "c");
      assert.ok(page.container.querySelector('a[href="/conferences/c/submit"]'));
    } finally { await page.close(); }
  });
  await test("directory errors are recoverable", async () => {
    failDirectory = true;
    const page = await mount("./src/components/ConferenceChooser.jsx");
    try {
      assert.match(page.container.textContent, /Conference directory unavailable/);
      failDirectory = false; await click(page.container, "Retry conferences");
      assert.match(page.container.textContent, /Test Conference/);
    } finally { await page.close(); }
  });
  await test("chair configures templates on the template page, then returns to submit a paper", async () => {
    const listing = await mount("./src/pages/ConferencePapers.jsx", {}, { authenticated: true, route: "/conferences/c/submissions", pattern: "/conferences/:confId/submissions" });
    try { assert.ok(listing.container.querySelector(".pf-paper-list")); assert.equal(listing.container.querySelector("#new-submission"), null); }
    finally { await listing.close(); }
    const page = await mount("./src/pages/ConferencePapers.jsx", {}, { authenticated: true, route: "/conferences/c/submit", pattern: "/conferences/:confId/submit", withTemplatePage: true });
    try {
      await choosePaper(page.container);
      assert.equal(button(page.container, "Create submission").disabled, false);
      assert.equal(page.container.querySelector("#paper-template-status"), null);
      await click(page.container, "Create submission");
      assert.match(page.container.querySelector("#paper-template-status").textContent, /ask a chair to publish a template/);
      assert.ok(!calls.some((call) => call.url === "/conferences/c/submissions" && call.method === "POST"));
      assert.ok(!calls.some((call) => call.url === "/templates"));
      await clickLink(page.container, "View conference template");
      assert.equal(page.container.querySelector("#new-submission"), null);
      await loadLibrary(page.container); await click(page.container, "Publish template version");
      await clickLink(page.container, "Submit a paper →");
      await choosePaper(page.container);
      assert.equal(page.container.querySelector("[aria-invalid=true]"), null);
    } finally { await page.close(); }
  });
  await test("template errors and closed windows are explained after submit and reload keeps the selected file", async () => {
    failHistory = true;
    submissionWindow = { allowed: false, reason: "The conference is not accepting initial submissions or draft edits at this time." };
    const page = await mount("./src/pages/ConferencePapers.jsx", {}, { authenticated: true, route: "/conferences/c/submit", pattern: "/conferences/:confId/submit" });
    try {
      const file = await choosePaper(page.container);
      await click(page.container, "Create submission");
      assert.match(page.container.querySelector("#paper-template-status").textContent, /reload the templates before submitting/);
      failHistory = false; addVersion(library); await click(page.container, "Reload templates");
      assert.equal(field(page.container, "Paper file (PDF, DOCX or LaTeX)").files[0], file);
      assert.equal(page.container.querySelector("#paper-template-status"), null);
      assert.match(page.container.querySelector("#paper-submission-window").textContent, /not accepting initial submissions/);
      await click(page.container, "Create submission");
      assert.ok(!calls.some((call) => call.url === "/conferences/c/submissions" && call.method === "POST"));
    } finally { await page.close(); }
  });
  await test("submit highlights all missing required fields, focuses the first, and clears each error as it is fixed", async () => {
    addVersion(library); failSubmission = true;
    conferenceSettings = { enabled: true, can_configure: true, settings: { lifecycle_status: "open", require_title: true, require_abstract: true, require_authors: true, require_track: true }, tracks: [{ track_id: "ai", name: "AI", active: true }] };
    const page = await mount("./src/pages/ConferencePapers.jsx", {}, { authenticated: true, route: "/conferences/c/submit", pattern: "/conferences/:confId/submit" });
    try {
      const form = page.container.querySelector("#new-submission");
      assert.doesNotMatch(form.textContent, /Before you submit|Action needed|Required before review/);
      assert.equal(form.querySelector("[aria-invalid=true]"), null);
      assert.equal(form.querySelector(".pf-validation-icon"), null);
      await click(page.container, "Create submission");
      assert.equal(form.querySelectorAll("[aria-invalid=true]").length, 5);
      assert.equal(form.querySelectorAll(".pf-validation-icon").length, 5);
      assert.equal(document.activeElement, field(form, "Paper title"));
      assert.ok(!calls.some((call) => call.url === "/conferences/c/submissions" && call.method === "POST"));
      await fillField(form, "Paper title", "   ");
      assert.equal(field(form, "Paper title").getAttribute("aria-invalid"), "true");
      await fillField(form, "Paper title", "Research paper");
      assert.equal(field(form, "Paper title").getAttribute("aria-invalid"), null);
      await click(page.container, "Create submission");
      assert.equal(document.activeElement, field(form, "Abstract"));
      await fillField(form, "Abstract", "Research abstract");
      await fillField(form, "Track", "ai");
      await click(page.container, "Add author");
      assert.equal(form.querySelector("#paper-authors-error"), null);
      assert.equal(field(form, "Author 1 name").getAttribute("aria-invalid"), "true");
      await fillField(form, "Author 1 name", "Research Author");
      await choosePaper(form);
      assert.equal(form.querySelector("[aria-invalid=true]"), null);
      assert.equal(form.querySelector(".pf-validation-icon"), null);
      await click(page.container, "Create submission");
      assert.equal(calls.filter((call) => call.url === "/conferences/c/submissions" && call.method === "POST").length, 1);
      assert.match(form.querySelector('[role="alert"]').textContent, /deadline has passed/);
    } finally { await page.close(); }
  });
  await test("draft uploads skip review requirements but still validate file and any added author names", async () => {
    addVersion(library); failSubmission = true;
    conferenceSettings = { enabled: true, settings: { require_title: true, require_abstract: true, require_authors: true, require_track: true }, tracks: [] };
    const page = await mount("./src/pages/ConferencePapers.jsx", {}, { authenticated: true, route: "/conferences/c/submit", pattern: "/conferences/:confId/submit" });
    try {
      await click(page.container, "Create submission");
      await act(async () => page.container.querySelector('input[type="checkbox"]').click());
      await flush();
      assert.equal(page.container.querySelectorAll("[aria-invalid=true]").length, 1);
      await choosePaper(page.container);
      await click(page.container, "Add author");
      await click(page.container, "Create submission");
      assert.equal(field(page.container, "Author 1 name").getAttribute("aria-invalid"), "true");
      assert.ok(!calls.some((call) => call.url === "/conferences/c/submissions" && call.method === "POST"));
      await fillField(page.container, "Author 1 name", "Draft Author");
      await click(page.container, "Create submission");
      const upload = calls.find((call) => call.url === "/conferences/c/submissions" && call.method === "POST");
      assert.equal(upload.data.get("submit_for_review"), "false");
      assert.equal(page.container.querySelector("[aria-invalid=true]"), null);
    } finally { await page.close(); }
  });
  await test("a required track with no options explains how to resolve it on submit", async () => {
    addVersion(library);
    conferenceSettings = { enabled: true, settings: { require_track: true }, tracks: [] };
    const page = await mount("./src/pages/ConferencePapers.jsx", {}, { authenticated: true, route: "/conferences/c/submit", pattern: "/conferences/:confId/submit" });
    try {
      await click(page.container, "Create submission");
      const track = field(page.container, "Track");
      assert.match(document.getElementById(track.getAttribute("aria-describedby").split(" ").at(-1)).textContent, /Ask a chair to add or enable a track/);
    } finally { await page.close(); }
  });
  await test("chair and author submission requirements share the same read-only view", async () => {
    let authorView;
    for (const actor of ["author", "chair"]) {
      reset(actor);
      conferenceSettings = { enabled: true, can_configure: actor === "chair", version: 1, settings: { lifecycle_status: "open", require_title: true }, tracks: [{ track_id: "ai", name: "Artificial Intelligence", description: "AI research papers", active: true, version: 1 }] };
      const page = await mount("./src/pages/ConferencePapers.jsx", {}, { authenticated: true, route: "/conferences/c/submit", pattern: "/conferences/:confId/submit" });
      try {
        const requirements = page.container.querySelector(".pf-inline-configuration");
        assert.equal(requirements.querySelector("summary").textContent, "Conference requirements");
        assert.equal(requirements.querySelectorAll("input, textarea, select, form").length, 0);
        assert.match(requirements.textContent, /Artificial Intelligence/);
        assert.doesNotMatch(requirements.textContent, /Configure conference|Save track|Create track|Save policy|Configure criteria|Chair review dashboard/);
        assert.ok(!calls.some((call) => call.url.endsWith("/review-progress")), "Submission must not load the chair review dashboard");
        const settingsLink = [...requirements.querySelectorAll("a")].find((node) => node.textContent === "Manage conference settings →");
        if (actor === "author") {
          authorView = requirements.textContent;
          assert.equal(settingsLink, undefined);
        } else {
          assert.equal(settingsLink?.getAttribute("href"), "/conferences/c?tab=settings");
          assert.equal(requirements.textContent.replace("Manage conference settings →", ""), authorView);
        }
      } finally { await page.close(); }
    }
  });
  await test("submission schedule guidance distinguishes future opening times, expired deadlines and archived conferences", async () => {
    for (const [settings, message] of [
      [{ lifecycle_status: "open", submissions_open_at: new Date(Date.now() + 86400000).toISOString() }, /Submissions open .*Please return then/],
      [{ lifecycle_status: "open", submissions_close_at: new Date(Date.now() - 86400000).toISOString() }, /submission deadline was .*extension/],
      [{ lifecycle_status: "archived" }, /conference is archived.*available submission options/],
    ]) {
      const page = await mount("./src/components/SubmissionRequirements.jsx", { confId: "c", templateStatus: "ready", settings: { enabled: true, settings, tracks: [], submission_window: { allowed: false } }, file: null, metadata: { title: "", abstract: "", authors: [], track_id: null } });
      try { assert.match(page.container.textContent, message); }
      finally { await page.close(); }
    }
  });
  await test("load failures explain account access and allow retry", async () => {
    failSettings = true;
    const page = await mount("./src/pages/ConferencePapers.jsx", {}, { authenticated: true, route: "/conferences/c/submit", pattern: "/conferences/:confId/submit" });
    try {
      assert.match(page.container.textContent, /Submission requirements could not be loaded/);
      assert.match(page.container.textContent, /Accept your conference invitation/);
      assert.equal(page.container.querySelector("#new-submission"), null);
      failSettings = false;
      await click(page.container, "Retry loading requirements");
      assert.ok(page.container.querySelector("#new-submission"));
      assert.doesNotMatch(page.container.textContent, /Submission requirements could not be loaded/);
    } finally { await page.close(); }
  });
  await test("upload errors explain the failure beside the submit button and preserve selected paper details", async () => {
    addVersion(library); failSubmission = true;
    conferenceSettings = { enabled: true, settings: { lifecycle_status: "open", require_title: true }, tracks: [] };
    const page = await mount("./src/pages/ConferencePapers.jsx", {}, { authenticated: true, route: "/conferences/c/submit", pattern: "/conferences/:confId/submit" });
    try {
      const form = page.container.querySelector("#new-submission");
      const input = form.querySelector('input[type="file"]');
      const file = new window.File(["paper contents"], "paper.pdf", { type: "application/pdf" });
      Object.defineProperty(input, "files", { value: [file] });
      await act(async () => input.dispatchEvent(new window.Event("change", { bubbles: true })));
      await fillField(form, "Paper title", "Research paper");
      assert.equal(button(page.container, "Create submission").disabled, false, "Valid forms must allow upload");
      await act(async () => form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
      await flush();
      assert.match(form.querySelector('[role="alert"]').textContent, /Paper could not be submitted.*deadline has passed.*selected file and paper details are kept/);
      assert.equal(input.files[0], file);
      assert.equal(button(page.container, "Create submission").disabled, false);
    } finally { await page.close(); }
  });
  await test("template page derives author permissions from the conference", async () => {
    role = "author"; addVersion(library);
    const page = await mount("./src/pages/LatestTemplate.jsx", {}, { authenticated: true, route: "/conferences/c/latest", pattern: "/conferences/:confId/latest" });
    try { assert.match(page.container.textContent, /Saved venue rules/); assert.doesNotMatch(page.container.textContent, /Configure a template/); }
    finally { await page.close(); }
  });
  await test("conference creation uses the canonical URL without a redirect", async () => {
    await client.createConference({ name: "Conference" });
    assert.equal(calls.at(-1).url, "/conferences/");
  });
  console.log(`${passed} onboarding scenarios passed.`);
} finally { await server.close(); dom.window.close(); }
