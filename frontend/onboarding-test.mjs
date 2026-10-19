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
let role, versions, snapshots, calls, failHistory, failPublish, failImport, failDirectory;
let library;
function reset(actor = "chair") {
  role = actor; versions = []; snapshots = new Map(); calls = [];
  failHistory = false; failPublish = false; failImport = false; failDirectory = false;
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
  else if (url === "/conferences/c/submissions") data = [];
  else if (url === "/conferences/c/settings") data = { enabled: false, settings: {}, tracks: [], submission_window: { allowed: true } };
  else if (url === "/conferences/c/workflow") data = { formatting_gate: "allow_issues", can_configure: false };
  else if (url === "/conferences/c/review-configuration") data = { form: { recommendations: ["Accept"], criteria: [] }, policy: { deadline: null, minimum_reviews: 1 }, can_configure: false };
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
async function mount(path, props = {}, { authenticated = false, route = "/", pattern = route } = {}) {
  const Component = (await server.ssrLoadModule(path)).default;
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  let tree = React.createElement(MemoryRouter, { initialEntries: [route] }, React.createElement(Routes, null,
    React.createElement(Route, { path: pattern, element: React.createElement(Component, props) })));
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
async function select(element, value) {
  await act(async () => { element.value = value; element.dispatchEvent(new window.Event("change", { bubbles: true })); });
  await flush();
}
async function loadLibrary(container) {
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
      await click(page.container, "Copy viewed version for editing");
      await click(page.container, "Publish template version");
      assert.equal(versions.length, 2); assert.deepEqual(snapshots.get("version-1"), first);
      assert.equal(library.template_id, "library");
      const comparison = [...page.container.querySelectorAll("a")].find((node) => node.textContent.includes("Compare the two latest"));
      assert.equal(comparison?.getAttribute("href"), "/conferences/c/diff?old=version-1&new=version-2");
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
      await click(page.container, "Start blank template");
      assert.ok(button(page.container, "Publish template version").disabled);
      await click(page.container, "Discard unpublished changes");
      assert.ok(!calls.some((call) => call.method === "POST"));
    } finally { await page.close(); }
  });
  await test("template import previews rules and parse errors preserve the draft", async () => {
    const page = await mount(manager, { confId: "c", canPublish: true });
    try {
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
  await test("paper list excludes submission form; dedicated submission unlocks after publishing a template", async () => {
    const listing = await mount("./src/pages/ConferencePapers.jsx", {}, { authenticated: true, route: "/conferences/c/submissions", pattern: "/conferences/:confId/submissions" });
    try { assert.ok(listing.container.querySelector(".pf-paper-list")); assert.equal(listing.container.querySelector("#new-submission"), null); }
    finally { await listing.close(); }
    const page = await mount("./src/pages/ConferencePapers.jsx", {}, { authenticated: true, route: "/conferences/c/submit", pattern: "/conferences/:confId/submit" });
    try {
      assert.equal(page.container.querySelector(".pf-paper-list"), null);
      assert.ok(page.container.querySelector('#new-submission input[type="file"]').disabled);
      await loadLibrary(page.container); await click(page.container, "Publish template version");
      assert.equal(page.container.querySelector('#new-submission input[type="file"]').disabled, false);
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
