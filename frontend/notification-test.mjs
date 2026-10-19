/** Isolated notification UX checks: no local backend, emails or database writes. */
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import react from '@vitejs/plugin-react';
import { JSDOM } from 'jsdom';
import { AxiosError } from 'axios';
const dom = new JSDOM('<!doctype html><body></body>', { url: 'http://localhost:5173/', pretendToBeVisual: true });
for (const key of ['window','document','navigator','HTMLElement','Element','Node','Event','CustomEvent','MouseEvent','KeyboardEvent','getComputedStyle','requestAnimationFrame','cancelAnimationFrame']) Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const React = await import('react');
const { act } = React;
const { createRoot } = await import('react-dom/client');
const { MemoryRouter, useLocation } = await import('react-router-dom');
const server = await createServer({ configFile: false, root: '.', appType: 'custom', plugins: [react()], server: { middlewareMode: true, hmr: false }, define: { 'import.meta.env.VITE_API_BASE': JSON.stringify('http://api.test/api/v1') }, ssr: { external: ['react','react-dom','react-dom/client','react-router-dom'] } });
const { api } = await server.ssrLoadModule('./src/lib/api.js');
const { AuthProvider, useAuth } = await server.ssrLoadModule('./src/context/AuthContext.jsx');
const Page = (await server.ssrLoadModule('./src/pages/Notifications.jsx')).default;
const Dropdown = (await server.ssrLoadModule('./src/components/NotificationDropdown.jsx')).default;
const timers = new Map(); let timerId = 0;
window.setInterval = (callback, delay) => { assert.equal(delay, 60_000); timers.set(++timerId, callback); return timerId; };
window.clearInterval = (id) => timers.delete(id);
let user, calls, rows, failFeed, failWrite, hold, release;
function item(id, owner = 'a', read = false) { return { notification_id: id, user_id: owner, title: `Update ${id}`, body: 'An update is available on a paper you can access', related_id: `paper-${id}`, read, type: 'submission_update', created_at: '2026-10-18T12:00:00+00:00' }; }
function reset() { user = { user_id: 'a', email: 'a@example.test' }; calls = []; rows = [item('one'), item('two')]; failFeed = failWrite = false; hold = null; release = null; }
function error(config, detail, status = 503) { throw new AxiosError(detail, 'ERR_BAD_RESPONSE', config, null, { config, status, data: { detail }, headers: {} }); }
api.defaults.adapter = async (config) => {
  calls.push(config); let data;
  if (config.url === '/auth/me') { if (!user) error(config, 'Sign in', 401); data = user; }
  else if (config.url === '/notifications/count-unread') data = { count: rows.filter((row) => row.user_id === user?.user_id && !row.read).length };
  else if (config.url === '/notifications/feed') {
    if (failFeed) error(config, 'Updates temporarily unavailable');
    const available = rows.filter((row) => row.user_id === user?.user_id && (!config.params.unread_only || !row.read));
    const offset = config.params.before ? Number(config.params.before) : 0;
    const end = offset + config.params.limit;
    data = { items: available.slice(offset, end), next_cursor: end < available.length ? String(end) : null };
    if (hold?.(config)) { hold = null; await new Promise((resolve) => { release = resolve; }); }
  } else if (config.method === 'patch') {
    if (failWrite) error(config, 'Read update failed');
    const id = config.url.split('/').at(-1);
    rows = rows.map((row) => row.user_id === user?.user_id && (id === 'read-all' || row.notification_id === id) ? { ...row, read: true } : row);
    data = id === 'read-all' ? { marked: 1 } : rows.find((row) => row.notification_id === id);
  } else throw new Error(`Unexpected request ${config.method} ${config.url}`);
  return { data: structuredClone(data), headers: {}, config, status: 200, statusText: 'OK' };
};
async function flush() { for (let i = 0; i < 5; i++) await act(async () => { await new Promise((resolve) => setTimeout(resolve, 5)); }); }
function button(container, text) { const node = [...container.querySelectorAll('button')].find((node) => node.textContent === text || node.getAttribute('aria-label') === text); assert.ok(node, `Missing button ${text}`); return node; }
async function click(container, text) { await act(async () => button(container, text).click()); await flush(); }
async function mount({ page = true, dropdown = false } = {}) {
  const container = document.createElement('div'); document.body.appendChild(container); const root = createRoot(container);
  let auth, location;
  function Probe() { auth = useAuth(); location = useLocation(); return null; }
  await act(async () => root.render(React.createElement(AuthProvider, null, React.createElement(MemoryRouter, null,
    dropdown && React.createElement(Dropdown), page && React.createElement(Page), React.createElement(Probe)))));
  await flush();
  return { container, auth: () => auth, location: () => location, close: async () => { await act(async () => root.unmount()); container.remove(); assert.equal(timers.size, 0, 'Polling must stop on unmount'); } };
}
let passed = 0;
async function test(name, run) { reset(); await run(); passed++; console.log(`OK ${name}`); }
try {
  await test('anonymous users see sign-in and never request private notifications', async () => {
    user = null; const view = await mount({ dropdown: true });
    try { assert.match(view.container.textContent, /Sign in/); assert.ok(!calls.some((call) => call.url.startsWith('/notifications'))); }
    finally { await view.close(); }
  });
  await test('history renders timestamps, links, unread count and an unread filter', async () => {
    rows[1].read = true; const view = await mount();
    try {
      assert.match(view.container.textContent, /1 unread/); assert.equal(view.container.querySelectorAll('time').length, 2);
      assert.equal(view.container.querySelector('a').getAttribute('href'), '/submissions/paper-one');
      await act(async () => view.container.querySelector('input[type="checkbox"]').click()); await flush();
      assert.match(view.container.textContent, /Update one/); assert.doesNotMatch(view.container.textContent, /Update two/);
    } finally { await view.close(); }
  });
  await test('history loads bounded pages without duplicates and refresh returns to newest', async () => {
    rows = Array.from({ length: 28 }, (_, i) => item(String(i))); const view = await mount();
    try {
      assert.equal(view.container.querySelectorAll('li').length, 25);
      await click(view.container, 'Load older notifications'); assert.equal(view.container.querySelectorAll('li').length, 28);
      assert.equal(view.container.querySelectorAll('li a').length, new Set([...view.container.querySelectorAll('li a')].map((a) => a.href)).size);
      await click(view.container, 'Refresh notifications'); assert.equal(view.container.querySelectorAll('li').length, 25);
    } finally { await view.close(); }
  });
  await test('individual and all-read changes refresh the server count and both mounted views', async () => {
    const view = await mount({ dropdown: true });
    try {
      await click(view.container, 'Mark Update one as read'); assert.equal(rows[0].read, true);
      assert.ok(view.container.querySelector('[aria-label="Notifications (1 unread)"]'));
      await click(view.container, 'Mark all as read'); assert.ok(rows.every((row) => row.read));
      assert.ok(view.container.querySelector('[aria-label="Notifications (0 unread)"]'));
    } finally { await view.close(); }
  });
  await test('read failures retain an actionable item and allow retry without false counts', async () => {
    failWrite = true; const view = await mount();
    try {
      await click(view.container, 'Mark Update one as read'); assert.match(view.container.textContent, /Read update failed/);
      assert.match(view.container.textContent, /2 unread/); assert.equal(rows[0].read, false);
      failWrite = false; await click(view.container, 'Mark Update one as read'); assert.match(view.container.textContent, /1 unread/);
    } finally { await view.close(); }
  });
  await test('load failure clears stale private results and refresh retries', async () => {
    const view = await mount();
    try {
      failFeed = true; await click(view.container, 'Refresh notifications');
      assert.match(view.container.textContent, /Updates temporarily unavailable/); assert.equal(view.container.querySelectorAll('li').length, 0);
      failFeed = false; await click(view.container, 'Refresh notifications'); assert.equal(view.container.querySelectorAll('li').length, 2);
    } finally { await view.close(); }
  });
  await test('menu toggles, closes on Escape and outside pointer, and links to complete history', async () => {
    const view = await mount({ page: false, dropdown: true });
    try {
      const trigger = button(view.container, 'Notifications (2 unread)'); assert.equal(trigger.getAttribute('aria-expanded'), 'false');
      await act(async () => trigger.click()); await flush(); assert.equal(trigger.getAttribute('aria-expanded'), 'true');
      assert.equal(view.container.querySelector('a[href="/notifications"]').textContent, 'View all notifications');
      await act(async () => document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true })));
      assert.equal(trigger.getAttribute('aria-expanded'), 'false'); assert.equal(document.activeElement, trigger);
      await act(async () => trigger.click()); await flush();
      await act(async () => document.body.dispatchEvent(new window.Event('pointerdown', { bubbles: true })));
      assert.equal(trigger.getAttribute('aria-expanded'), 'false');
    } finally { await view.close(); }
  });
  await test('zero unread keeps the notification entry available and shows an empty menu', async () => {
    rows = []; const view = await mount({ page: false, dropdown: true });
    try { await click(view.container, 'Notifications (0 unread)'); assert.match(view.container.textContent, /No unread notifications/); }
    finally { await view.close(); }
  });
  await test('background polling and returning focus refresh counts, with bounded recent items', async () => {
    const view = await mount({ page: false, dropdown: true });
    try {
      rows.push(...Array.from({ length: 10 }, (_, i) => item(`fresh-${i}`)));
      await act(async () => { for (const callback of timers.values()) callback(); }); await flush();
      assert.ok(view.container.querySelector('[aria-label="Notifications (12 unread)"]'));
      await click(view.container, 'Notifications (12 unread)'); assert.equal(view.container.querySelectorAll('li').length, 5);
      rows = []; await act(async () => window.dispatchEvent(new window.Event('focus'))); await flush();
      assert.ok(view.container.querySelector('[aria-label="Notifications (0 unread)"]'));
    } finally { await view.close(); }
  });
  await test('late responses from the previous account cannot replace the current account feed', async () => {
    hold = () => true; const view = await mount();
    try {
      assert.ok(release); user = { user_id: 'b', email: 'b@example.test' }; rows.push(item('private-b', 'b'));
      await act(async () => { await view.auth().refresh(); }); await flush();
      assert.match(view.container.textContent, /Update private-b/); assert.doesNotMatch(view.container.textContent, /Update one/);
      await act(async () => release()); await flush();
      assert.match(view.container.textContent, /Update private-b/); assert.doesNotMatch(view.container.textContent, /Update one/);
    } finally { await view.close(); }
  });
  await test('sign-out clears private UI and aborts pending notification work', async () => {
    const view = await mount({ dropdown: true });
    try {
      assert.match(view.container.textContent, /Update one/);
      await act(async () => window.dispatchEvent(new window.Event('paper:session-expired'))); await flush();
      assert.doesNotMatch(view.container.textContent, /Update one/); assert.match(view.container.textContent, /Sign in/);
      assert.equal(timers.size, 0);
    } finally { await view.close(); }
  });
  await test('conference membership notifications route to conferences and links remain keyboard accessible', async () => {
    rows = [{ ...item('member'), type: 'member_added', related_id: 'conference-c' }]; const view = await mount();
    try {
      const link = view.container.querySelector('li a'); assert.equal(link.getAttribute('href'), '/conferences');
      await act(async () => link.click()); await flush(); assert.equal(view.location().pathname, '/conferences');
      assert.equal(rows[0].read, false, 'Following a link must not silently mark it read');
    } finally { await view.close(); }
  });
  console.log(`${passed} notification UI scenarios passed`);
} finally { await server.close(); dom.window.close(); }
