/** Invitation screens with isolated API responses; never sends email or touches live data. */
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import react from '@vitejs/plugin-react';
import { JSDOM } from 'jsdom';
import { AxiosError } from 'axios';
const dom = new JSDOM('<!doctype html><body></body>', { url: 'http://localhost:5173/', pretendToBeVisual: true });
for (const key of ['window','document','navigator','HTMLElement','Element','Node','Event','MouseEvent','getComputedStyle','requestAnimationFrame','cancelAnimationFrame']) Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const React = await import('react');
const { act } = React;
const { createRoot } = await import('react-dom/client');
const { MemoryRouter, Routes, Route, useLocation } = await import('react-router-dom');
const server = await createServer({ configFile: false, root: '.', appType: 'custom', plugins: [react()], server: { middlewareMode: true, hmr: false }, define: { 'import.meta.env.VITE_API_BASE': JSON.stringify('http://api.test/api/v1') }, ssr: { external: ['react','react-dom','react-dom/client','react-router-dom'] } });
const { api } = await server.ssrLoadModule('./src/lib/api.js');
const { AuthProvider } = await server.ssrLoadModule('./src/context/AuthContext.jsx');
const TOKEN = 'a'.repeat(43);
const account = { user_id: 'recipient', full_name: 'Recipient', email: 'recipient@example.test' };
let user, calls, rows, enabled, failCreate, failInspect, failAccept, failHistory, registered;
const record = (id = 'invite-1') => ({ invitation_id: id, recipient_email: account.email, role: 'reviewer', created_at: 1900000000, expires_at: 1900600000, status: 'pending' });
function reset() { user = { ...account }; calls = []; rows = []; enabled = true; failCreate = false; failInspect = false; failAccept = false; failHistory = false; registered = false; }
function error(config, detail, status = 503) { throw new AxiosError(detail, 'ERR_BAD_RESPONSE', config, null, { config, status, data: { detail }, headers: {} }); }
api.defaults.adapter = async (config) => {
  calls.push(config);
  const url = config.url, method = config.method;
  let data;
  if (url === '/auth/me') { if (!user) error(config, 'Sign in', 401); data = user; }
  else if (url === '/auth/google/config') data = { enabled: false };
  else if (url === '/auth/register') { registered = true; data = account; }
  else if (url === '/auth/login') { user = { ...account }; data = { access_token: 'test-only-session' }; }
  else if (url === '/conferences/c/invitations' && method === 'get') {
    if (failHistory) error(config, 'Invitation history unavailable');
    data = config.params?.before ? { enabled, invitations: [record('older')], next_cursor: null } : { enabled, invitations: rows, next_cursor: rows.length ? 'older-cursor' : null };
  } else if (url === '/conferences/c/invitations' && method === 'post') {
    if (failCreate) error(config, 'Too many invitations', 429);
    rows = [record()]; data = { invitation: rows[0], token: TOKEN };
  } else if (url === '/conferences/c/invitations/invite-1' && method === 'delete') {
    rows = rows.map((row) => ({ ...row, status: 'revoked' })); data = rows[0];
  } else if (url === '/invitations/inspect') {
    if (failInspect) error(config, 'Invitation unavailable for this account', 404);
    data = { invitation_id: 'invite-1', conference_id: 'c', conference_name: 'Invited Conference', role: 'reviewer', status: 'pending', expires_at: 1900600000 };
  } else if (url === '/invitations/accept') {
    if (failAccept) error(config, 'Invitation expired or revoked', 404);
    data = { invitation_id: 'invite-1', conference_id: 'c', conference_name: 'Invited Conference', role: 'reviewer', membership_role: 'reviewer', status: 'accepted' };
  } else throw new Error(`Unexpected ${method} ${url}`);
  return { data: structuredClone(data), headers: {}, config, status: 200, statusText: 'OK' };
};
async function flush() { for (let i = 0; i < 5; i++) await act(async () => { await new Promise((resolve) => setTimeout(resolve, 5)); }); }
function button(container, label) { const result = [...container.querySelectorAll('button')].find((node) => node.textContent === label); assert.ok(result, `Missing ${label}`); return result; }
async function click(container, label) { await act(async () => button(container, label).click()); await flush(); }
async function input(element, value) {
  await act(async () => { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(element, value); element.dispatchEvent(new window.Event('input', { bubbles: true })); }); await flush();
}
async function choose(element, value) { await act(async () => { element.value = value; element.dispatchEvent(new window.Event('change', { bubbles: true })); }); await flush(); }
async function mount(path = './src/components/ConferenceInvitations.jsx', route = '/', authenticated = false) {
  const Component = (await server.ssrLoadModule(path)).default;
  const container = document.createElement('div'); document.body.appendChild(container);
  const root = createRoot(container);
  let location;
  function Probe() { location = useLocation(); return null; }
  let tree = React.createElement(MemoryRouter, { initialEntries: [route] }, React.createElement(Routes, null, React.createElement(Route, { path: '*', element: React.createElement(Component, { confId: 'c' }) })), React.createElement(Probe));
  if (authenticated) tree = React.createElement(AuthProvider, null, tree);
  await act(async () => root.render(tree)); await flush();
  return { container, location: () => location, close: async () => { await act(async () => root.unmount()); container.remove(); } };
}
let passed = 0;
async function test(name, run) { reset(); await run(); passed++; console.log(`OK ${name}`); }
const invitationRoute = `/invitations#token=${TOKEN}`;
try {
  await test('chair creates a fragment-only link with the selected role and expiry', async () => {
    const page = await mount();
    try {
      await input(page.container.querySelector('input[type="email"]'), account.email);
      await choose(page.container.querySelectorAll('select')[0], 'reviewer'); await choose(page.container.querySelectorAll('select')[1], '3');
      await click(page.container, 'Create invitation link');
      assert.deepEqual(JSON.parse(calls.find((call) => call.method === 'post').data), { email: account.email, role: 'reviewer', expires_in_days: 3 });
      const link = new URL(page.container.querySelector('input[readonly]').value);
      assert.equal(link.pathname, '/invitations'); assert.equal(link.search, ''); assert.equal(new URLSearchParams(link.hash.slice(1)).get('token'), TOKEN);
      assert.match(page.container.textContent, /No email was sent automatically/);
      assert.ok(![...page.container.querySelectorAll('option')].some((option) => option.value === 'owner'));
    } finally { await page.close(); }
  });
  await test('link copying has a manual fallback and revocation removes the displayed secret', async () => {
    let copied;
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (value) => { copied = value; } } });
    const page = await mount();
    try {
      await input(page.container.querySelector('input[type="email"]'), account.email); await click(page.container, 'Create invitation link');
      await click(page.container, 'Copy invitation link'); assert.ok(copied.endsWith(TOKEN));
      navigator.clipboard.writeText = async () => { throw new Error('Denied'); };
      await click(page.container, 'Copy invitation link'); assert.match(page.container.textContent, /copy it manually/);
      await click(page.container, `Revoke invitation for ${account.email}`); assert.equal(page.container.querySelector('input[readonly]'), null);
      assert.match(page.container.textContent, /revoked/);
    } finally { await page.close(); }
  });
  await test('schema capability fallback does not offer an unusable create form', async () => {
    enabled = false; const page = await mount();
    try { assert.match(page.container.textContent, /not enabled yet/); assert.equal(page.container.querySelector('form'), null); }
    finally { await page.close(); }
  });
  await test('creation failures preserve recipient input and do not invent a link', async () => {
    failCreate = true; const page = await mount();
    try {
      await input(page.container.querySelector('input[type="email"]'), account.email); await click(page.container, 'Create invitation link');
      assert.match(page.container.textContent, /Too many invitations/); assert.equal(page.container.querySelector('input[type="email"]').value, account.email); assert.equal(page.container.querySelector('input[readonly]'), null);
      failCreate = false; await click(page.container, 'Create invitation link'); assert.ok(page.container.querySelector('input[readonly]'));
    } finally { await page.close(); }
  });
  await test('history uses pagination and never retrieves raw links', async () => {
    rows = [record()]; const page = await mount();
    try {
      assert.equal(page.container.querySelector('input[readonly]'), null);
      await click(page.container, 'Load older invitations'); assert.ok(calls.some((call) => call.params?.before === 'older-cursor'));
      assert.equal(page.container.querySelectorAll('li').length, 2);
    } finally { await page.close(); }
  });
  await test('inspection does not accept; explicit acceptance removes the token from the URL', async () => {
    const page = await mount('./src/pages/Invitation.jsx', invitationRoute, true);
    try {
      assert.match(page.container.textContent, /Invited Conference/); assert.ok(!calls.some((call) => call.url.endsWith('/accept')));
      assert.deepEqual(JSON.parse(calls.find((call) => call.url.endsWith('/inspect')).data), { token: TOKEN });
      assert.ok(!calls.some((call) => call.url.includes(TOKEN)));
      await click(page.container, 'Accept invitation'); assert.match(page.container.textContent, /Invitation accepted/);
      assert.equal(page.location().hash, ''); assert.equal(page.container.querySelector('a').getAttribute('href'), '/conferences/c/submissions');
      assert.ok(!JSON.stringify(page.location().state).includes(TOKEN));
      assert.ok(!Object.values(window.localStorage).includes(TOKEN) && !Object.values(window.sessionStorage).includes(TOKEN));
    } finally { await page.close(); }
  });
  await test('wrong-account inspection reveals no conference details and can be checked again', async () => {
    failInspect = true; const page = await mount('./src/pages/Invitation.jsx', invitationRoute, true);
    try {
      assert.match(page.container.textContent, /Invitation unavailable for this account/); assert.doesNotMatch(page.container.textContent, /Invited Conference/);
      assert.ok(![...page.container.querySelectorAll('button')].some((node) => node.textContent === 'Accept invitation'));
      failInspect = false; await click(page.container, 'Check invitation again'); assert.match(page.container.textContent, /Invited Conference/);
    } finally { await page.close(); }
  });
  await test('revoked/expired acceptance cannot show a successful membership', async () => {
    const page = await mount('./src/pages/Invitation.jsx', invitationRoute, true);
    try { failAccept = true; await click(page.container, 'Accept invitation'); assert.match(page.container.textContent, /Invitation expired or revoked/); assert.doesNotMatch(page.container.textContent, /You have reviewer access/); assert.equal(page.location().hash, `#token=${TOKEN}`); }
    finally { await page.close(); }
  });
  await test('embedded account creation returns to the invitation without accepting it', async () => {
    user = null; const page = await mount('./src/pages/Invitation.jsx', invitationRoute, true);
    try {
      assert.match(page.container.textContent, /Join a conference/);
      await click(page.container, 'Create an account');
      const fields = page.container.querySelectorAll('form input');
      await input(fields[0], 'Recipient'); await input(fields[1], account.email); await input(fields[2], 'password123');
      await click(page.container, 'Create account');
      assert.equal(registered, true); assert.match(page.container.textContent, /Invited Conference/);
      assert.equal(page.location().hash, `#token=${TOKEN}`); assert.ok(!calls.some((call) => call.url.endsWith('/accept')));
    } finally { await page.close(); }
  });
  await test('incomplete links never trigger token inspection', async () => {
    const page = await mount('./src/pages/Invitation.jsx', '/invitations#token=bad', true);
    try { assert.match(page.container.textContent, /complete invitation link/); assert.ok(!calls.some((call) => call.url.startsWith('/invitations/'))); }
    finally { await page.close(); }
  });
  await test('invitation history searches only loaded records and clears without extra requests', async () => {
    rows = [record(), { ...record('invite-2'), recipient_email: 'other@example.test', status: 'revoked' }];
    const page = await mount();
    try {
      const reads = calls.filter((call) => call.method === 'get').length;
      await input(page.container.querySelector('input[type="search"]'), 'revoked'); assert.equal(page.container.querySelectorAll('li').length, 1);
      assert.match(page.container.querySelector('li').textContent, /other@example.test/);
      await input(page.container.querySelector('input[type="search"]'), 'missing'); assert.match(page.container.textContent, /No matching invitations/);
      await click(page.container, 'Clear invitation search'); assert.equal(page.container.querySelectorAll('li').length, 2);
      assert.equal(calls.filter((call) => call.method === 'get').length, reads);
    } finally { await page.close(); }
  });
  console.log(`${passed} invitation UI scenarios passed.`);
} finally { await server.close(); dom.window.close(); }
