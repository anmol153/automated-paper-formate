/**
 * Component test: mounts each page in a real DOM, with the real router and real
 * effects, against real report JSON from the running backend.
 *
 * jsdom rather than a browser because the point is to prove the data-shaped code
 * paths render without errors, not to check pixels.
 *
 * Usage:
 *   cd backend && ../.venv/bin/python -m uvicorn app.main:app --port 8000 --app-dir backend &
 *   cd frontend && node component-test.mjs
 *
 * Point it elsewhere with API_BASE=http://localhost:8010/api/v1 npm run test:components
 */
import { createServer } from "vite";
import { readFile } from "node:fs/promises";
import react from "@vitejs/plugin-react";
import axios from "axios";
import { JSDOM } from "jsdom";

const API = (process.env.API_BASE || "http://localhost:8000/api/v1").replace(/\/$/, "");

/* ---------------- real fixtures from the backend ---------------- */

let accessToken = null;
async function api(path, init = {}) {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const res = await fetch(API + path, { ...init, headers });
  if (!res.ok) throw new Error(`${path} -> ${res.status} ${await res.text()}`);
  return res.json();
}

async function asFile(path, name) {
  return new File([await readFile(path)], name);
}

function multipart(entries) {
  const fd = new FormData();
  for (const [key, value] of Object.entries(entries)) {
    for (const item of Array.isArray(value) ? value : [value]) fd.append(key, item);
  }
  return fd;
}

const testEmail = `smoke-${Date.now()}@example.test`;
await api("/auth/register", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: testEmail, full_name: "Smoke Author", password: "smoke-password-123" }),
});
const session = await api("/auth/login", {
  method: "POST", body: new URLSearchParams({ username: testEmail, password: "smoke-password-123" }),
});
accessToken = session.access_token;
const chairToken = accessToken;
// Test-only bearer authentication; the application browser uses HttpOnly cookies.
axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

const rules = await api("/templates/import", {
  method: "POST",
  body: multipart({ file: await asFile("../samples/template.pdf", "template.pdf"), name: "Smoke Venue" }),
});
const saved = await api("/templates", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(rules),
});
const batch = await api("/submissions", {
  method: "POST",
  body: multipart({
    template_id: saved.template_id,
    files: [
      await asFile("../samples/paper.pdf", "paper.pdf"),
      await asFile("../samples/paper.tex", "paper.tex"),
      await asFile("../README.md", "notes.md"),
    ],
  }),
});
const single = await api("/compare", { method: "POST", body: multipart({ demo: "true" }) });
const conference = await api("/conferences/", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ name: "Revision Smoke Conference" }),
});
const inviteEmail = `invited-${Date.now()}@example.test`;
const pendingInvitation = await api(`/conferences/${conference.conference_id}/invitations`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: inviteEmail, role: "author", expires_in_days: 3 }),
});
await api('/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: inviteEmail, full_name: 'Invited Author', password: 'invited-password-123' }) });
const invitedSession = await api('/auth/login', { method: 'POST', body: new URLSearchParams({ username: inviteEmail, password: 'invited-password-123' }) });
await api(`/conferences/${conference.conference_id}/templates`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(rules),
});
const intakeTrack = await api(`/conferences/${conference.conference_id}/tracks`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "Systems research", description: "Research systems track" }) });
await api(`/conferences/${conference.conference_id}/settings`, { method: "PUT", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ expected_version: 0, settings: { abbreviation: "RSC", website: "https://example.org/conference", research_scope: "Formatting research", require_title: true, require_abstract: true, require_authors: true, require_track: true } }) });
async function participant(role) {
  const email = `${role}-${Date.now()}@example.test`;
  const user = await api("/auth/register", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, full_name: `Smoke ${role}`, password: "smoke-password-123" }) });
  const login = await api("/auth/login", { method: "POST", body: new URLSearchParams({ username: email, password: "smoke-password-123" }) });
  await api(`/conferences/${conference.conference_id}/members`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: user.user_id, role }) });
  return { user, token: login.access_token };
}
const paperAuthor = await participant("author");
const paperReviewer = await participant("reviewer");
accessToken = paperAuthor.token;
const conferencePaper = await api(`/conferences/${conference.conference_id}/submissions`, {
  method: "POST", body: multipart({ file: await asFile("../samples/paper.tex", "paper.tex"), metadata_json: JSON.stringify({ title: "Declared research paper", abstract: "A clear research abstract.", authors: [{ name: "Smoke Author", affiliation: "Smoke University" }], track_id: intakeTrack.track_id }) }),
});
const pdfPaper = await api(`/conferences/${conference.conference_id}/submissions`, {
  method: "POST", body: multipart({ file: await asFile("../samples/paper.pdf", "paper.pdf"), metadata_json: JSON.stringify({ title: "PDF viewer paper", abstract: "A PDF document for review.", authors: [{ name: "Smoke Author" }], track_id: intakeTrack.track_id }) }),
});
const pdfBase = `/submissions/${pdfPaper.submission_id}`;
const pdfRevision = (await api(pdfBase + "/revisions")).revisions[0];
await api(pdfBase + "/conversation", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body: "PDF page feedback", revision_id: pdfRevision.revision_id, page_number: 1 }) });
accessToken = chairToken;
await api(pdfBase + "/conversation", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body: "Confidential PDF page discussion", visibility: "chairs", revision_id: pdfRevision.revision_id, page_number: 1 }) });
const revisionBase = `/submissions/${conferencePaper.submission_id}`;
const firstRevision = (await api(revisionBase + "/revisions")).revisions[0];
const revisedFile = new File([(await readFile("../samples/paper.tex", "utf8")).replace("fifty papers", "sixty papers"), "\n% Revision smoke change\n"], "revised.tex");
const secondRevision = await api(revisionBase + "/revisions", {
  method: "POST", body: multipart({ file: revisedFile, parent_revision_id: firstRevision.revision_id,
    request_key: `smoke-${Date.now()}`, change_summary: "Updated the paper" }),
});
await api(revisionBase + "/check-compliance", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ revision_id: secondRevision.revision_id }),
});
await api(revisionBase + "/conversation", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ body: "Please clarify this earlier revision", revision_id: firstRevision.revision_id, page_number: 1 }),
});
await api(revisionBase + "/conversation", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ body: "Private chair observation", visibility: "chairs" }),
});

console.log(
  `backend: ${batch.papers.length} papers in batch, ` +
    `accepted/rejected/review = ${batch.accepted}/${batch.rejected}/${batch.needs_review}`,
);

/* ---------------- DOM ---------------- */

const dom = new JSDOM("<!doctype html><html><body><div id=root></div></body></html>", {
  url: "http://localhost:5173/",
  pretendToBeVisual: true,
});
for (const key of ["window", "document", "navigator", "HTMLElement", "Element", "Node", "FormData", "File", "Blob", "Event", "CustomEvent", "MouseEvent", "getComputedStyle", "requestAnimationFrame", "cancelAnimationFrame"]) {
  // Node 22 defines some of these as getter-only on globalThis.
  try {
    globalThis[key] = dom.window[key];
  } catch {
    Object.defineProperty(globalThis, key, {
      value: dom.window[key],
      configurable: true,
      writable: true,
    });
  }
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const server = await createServer({
  configFile: false,
  root: ".",
  server: { middlewareMode: true, hmr: false },
  appType: "custom",
  plugins: [react()],
  // The app defaults to the relative "/api/v1" that the Vite proxy rewrites;
  // there is no proxy in this harness, so point it at the backend directly.
  define: { "import.meta.env.VITE_API_BASE": JSON.stringify(API) },
  // Keep React external so the app modules and this test share one instance.
  // Inlining the CJS react-dom/client both breaks parsing and duplicates React,
  // which shows up as "invalid hook call" rather than anything obvious.
  ssr: { external: ["react", "react-dom", "react-dom/client", "react-router-dom"] },
});

const { createRoot } = await import("react-dom/client");
const React = (await import("react")).default;
const { act } = await import("react");
const { MemoryRouter, Routes, Route } = await import("react-router-dom");

async function asUser(token) {
  accessToken = token;
  axios.defaults.headers.common.Authorization = `Bearer ${token}`;
  const client = await server.ssrLoadModule("./src/lib/api.js");
  client.api.defaults.headers.common.Authorization = `Bearer ${token}`;
}

let failures = 0;

async function settle(container) {
  // Auth restoration, paper loading, then report loading are successive effects.
  // Flush each render so a timer in one act() does not mask the next request.
  for (let attempt = 0; attempt < 40; attempt += 1) {
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
    const loading = [...container.querySelectorAll('[role="status"]')]
      .some((node) => node.textContent.startsWith("Loading"));
    if (!loading) return;
  }
  throw new Error(`Page did not finish loading: ${container.textContent}`);
}

async function mount(mod, route, state, { pattern = route, authenticated = false, interact } = {}) {
  const Page = (await server.ssrLoadModule(mod)).default;
  const { AuthProvider } = await server.ssrLoadModule("./src/context/AuthContext.jsx");
  // A fresh container per case: MemoryRouter keeps its location across
  // re-renders, so reusing one router would leak state between cases.
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const entry = state ? { pathname: route, state } : route;
  let tree = React.createElement(
        MemoryRouter,
        { initialEntries: [entry] },
        React.createElement(
          Routes,
          null,
          React.createElement(Route, { path: pattern, element: React.createElement(Page) }),
        ),
      );
  if (authenticated) tree = React.createElement(AuthProvider, null, tree);
  await act(async () => {
    root.render(tree);
  });
  // Let the data-loading effects settle.
  await act(async () => {
    await new Promise((r) => setTimeout(r, 300));
  });
  await settle(container);
  if (interact) {
    await act(async () => { await interact(container); });
    await settle(container);
  }
  const result = { html: container.innerHTML, text: container.textContent };
  await act(async () => {
    root.unmount();
  });
  container.remove();
  return result;
}

function check(label, cond, detail) {
  if (cond) {
    console.log(`  OK   ${label}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${label} — ${detail}`);
  }
}

/* ---------------- cases ---------------- */

console.log("\nResults — batch report");
{
  const { html, text } = await mount("./src/pages/Results.jsx", "/results", { report: batch });
  for (const p of batch.papers) {
    check(`renders ${p.filename}`, html.includes(p.filename), "filename absent from DOM");
  }
  const blocking = batch.papers.flatMap((p) => p.blocking_reasons);
  if (blocking.length) {
    check("renders a blocking reason name", text.includes(blocking[0].name), `${blocking[0].name} absent`);
    const withAdvice = blocking.find((b) => b.advice);
    if (withAdvice) {
      check(
        "renders remediation advice",
        text.includes(withAdvice.advice.slice(0, 40)),
        "advice absent",
      );
    }
  }
  check("shows the checks disclosure", text.includes("Show all"), "no 'Show all' control");
  check(
    "tallies the batch",
    text.includes("papers") && text.includes(batch.template_name),
    "batch header missing template name / count",
  );
}

console.log("\nResults — single comparison report");
{
  const { text } = await mount("./src/pages/Results.jsx", "/results", { report: single, demo: true });
  check("renders the single-report header", text.includes("Overall compliance"), "header absent");
  check("marks it as demo data", text.includes("demo data"), "demo badge absent");
}

console.log("\nResults — no report");
{
  const { text } = await mount("./src/pages/Results.jsx", "/results", undefined);
  check("shows the empty state", text.includes("No report yet"), "empty state absent");
}

console.log("\nSubmit — template picker and multi-file zone");
{
  const { text, html } = await mount("./src/pages/Submit.jsx", "/submit", undefined);
  check("lists the saved template", text.includes("Smoke Venue"), "template absent from the select");
  check("offers the Drive tab", text.includes("Google Drive folder"), "Drive tab absent");
  check("renders the multi-file drop zone", text.includes("Drop papers here"), "drop zone absent");
  check("offers paste", text.toLowerCase().includes("paste"), "paste affordance absent");
  check("has a multi-select file input", html.includes('type="file"') && html.includes("multiple"), "input not multiple");
}

console.log("\nSetup — rule editor");
{
  const { text } = await mount("./src/pages/Setup.jsx", "/setup", undefined);
  check("renders template setup", text.includes("Template setup"), "heading absent");
  check("has an import step", text.includes("Import rules"), "import control absent");
  check("renders the file type panel", text.includes("Accepted files"), "panel absent");
  check("renders page setup panel", text.includes("Page setup"), "panel absent");
  check("renders anonymisation panel", text.includes("Anonymisation"), "panel absent");
  check("renders the decision panel", text.includes("Decision"), "panel absent");
  check("explains the metadata false-positive tradeoff", text.includes("rarely identify anyone"), "hint absent");
}

console.log("\nCompare — legacy single-pair flow");
{
  const { text } = await mount("./src/pages/Home.jsx", "/compare", undefined);
  check("renders the comparison form", text.includes("Check a paper against a template"), "heading absent");
  check("offers demo data", text.includes("Try demo data"), "demo button absent");
}

console.log("\nLogin — account form");
{
  const { text, html } = await mount("./src/pages/Login.jsx", "/login");
  check("renders sign in", text.includes("Sign in"), "sign-in heading absent");
  check("offers account creation", text.includes("Create an account"), "registration absent");
  check("has password and email inputs", html.includes('type="password"') && html.includes('type="email"'), "credentials absent");
  check("does not persist bearer tokens", !window.localStorage.getItem("access_token"), "token stored in localStorage");
  check("offers Google sign-in with a disabled fallback", text.includes("Continue with Google") && text.includes("Google sign-in is currently unavailable"), "Google login fallback missing");
}

console.log("\nAccount — connected sign-in methods");
{
  const account = await mount("./src/pages/Account.jsx", "/account", undefined, { authenticated: true });
  check("shows current account and Google connection entry", account.text.includes("Account settings") && account.text.includes(testEmail) && account.text.includes("Connect your Google account"), "account connection view missing");
  check("exposes an account ID without browser console commands", account.text.includes("Your account ID") && account.text.includes("Copy account ID") && account.html.includes((await api("/auth/me")).user_id), "account ID missing");
}

console.log("\nConference onboarding — chair memberships and templates");
{
  const members = await mount("./src/pages/Conferences.jsx", "/conferences", undefined, { authenticated: true,
    interact: (container) => [...container.querySelectorAll("button")].find((node) => node.textContent.trim() === "Members").click(),
  });
  check("chairs can see and manage conference participants", members.text.includes("Add Member") && members.text.includes(paperAuthor.user.user_id), "chair member list missing");
  check("chairs can create and track private invitations", members.text.includes("Create invitation link") && members.text.includes(inviteEmail) && !members.html.includes(pendingInvitation.token), "invitation controls/history missing or secret exposed");
  check("does not offer unsupported conference deletion", !members.text.includes("Delete"), "unsupported deletion offered");
  const templates = await mount("./src/pages/LatestTemplate.jsx", `/conferences/${conference.conference_id}/latest`, undefined,
    { authenticated: true, pattern: "/conferences/:confId/latest" });
  check("chairs can publish template versions from the existing page", templates.text.includes("Configure a template") && templates.text.includes("Load saved rules") && templates.text.includes("Published template version"), "template publication controls missing");
}

console.log("\nConference papers — private submission list");
{
  const { text } = await mount("./src/pages/ConferencePapers.jsx", `/conferences/${conference.conference_id}/submissions`, undefined,
    { pattern: "/conferences/:confId/submissions", authenticated: true });
  check("shows the conference", text.includes(conference.name), "conference name missing");
  check("lists the current file", text.includes("revised.tex"), "paper missing");
  check("keeps the submission form off the paper list", !text.includes("Create submission"), "submission form still appears on listing");
  check("shows configurable formatting policy", text.includes("Submission formatting policy") && text.includes("Save policy"), "policy controls missing");
  check("shows conference scheduling and track controls", text.includes("Submission opening time") && text.includes("Requested revision deadline") && text.includes("Systems research"), "conference settings missing");
  const submission = await mount("./src/pages/ConferencePapers.jsx", `/conferences/${conference.conference_id}/submit`, undefined,
    { pattern: "/conferences/:confId/submit", authenticated: true });
  check("offers declared submission metadata on its own page", submission.text.includes("Paper title") && submission.text.includes("Abstract") && submission.text.includes("Add author") && submission.text.includes("Create submission"), "dedicated submission form missing");
  check("chairs have conference template setup beside the submission form", text.includes("Configure a template") && text.includes("Copy viewed version for editing"), "template setup missing");
}

console.log("\nSubmission — revision history and retained reports");
{
  const route = `/submissions/${conferencePaper.submission_id}`;
  const options = { pattern: "/submissions/:submissionId", authenticated: true };
  const { text } = await mount("./src/pages/SubmissionDetail.jsx", route, undefined, options);
  check("shows the current revision", text.includes("Current revision 2"), "current revision missing");
  check("shows lifecycle actions", text.includes("Next actions") && text.includes("Apply action"), "lifecycle actions missing");
  check("shows collaborator management", text.includes("Grant paper access"), "collaborator form missing");
  check("shows stable paper number and declared title", text.includes("Paper #1") && text.includes("Declared research paper"), "paper identity missing");
  const files = await mount("./src/pages/SubmissionDetail.jsx", route, undefined, {
    ...options, interact: (container) => [...container.querySelectorAll("button")].find((b) => b.textContent === "Files and revisions").click(),
  });
  check("offers the next revision", files.text.includes("Upload revision 3"), "revision form missing");
  check("downloads the selected file", files.text.includes("Download revised.tex"), "download control missing");
  const comparison = await mount("./src/pages/SubmissionDetail.jsx", `${route}?tab=compare`, undefined, {
    ...options, interact: async (container) => {
      container.querySelector('section[aria-label="Revision comparison"] form').dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
    },
  });
  check("compares retained formatting findings", comparison.text.includes("Formatting finding changes") && comparison.text.includes("Remaining:"), "finding diff missing");
  check("compares extracted properties", comparison.text.includes("Saved document properties") || comparison.html.includes("Saved document properties"), "property comparison missing");
  check("pins exact saved report snapshots", comparison.text.includes("Run 1") && comparison.text.includes("Run 2") && comparison.text.includes("check-"), "exact reports missing");
  const textComparison = await mount("./src/pages/SubmissionDetail.jsx", `${route}?tab=compare&compare_text=1`, undefined, {
    ...options, interact: (container) => container.querySelector('section[aria-label="Revision comparison"] form').dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })),
  });
  check("renders added and removed extracted text", textComparison.html.includes('aria-label="added"') && textComparison.html.includes('aria-label="removed"') && textComparison.text.includes("sixty papers") && textComparison.text.includes("fifty papers"), "text hunks missing");
  check("explains text diff limitations", textComparison.text.includes("Line numbers refer to extracted text, not pages"), "text limitations missing");
  const reports = await mount("./src/pages/SubmissionDetail.jsx", route, undefined, {
    ...options, interact: (container) => [...container.querySelectorAll("button")].find((b) => b.textContent === "Formatting checks").click(),
  });
  check("retains earlier check attempts", reports.text.includes("Run 1") && reports.text.includes("Run 2"), "report history missing");
  check("reuses detailed formatting findings", reports.text.includes("Show all"), "detailed checks missing");
  const runs = await api(revisionBase + `/revisions/${secondRevision.revision_id}/checks`);
  await mount("./src/pages/SubmissionDetail.jsx", `${route}?revision=${secondRevision.revision_id}&tab=checks&run=${runs.at(-1).run_id}`, undefined, {
    ...options, interact: (container) => check("opens the exact saved report link", [...container.querySelectorAll("select")].some((select) => select.value === runs.at(-1).run_id), "pinned report not selected"),
  });
  const missingRun = await mount("./src/pages/SubmissionDetail.jsx", `${route}?tab=checks&run=unknown`, undefined, options);
  check("does not substitute an unavailable linked report", missingRun.text.includes("requested saved report is unavailable") && !missingRun.text.includes("Show all"), "missing report silently replaced");
  const old = await mount("./src/pages/SubmissionDetail.jsx", `${route}?revision=${firstRevision.revision_id}`, undefined, options);
  check("marks an earlier revision", old.text.includes("earlier upload"), "old revision warning missing");
  const conversation = await mount("./src/pages/SubmissionDetail.jsx", route, undefined, {
    ...options, interact: (container) => [...container.querySelectorAll("button")].find((b) => b.textContent === "Conversation").click(),
  });
  check("shows revision-linked comments", conversation.text.includes("Please clarify this earlier revision") && conversation.text.includes("Earlier version"), "revision comment missing");
  check("offers discussion resolution and replies", conversation.text.includes("Resolve thread") && conversation.text.includes("Post reply"), "thread controls missing");
  check("chairs see confidential discussion", conversation.text.includes("Private chair observation") && conversation.text.includes("Confidential"), "chair thread missing");
  const activity = await mount("./src/pages/SubmissionDetail.jsx", route, undefined, {
    ...options, interact: (container) => [...container.querySelectorAll("button")].find((b) => b.textContent === "Activity").click(),
  });
  check("shows the activity timeline", activity.text.includes("submission · created") && activity.text.includes("revision · uploaded"), "activity events missing");
}

console.log("\nConference invitation — explicit authenticated acceptance");
{
  await asUser(invitedSession.access_token);
  const path = `/invitations#token=${pendingInvitation.token}`;
  const invitation = await mount('./src/pages/Invitation.jsx', path, undefined, { authenticated: true, pattern: '/invitations' });
  check('invited account can inspect before joining', invitation.text.includes(conference.name) && invitation.text.includes('Accept invitation'), 'recipient inspection missing');
  const accepted = await mount('./src/pages/Invitation.jsx', path, undefined, { authenticated: true, pattern: '/invitations',
    interact: (container) => [...container.querySelectorAll('button')].find((node) => node.textContent === 'Accept invitation').click(),
  });
  check('explicit acceptance grants conference access', accepted.text.includes('Invitation accepted') && accepted.html.includes(`/conferences/${conference.conference_id}/submissions`), 'accepted conference link missing');
  const member = await api(`/conferences/${conference.conference_id}`);
  check('accepted membership is readable but private member lists stay hidden', member.conference_id === conference.conference_id && member.members.length === 0, 'accepted membership/privacy incorrect');
  await asUser(chairToken);
}

console.log("\nDocument review — authenticated PDF and page discussions");
{
  const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL;
  const created = [], revoked = [];
  URL.createObjectURL = () => { const value = `blob:integration-${created.length}`; created.push(value); return value; };
  URL.revokeObjectURL = (value) => revoked.push(value);
  try {
    const path = `${pdfBase}?tab=document&revision=${pdfRevision.revision_id}&page=1`;
    const options = { authenticated: true, pattern: "/submissions/:submissionId" };
    const chair = await mount("./src/pages/SubmissionDetail.jsx", path, undefined, options);
    check("PDF preview uses an authorized local blob", chair.html.includes("blob:integration-") && chair.html.includes("Paper revision 1, page 1"), "protected PDF frame missing");
    check("direct document links load chair visibility controls", chair.text.includes("Comment visibility") && chair.text.includes("Confidential PDF page discussion"), "direct-link chair access missing");
    await asUser(paperAuthor.token);
    const author = await mount("./src/pages/SubmissionDetail.jsx", path, undefined, options);
    check("author sees page feedback without confidential discussion", author.text.includes("PDF page feedback") && !author.text.includes("Confidential PDF page discussion") && !author.text.includes("Comment visibility"), "confidential page thread leaked");
    const source = await mount("./src/pages/SubmissionDetail.jsx", `${revisionBase}?tab=document&revision=${firstRevision.revision_id}&page=1`, undefined, options);
    check("source documents retain original revision anchors and download fallback", source.text.includes("Inline preview supports PDF") && source.text.includes("Please clarify this earlier revision") && source.text.includes("Download original"), "source fallback/anchor missing");
    check("preview blob URLs are released on leaving the document", created.length > 0 && created.every((value) => revoked.includes(value)), "preview memory retained after unmount");
  } finally {
    URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke;
    await asUser(chairToken);
  }
}

console.log("\nConference intake — declared metadata and access");
{
  await asUser(paperAuthor.token);
  const route = `/submissions/${conferencePaper.submission_id}`;
  const options = { pattern: "/submissions/:submissionId", authenticated: true };
  const author = await mount("./src/pages/SubmissionDetail.jsx", route, undefined, options);
  check("authors can edit declared metadata", author.text.includes("Save paper details") && author.html.includes("Smoke University"), "metadata editor missing");
  const original = (await api(revisionBase + "/metadata")).metadata;
  await api(revisionBase + "/metadata", { method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_version: original.version, expected_revision_id: secondRevision.revision_id,
      title: "Updated declared research paper", abstract: original.abstract, authors: original.authors, track_id: original.track_id }) });
  const updated = await mount("./src/pages/SubmissionDetail.jsx", route, undefined, { ...options,
    interact: (container) => [...container.querySelectorAll("button")].find((button) => button.textContent === "View metadata history").click(),
  });
  check("retains declared metadata history", updated.text.includes("Updated declared research paper") && updated.text.includes("Metadata version 1") && updated.text.includes("Metadata version 2"), "metadata history missing");
  const conferenceView = await mount("./src/pages/ConferencePapers.jsx", `/conferences/${conference.conference_id}/submissions`, undefined, { pattern: "/conferences/:confId/submissions", authenticated: true });
  check("author sees settings without chair controls", conferenceView.text.includes("Initial submissions open") && !conferenceView.text.includes("Save conference settings") && !conferenceView.text.includes("Create track"), "chair controls leaked");
  check("authors can read conference templates without publication controls", conferenceView.text.includes("Published template version") && !conferenceView.text.includes("Configure a template"), "author template permissions incorrect");
  await asUser(chairToken);
}

console.log("\nFormal reviews — configure, draft, submit, release");
{
  const route = `/submissions/${conferencePaper.submission_id}`;
  const options = { pattern: "/submissions/:submissionId", authenticated: true,
    interact: (container) => [...container.querySelectorAll("button")].find((b) => b.textContent === "Reviews").click() };
  const config = await api(`/conferences/${conference.conference_id}/review-configuration`);
  const form = { name: "Smoke review form", criteria: [
    { id: "quality", label: "Technical quality", kind: "score", required: true, visibility: "authors", minimum: 1, maximum: 5 },
    { id: "strengths", label: "Strengths", kind: "text", required: true, visibility: "authors" },
    { id: "confidence", label: "Chair confidence", kind: "score", required: false, visibility: "chairs", minimum: 1, maximum: 5 },
  ], recommendations: ["Accept", "Reject"] };
  const configured = await api(`/conferences/${conference.conference_id}/review-configuration`, { method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_version: config.version, form, policy: { ...config.policy, minimum_reviews: 1 } }) });
  const assignment = await api(revisionBase + "/review", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(paperReviewer.user.user_id) });
  await asUser(paperReviewer.token);
  let reviewer = await mount("./src/pages/SubmissionDetail.jsx", route, undefined, options);
  check("renders configurable review fields", reviewer.text.includes("Technical quality") && reviewer.text.includes("Strengths"), "review fields missing");
  check("offers draft and formal submission", reviewer.text.includes("Save private draft") && reviewer.text.includes("Submit formal review"), "review actions missing");
  const body = { assignment_id: assignment.assignment_id, revision_id: secondRevision.revision_id, form_id: configured.form_id, expected_version: 0,
    submit: false, recommendation: "Accept", answers: { quality: 4, strengths: "Clear research contribution", confidence: 5 }, confidential_comments: "Private review details for chairs" };
  await api(revisionBase + "/reviews/mine", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  body.submit = true; body.expected_version = 1;
  await api(revisionBase + "/reviews/mine", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const workspace = await mount("./src/pages/ReviewerWorkspace.jsx", "/reviewer", undefined, { authenticated: true });
  check("reviewer workspace shows submitted review", workspace.text.includes("Review: submitted") && workspace.text.includes("revised.tex"), "review workspace missing assignment");
  await asUser(paperAuthor.token);
  const before = await mount("./src/pages/SubmissionDetail.jsx", route, undefined, options);
  check("authors cannot see unreleased reviews", before.text.includes("No reviews are visible") && !before.text.includes("Clear research contribution"), "unreleased review leaked");
  await asUser(chairToken);
  const chair = await mount("./src/pages/SubmissionDetail.jsx", route, undefined, options);
  check("chair sees review progress and private notes", chair.text.includes("1 submitted") && chair.text.includes("Private review details for chairs"), "chair review details missing");
  await api(revisionBase + "/reviews/release", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision_id: secondRevision.revision_id }) });
  await asUser(paperAuthor.token);
  const released = await mount("./src/pages/SubmissionDetail.jsx", route, undefined, options);
  check("authors see released review content", released.text.includes("Clear research contribution") && released.text.includes("Reviewer"), "released review missing");
  check("private review fields stay hidden", !released.text.includes("Private review details for chairs") && !released.text.includes("Chair confidence"), "private review data leaked");
}

console.log("\nNotification center — authorized feed and read controls");
{
  await asUser(paperAuthor.token);
  const feed = await api('/notifications/feed?limit=2');
  check("returns a bounded authorized notification page", feed.items.length > 0 && feed.items.length <= 2 && feed.items.every((item) => item.email === null && item.body !== 'Private review details for chairs'), "notification feed missing or private content exposed");
  const history = await mount('./src/pages/Notifications.jsx', '/notifications', undefined, { authenticated: true });
  check("renders real notification history with timestamps and links", history.text.includes('Unread only') && history.html.includes('<time') && history.html.includes(`/submissions/${conferencePaper.submission_id}`), "notification history missing");
  const first = feed.items[0];
  const updated = await mount('./src/pages/Notifications.jsx', '/notifications', undefined, { authenticated: true,
    interact: (container) => container.querySelector(`button[aria-label="Mark ${first.title} as read"]`).click() });
  check("marking read persists through the real API", (await api('/notifications/feed')).items.find((item) => item.notification_id === first.notification_id)?.read === true && !updated.text.includes('Read update failed'), "read state did not persist");
  const menu = await mount('./src/components/NotificationDropdown.jsx', '/notifications', undefined, { authenticated: true,
    interact: (container) => container.querySelector('button').click() });
  check("notification menu opens and offers complete history", menu.html.includes('aria-expanded="true"') && menu.text.includes('View all notifications'), "menu did not open");
  await api('/notifications/read-all', { method: 'PATCH' });
  check("mark all read clears the authorized count", (await api('/notifications/count-unread')).count === 0, "unread count not cleared");
}

console.log("\nGoogle SDK — configured rendering and rejected credential");
{
  // Only this external-provider UI branch is stubbed. Backend tests separately
  // verify real RSA signatures and cookie sessions without live Google accounts.
  const { api: appApi } = await server.ssrLoadModule("./src/lib/api.js");
  const adapter = appApi.defaults.adapter;
  const realAdapter = axios.getAdapter(adapter);
  const previousGoogle = window.google;
  let initialized;
  window.google = { accounts: { id: {
    initialize: (options) => { initialized = options; },
    renderButton: (container) => { const button = document.createElement("button"); button.textContent = "Google chooser test button"; container.appendChild(button); },
  } } };
  appApi.defaults.adapter = async (config) => {
    const response = (data) => ({ data, status: 200, statusText: "OK", headers: {}, config });
    if (config.url === "/auth/google/config") return response({ enabled: true, client_id: "test-client.apps.googleusercontent.com" });
    if (config.url === "/auth/google/challenge") return response({ challenge_id: "test-challenge-".repeat(3), nonce: "test-browser-nonce", client_id: "test-client.apps.googleusercontent.com" });
    if (config.url === "/auth/google/complete") throw new axios.AxiosError("Rejected Google token", "ERR_BAD_REQUEST", config, undefined, { status: 401, data: { detail: "Google could not verify this sign-in; try again" }, headers: {} });
    return realAdapter(config);
  };
  try {
    const google = await mount("./src/pages/Login.jsx", "/login", undefined, { authenticated: true, interact: async (container) => {
      check("passes nonce to the Google account chooser", initialized?.nonce === "test-browser-nonce" && initialized.auto_select === false && container.textContent.includes("Google chooser test button"), "nonce or chooser missing");
      await initialized.callback({ credential: "test-only-invalid-credential" });
    } });
    check("offers retry after Google verification failure", google.text.includes("Google could not verify") && google.text.includes("Retry Google sign-in"), "Google failure recovery missing");
    check("does not store Google credentials in browser storage", !Object.values(window.localStorage).includes("test-only-invalid-credential") && !Object.values(window.sessionStorage).includes("test-only-invalid-credential"), "Google credential persisted");
  } finally {
    appApi.defaults.adapter = adapter;
    window.google = previousGoogle;
  }
}

await server.close();
console.log(failures ? `\n${failures} check(s) failed` : "\nall checks passed");
process.exit(failures ? 1 : 0);
