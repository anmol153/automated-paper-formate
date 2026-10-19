/** D1 shell tests use an isolated API adapter, never the selected local database. */
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import react from '@vitejs/plugin-react';
import { JSDOM } from 'jsdom';
import { AxiosError } from 'axios';
const dom = new JSDOM('<!doctype html><body></body>', { url: 'http://localhost:5173/', pretendToBeVisual: true });
for (const key of ['window','document','navigator','localStorage','HTMLElement','Element','Node','Event','CustomEvent','MouseEvent','KeyboardEvent','getComputedStyle','requestAnimationFrame','cancelAnimationFrame']) Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let wide = true;
const listeners = new Set();
window.matchMedia = (query) => ({ get matches() { return query.includes('1280') && wide; }, media: query,
  addEventListener: (type, callback) => listeners.add(callback), removeEventListener: (type, callback) => listeners.delete(callback) });
// JSDOM has no native modal implementation. Real focus containment/Escape are
// additionally checked in Chromium; this shim verifies our lifecycle integration.
window.HTMLDialogElement.prototype.showModal = function () { this.open = true; this.querySelector('button')?.focus(); };
window.HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new window.Event('close')); };
const React = await import('react'); const { act } = React;
const { createRoot } = await import('react-dom/client');
const { MemoryRouter, useLocation } = await import('react-router-dom');
const server = await createServer({ configFile: false, root: '.', appType: 'custom', plugins: [react()], server: { middlewareMode: true, hmr: false }, define: { 'import.meta.env.VITE_API_BASE': JSON.stringify('http://api.test/api/v1') }, ssr: { external: ['react','react-dom','react-dom/client','react-router-dom'] } });
const { api } = await server.ssrLoadModule('./src/lib/api.js');
const { AuthProvider, useAuth } = await server.ssrLoadModule('./src/context/AuthContext.jsx');
const App = (await server.ssrLoadModule('./src/App.jsx')).default;
let user, calls, failLogout;
function reset() { user = null; calls = []; failLogout = false; wide = true; document.documentElement.classList.remove('dark'); window.localStorage.clear(); }
function reject(config, detail, status = 503) { throw new AxiosError(detail, 'ERR_BAD_RESPONSE', config, null, { config, status, data: { detail }, headers: {} }); }
api.defaults.adapter = async (config) => {
  calls.push(config); let data;
  if (config.url === '/auth/me') { if (!user) reject(config, 'Sign in', 401); data = user; }
  else if (config.url === '/auth/logout') { if (failLogout) reject(config, 'Sign-out temporarily unavailable'); user = null; data = {}; }
  else if (config.url === '/auth/google/config') data = { enabled: false };
  else if (config.url === '/notifications/count-unread') data = { count: 0 };
  else if (config.url === '/notifications/feed') data = { items: [], next_cursor: null };
  else if (config.url === '/conferences' || config.url === '/conferences/' || config.url === '/templates') data = [];
  else if (config.url === '/reviewer/workspace') data = { assignments: [], conflicts: [] };
  else if (config.url === '/drive/status') data = { configured: false };
  else throw new Error(`Unexpected ${config.method} ${config.url}`);
  return { data: structuredClone(data), config, headers: {}, status: 200, statusText: 'OK' };
};
async function flush() { for (let i = 0; i < 5; i++) await act(async () => { await new Promise((resolve) => setTimeout(resolve, 5)); }); }
async function mount(route = '/results', element = React.createElement(App)) {
  const container = document.createElement('div'); document.body.appendChild(container); const root = createRoot(container);
  let auth, location;
  function Probe() { auth = useAuth(); location = useLocation(); return null; }
  await act(async () => root.render(React.createElement(AuthProvider, null, React.createElement(MemoryRouter, { initialEntries: [route] }, element, React.createElement(Probe))))); await flush();
  return { container, auth: () => auth, location: () => location, close: async () => { await act(async () => root.unmount()); container.remove(); assert.equal(document.body.style.overflow, ''); assert.equal(listeners.size, 0); } };
}
function findButton(view, name) { const node = [...view.container.querySelectorAll('button')].find((node) => node.getAttribute('aria-label') === name || node.textContent === name); assert.ok(node, `Missing ${name}`); return node; }
async function click(view, name) { await act(async () => findButton(view, name).click()); await flush(); }
const account = (id) => ({ user_id: id, full_name: `Test participant ${id}`, email: `${id}@example.test` });
let passed = 0;
async function test(name, run) { reset(); await run(); passed++; console.log(`OK ${name}`); }
try {
  await test('legacy results route and page body render within the new shell', async () => {
    const view = await mount();
    try {
      assert.match(view.container.textContent, /No report yet/); assert.equal(view.container.querySelectorAll('main').length, 1);
      assert.equal(view.container.querySelector('.pf-skip-link').getAttribute('href'), '#main-content');
      assert.ok(view.container.querySelector('#main-content[tabindex="-1"]'));
      assert.equal(view.container.querySelectorAll('[role="tablist"]').length, 0);
      assert.ok(view.container.querySelector('a[href="/dashboard"]'), 'Dashboard is reachable from the shell');
      assert.ok(!calls.some((call) => call.url.startsWith('/notifications')));
    } finally { await view.close(); }
  });
  await test('navigation collapse preserves link names and the expansion control has a real target', async () => {
    const view = await mount('/compare');
    try {
      assert.ok(document.getElementById(findButton(view, 'Collapse navigation').getAttribute('aria-controls')));
      await click(view, 'Collapse navigation'); assert.ok(view.container.querySelector('.pf-shell.is-compact'));
      const active = view.container.querySelector('.pf-sidebar a[aria-current="page"]');
      assert.equal(active.getAttribute('aria-label'), 'Compare documents'); assert.equal(active.title, 'Compare documents');
      await click(view, 'Expand navigation'); assert.ok(!view.container.querySelector('.pf-shell.is-compact'));
    } finally { await view.close(); }
  });
  await test('mobile drawer opens, locks background scroll, and restores focus on close', async () => {
    wide = false; const view = await mount();
    try {
      const trigger = findButton(view, 'Open navigation'); await act(async () => trigger.click()); await flush();
      const dialog = view.container.querySelector('dialog'); assert.equal(dialog.open, true); assert.equal(document.body.style.overflow, 'hidden');
      assert.equal(trigger.getAttribute('aria-expanded'), 'true');
      await click(view, 'Close navigation'); assert.equal(dialog.open, false); assert.equal(document.activeElement, trigger);
      assert.equal(document.body.style.overflow, '');
    } finally { await view.close(); }
  });
  await test('drawer navigation changes the real route, selects its link and closes', async () => {
    wide = false; const view = await mount();
    try {
      await click(view, 'Open navigation');
      await act(async () => view.container.querySelector('dialog a[href="/conferences"]').click()); await flush();
      assert.equal(view.location().pathname, '/conferences'); assert.equal(view.container.querySelector('dialog').open, false);
      assert.equal(view.container.querySelector('.pf-sidebar a[aria-current="page"]').getAttribute('href'), '/conferences');
      assert.match(view.container.querySelector('main').textContent, /Create conference/);
    } finally { await view.close(); }
  });
  await test('paper deep links preserve historical revision, run, page and comparison parameters', async () => {
    const query = '?tab=document&revision=r1&run=check1&page=2&compare_base=r1&compare_target=r2&base_run=a&target_run=b&compare_text=1';
    const view = await mount('/submissions/paper-one' + query);
    try { assert.equal(view.location().search, query); assert.ok(view.container.querySelector('.pf-shell.is-compact')); assert.match(view.container.textContent, /Sign in to view this paper/); assert.match(view.container.querySelector('.pf-breadcrumbs').textContent, /Paper workspace/); }
    finally { await view.close(); }
  });
  await test('invitation fragments survive shell mounting and drawer state changes', async () => {
    wide = false; const fragment = '#token=' + 'a'.repeat(43); const view = await mount('/invitations' + fragment);
    try { await click(view, 'Open navigation'); await click(view, 'Close navigation'); assert.equal(view.location().hash, fragment); assert.ok(!calls.some((call) => call.url === '/invitations/accept')); }
    finally { await view.close(); }
  });
  await test('theme control shows a light-mode icon and toggles/restores its preference', async () => {
    const view = await mount();
    try {
      const light = findButton(view, 'Switch to dark mode'); assert.match(light.querySelector('svg').style.transform, /scale\(1\)/);
      await click(view, 'Switch to dark mode'); assert.ok(document.documentElement.classList.contains('dark')); assert.equal(window.localStorage.getItem('theme'), 'dark');
      await click(view, 'Switch to light mode'); assert.ok(!document.documentElement.classList.contains('dark'));
    } finally { await view.close(); }
  });
  await test('account replacement remounts private page content and notification identity', async () => {
    user = account('a'); const view = await mount('/reviewer');
    try {
      const oldMain = view.container.querySelector('main'); assert.match(view.container.textContent, /Test participant a/);
      user = account('b'); await act(async () => { await view.auth().refresh(); }); await flush();
      assert.notEqual(view.container.querySelector('main'), oldMain); assert.doesNotMatch(view.container.textContent, /Test participant a/); assert.match(view.container.textContent, /Test participant b/);
      assert.ok(view.container.querySelector('a[href="/notifications"]'));
    } finally { await view.close(); }
  });
  await test('sign-out errors remain visible, then successful retry clears account navigation', async () => {
    user = account('a'); const view = await mount();
    try {
      await click(view, 'Account menu');
      failLogout = true; await click(view, 'Sign out'); assert.match(view.container.textContent, /Sign-out temporarily unavailable/); assert.ok(view.auth().user);
      failLogout = false; await click(view, 'Sign out'); assert.equal(view.auth().user, null); assert.doesNotMatch(view.container.textContent, /Test participant a/);
      assert.equal(view.container.querySelector('.pf-sidebar a[href="/notifications"]'), null);
    } finally { await view.close(); }
  });
  await test('sidebar account menu exposes working destinations and closes after navigation', async () => {
    user = account('a'); const view = await mount();
    try {
      assert.ok(view.container.querySelector('.pf-sidebar-account .pf-account-trigger'));
      await click(view, 'Account menu');
      const menu = view.container.querySelector('[role="menu"][aria-label="Account options"]');
      assert.ok(menu); assert.deepEqual([...menu.querySelectorAll('a')].map((node) => node.getAttribute('href')), ['/account','/my-invitations','/my-schedule','/docs']);
      await act(async () => menu.querySelector('a[href="/docs"]').click()); await flush();
      assert.equal(view.location().pathname, '/docs'); assert.equal(view.container.querySelector('[role="menu"][aria-label="Account options"]'), null);
      assert.match(view.container.querySelector('main').textContent, /A quick guide/);
    } finally { await view.close(); }
  });
  await test('account menu supports arrow keys, Escape focus return and outside dismissal', async () => {
    user = account('a'); const view = await mount();
    try {
      const trigger = findButton(view, 'Account menu'); await click(view, 'Account menu');
      assert.equal(document.activeElement.textContent, 'Settings');
      await act(async () => document.activeElement.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'End', bubbles: true, cancelable: true })));
      assert.equal(document.activeElement.textContent, 'Sign out');
      await act(async () => document.activeElement.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true })));
      assert.equal(document.activeElement.textContent, 'Settings');
      await act(async () => document.activeElement.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })));
      assert.equal(document.activeElement, trigger); assert.equal(trigger.getAttribute('aria-expanded'), 'false');
      await click(view, 'Account menu'); await act(async () => document.body.dispatchEvent(new window.Event('pointerdown', { bubbles: true })));
      assert.equal(trigger.getAttribute('aria-expanded'), 'false');
    } finally { await view.close(); }
  });
  await test('resizing to desktop closes an open drawer and releases its scroll lock', async () => {
    wide = false; const view = await mount();
    try { await click(view, 'Open navigation'); await act(async () => { wide = true; for (const callback of listeners) callback(); }); await flush(); assert.equal(view.container.querySelector('dialog').open, false); assert.equal(document.body.style.overflow, ''); }
    finally { await view.close(); }
  });
  await test('drawer wraps forward and reverse keyboard focus at its visible controls', async () => {
    wide = false; const view = await mount();
    try {
      await click(view, 'Open navigation');
      const controls = [...view.container.querySelectorAll('dialog a[href], dialog button')];
      // JSDOM has no layout; declare these rendered controls visible for this
      // focus-policy test. Chromium separately verifies the real visibility/layout.
      for (const control of controls) control.getClientRects = () => [{}];
      const first = controls[0], last = controls.at(-1);
      await act(async () => { last.focus(); last.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })); });
      assert.ok(document.activeElement === first, 'Forward focus should reach the first drawer control; actual=' + document.activeElement?.outerHTML?.slice(0,160));
      await act(async () => first.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true })));
      assert.ok(document.activeElement === last, 'Reverse focus should reach the last drawer control');
    } finally { await view.close(); }
  });
  await test('shared fields associate labels/help/errors and statuses distinguish compliance from decisions', async () => {
    const Field = (await server.ssrLoadModule('./src/components/ui/Field.jsx')).default;
    const Badge = (await server.ssrLoadModule('./src/components/ui/StateBadge.jsx')).default;
    const Button = (await server.ssrLoadModule('./src/components/ui/Button.jsx')).default;
    const view = await mount('/results', React.createElement('div', null,
      React.createElement(Field, { label: 'Paper title', hint: 'Use the declared title', error: 'Title is required', required: true }, React.createElement('input')),
      React.createElement(Badge, { status: 'passed' }), React.createElement(Badge, { status: 'accepted' }),
      React.createElement(Button, { busy: true }, 'Saving')));
    try {
      const input = view.container.querySelector('input'); assert.equal(view.container.querySelector('label').htmlFor, input.id); assert.equal(input.getAttribute('aria-invalid'), 'true'); assert.equal(input.required, true);
      for (const id of input.getAttribute('aria-describedby').split(' ')) assert.ok(view.container.querySelector(`[id="${id}"]`));
      assert.match(view.container.textContent, /Passed/); assert.match(view.container.textContent, /Accepted/); assert.equal(view.container.querySelector('button').disabled, true);
    } finally { await view.close(); }
  });
  console.log(`${passed} shell scenarios passed`);
} finally { await server.close(); dom.window.close(); }
