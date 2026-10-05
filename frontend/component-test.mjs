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
import { JSDOM } from "jsdom";

const API = (process.env.API_BASE || "http://localhost:8000/api/v1").replace(/\/$/, "");

/* ---------------- real fixtures from the backend ---------------- */

async function api(path, init) {
  const res = await fetch(API + path, init);
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

console.log(
  `backend: ${batch.papers.length} papers in batch, ` +
    `accepted/rejected/review = ${batch.accepted}/${batch.rejected}/${batch.needs_review}`,
);

/* ---------------- DOM ---------------- */

const dom = new JSDOM("<!doctype html><html><body><div id=root></div></body></html>", {
  url: "http://localhost:5173/",
  pretendToBeVisual: true,
});
for (const key of ["window", "document", "navigator", "HTMLElement", "Element", "Node", "FormData", "File", "Blob", "Event", "MouseEvent", "getComputedStyle", "requestAnimationFrame", "cancelAnimationFrame"]) {
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

let failures = 0;

async function mount(mod, route, state) {
  const Page = (await server.ssrLoadModule(mod)).default;
  // A fresh container per case: MemoryRouter keeps its location across
  // re-renders, so reusing one router would leak state between cases.
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const entry = state ? { pathname: route, state } : route;
  await act(async () => {
    root.render(
      React.createElement(
        MemoryRouter,
        { initialEntries: [entry] },
        React.createElement(
          Routes,
          null,
          React.createElement(Route, { path: route, element: React.createElement(Page) }),
        ),
      ),
    );
  });
  // Let the data-loading effects settle.
  await act(async () => {
    await new Promise((r) => setTimeout(r, 300));
  });
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

await server.close();
console.log(failures ? `\n${failures} check(s) failed` : "\nall checks passed");
process.exit(failures ? 1 : 0);
