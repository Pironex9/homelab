// usage: node scripts/offline_check.mjs http://127.0.0.1:PORT username password
//
// Proves the offline capture queue in a real Chrome, against a running app
// with an empty month: the service worker serves /capture from cache with
// the network off, IndexedDB holds what was recorded, and nothing leaves the
// queue without the server's JSON answer. context.setOffline cuts the page
// and the service worker alike, but a page loaded while "offline" still
// reports navigator.onLine true and gets no `online` event when the network
// returns: the same as shop wifi without an uplink. Recovery there comes from
// capture.js's timed retry, so the waits below allow for it (15 s).
// Same load-bearing settings as shot.mjs.
//
//   1. offline: two entries queue, the counter shows 2; online: both upload,
//      each listed exactly once.
//   1b. the same amount again offline: after upload it waits under /drafts.
//   1c. a bad amount online: queued, back in the form, fixed, uploaded once.
//   2. session gone (cookie cleared, as when it expires): the cached form
//      still opens offline and queues; back online the login prompt shows and
//      the counter stays 1; after logging in it uploads.
//   3. logout: the Cache Storage is emptied when /login loads, the queue is
//      not, and /login shows the counter; an item that could not upload
//      before the logout uploads after the next login.
//   4. Pangolin in front, abroad: a 302 to an external login and a 200 HTML
//      login page both keep the item queued and show the login prompt.
//   4b. abroad on a live connection, Pangolin answers /capture itself with a
//      302 to its SSO login: the cached form opens anyway, a capture queues,
//      and it uploads once the wall is gone.
//   5. the phone's storage is full while offline: the form says so and keeps
//      what was typed instead of navigating to an error page.
//   6. a refused item of another user (409) is only counted: no amount,
//      merchant or date on screen, no discard button; it uploads once its
//      author's session is back.
const PW = process.env.PLAYWRIGHT_CORE
  || '/usr/lib/node_modules/@playwright/cli/node_modules/playwright-core/index.mjs';
const { chromium } = await import(PW);

const [, , base, username, password] = process.argv;
if (!base || !username || !password) {
  console.error('usage: node scripts/offline_check.mjs URL USERNAME PASSWORD');
  process.exit(2);
}

const browser = await chromium.launch({
  executablePath: '/usr/bin/google-chrome',
  args: ['--no-sandbox'],
});
const context = await browser.newContext({ viewport: { width: 390, height: 900 } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
if (process.env.DEBUG) {   // DEBUG=1: every request, the service worker's included
  context.on('request', (r) => r.serviceWorker() && console.log('sw: ', r.method(), r.url()));
  page.on('console', (m) => console.log('console:', m.text()));
  page.on('requestfinished', async (r) => console.log('req:', r.method(), r.url(), (await r.response())?.status()));
  page.on('requestfailed', (r) => console.log('fail:', r.method(), r.url(), r.failure()?.errorText));
}
const tag = Date.now().toString(36);
let failed = false;

function ok(cond, what) {
  console.log(`${cond ? 'ok  ' : 'FAIL'} ${what}`);
  if (!cond) failed = true;
}

const counter = () => page.locator('[data-pending]');
const counterText = () => counter().textContent();
const queueSize = () => page.evaluate(() => new Promise((resolve, reject) => {
  const req = indexedDB.open('haztartas', 1);
  req.onupgradeneeded = () => req.result.createObjectStore('queue', { keyPath: 'client_uuid' });
  req.onsuccess = () => {
    const r = req.result.transaction('queue').objectStore('queue').count();
    r.onsuccess = () => { req.result.close(); resolve(r.result); };
  };
  req.onerror = () => reject(req.error);
}));
const cachedCapture = () => page.evaluate(async () => !!(await caches.match('/capture')));
// page.waitForFunction treats a returned Promise as truthy and never awaits
// it, so an async condition (Cache Storage, IndexedDB) is polled from here.
async function until(cond, what, ms = 10000) {
  const end = Date.now() + ms;
  while (!(await cond())) {
    if (Date.now() > end) throw new Error(`timed out: ${what}`);
    await page.waitForTimeout(250);
  }
}
const waitNotCached = () => until(async () => !(await cachedCapture()), '/capture leaves the cache');
const syncRoute = '**/capture/sync';

async function login() {
  await page.goto(`${base}/login`);
  await page.fill('#username', username);
  await page.fill('#password', password);
  await Promise.all([page.waitForURL(`${base}/`), page.click('button[type=submit]')]);
}

async function record(merchant, amount) {
  await page.fill('#f-amount', amount);
  const cat = await page.$eval('#f-category optgroup option', (o) => o.value);
  await page.selectOption('#f-category', cat);
  await page.fill('#f-merchant', merchant);
  await page.click('form[data-capture] button[type=submit]');
}

async function waitCount(n) {
  await page.waitForFunction((want) => {
    const el = document.querySelector('[data-pending]');
    return el && el.classList.contains('is-on') && el.textContent.startsWith(`${want} `);
  }, n, { timeout: 10000 });
}

// A freshly loaded page renders the counter hidden before capture.js has
// counted, so "counter hidden" alone proves nothing right after a navigation:
// wait for the queue itself to empty, then for the counter.
async function waitUploaded() {
  await until(async () => await queueSize() === 0, 'queue empties', 45000);
  await counter().waitFor({ state: 'hidden', timeout: 5000 });
}

async function listedTimes(merchant) {
  const html = await page.evaluate(() => fetch('/entries').then((r) => r.text()));
  return html.split(merchant).length - 1;
}

try {
  // ---- 1. offline, two entries, back online
  await login();
  await page.goto(`${base}/capture`);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await until(async () => await page.evaluate(() => !!navigator.serviceWorker.controller)
    && cachedCapture(), 'service worker in control, /capture cached');
  ok(true, 'service worker controls /capture and has it cached');

  await context.setOffline(true);
  await page.reload();
  ok(await page.locator('form[data-capture]').isVisible(), 'offline: /capture opens from cache');
  await record(`Offline-A-${tag}`, '7,30');
  await waitCount(1);
  await record(`Offline-B-${tag}`, '8,40');
  await waitCount(2);
  ok((await counterText()).trim() === '2 tétel vár feltöltésre', `offline: counter shows "${(await counterText()).trim()}"`);
  ok(await queueSize() === 2, 'offline: IndexedDB queue holds 2');

  await context.setOffline(false);
  await counter().waitFor({ state: 'hidden', timeout: 45000 });
  ok(true, 'online: counter hidden');
  ok(await queueSize() === 0, 'online: queue empty');
  const a = await listedTimes(`Offline-A-${tag}`);
  const b = await listedTimes(`Offline-B-${tag}`);
  ok(a === 1 && b === 1, `online: /entries lists each once (A=${a}, B=${b})`);

  // ---- 1b. the same amount again, offline: it could not ask, so it waits as a draft
  await context.setOffline(true);
  await page.goto(`${base}/capture`);
  await record(`Again-${tag}`, '7,30');
  await waitCount(1);
  await context.setOffline(false);
  await counter().waitFor({ state: 'hidden', timeout: 45000 });
  const drafts = await page.evaluate(() => fetch('/drafts').then((r) => r.text()));
  ok(drafts.split(`Again-${tag}`).length - 1 === 1 && await listedTimes(`Again-${tag}`) === 0,
    'duplicate amount: listed under /drafts, not under /entries');

  // ---- 1c. refused on its merits: it stays queued and comes back into the form
  await page.goto(`${base}/capture`);
  await record(`Fixme-${tag}`, 'abc');
  await page.locator('[data-error]').waitFor({ state: 'visible', timeout: 15000 });
  ok(await page.inputValue('#f-amount') === 'abc'
    && await page.inputValue('#f-merchant') === `Fixme-${tag}`, 'bad amount: back in the form with its error');
  ok(await queueSize() === 1 && (await counterText()).trim().startsWith('1 '), 'bad amount: still queued, counted');
  await page.reload();
  ok(await page.inputValue('#f-amount') === 'abc', 'bad amount: back in the form after reopening too');
  await page.fill('#f-amount', '11,20');
  await page.click('form[data-capture] button[type=submit]');
  await page.waitForURL(`${base}/`, { timeout: 15000 });
  ok(await queueSize() === 0 && await listedTimes(`Fixme-${tag}`) === 1, 'fixed: uploaded once, refused copy gone');

  // ---- 2. session gone while offline
  await context.clearCookies();
  await context.setOffline(true);
  await page.goto(`${base}/capture`);
  ok(await page.locator('form[data-capture]').isVisible(), 'no session, offline: cached /capture opens');
  await record(`Expired-${tag}`, '9,50');
  await waitCount(1);
  await context.setOffline(false);
  await page.locator('[data-login]').waitFor({ state: 'visible', timeout: 45000 });
  ok(true, 'no session, online: login prompt shows');
  ok((await counterText()).trim().startsWith('1 '), 'no session, online: counter stays 1');
  ok(await queueSize() === 1, 'no session, online: queue still holds 1');
  ok(await page.getAttribute('[data-login] a', 'href') === '/login', 'login prompt links to /login');

  // a session expiry ends at /login: the cached form of whoever was logged
  // in goes, the queue stays and is counted there
  await page.goto(`${base}/login`);
  await waitNotCached();
  ok(true, '/login: Cache Storage emptied on load');
  await waitCount(1);
  ok(await queueSize() === 1, '/login: counter shows the 1 queued item, queue kept');

  await login();
  await page.goto(`${base}/capture`);
  await waitUploaded();
  ok(true, 'after login: uploaded, queue empty, counter hidden');
  const c = await listedTimes(`Expired-${tag}`);
  ok(c === 1, `after login: /entries lists it once (${c})`);

  // ---- 3. logout clears the cache, keeps the queue
  await page.route('**/capture/sync', (r) => r.fulfill({ status: 503, body: 'down' }));
  await record(`Logout-${tag}`, '10,60');
  await waitCount(1);
  await page.goto(`${base}/`);   // the logout form lives in the home menu
  await Promise.all([
    page.waitForURL(`${base}/login`),
    page.evaluate(() => document.querySelector('form[action="/logout"]').requestSubmit()),
  ]);
  await waitNotCached();
  ok(true, 'logout: /capture is gone from Cache Storage');
  ok(await queueSize() === 1, 'logout: the queue still holds 1');
  await waitCount(1);
  ok(true, 'logout: /login shows the counter');
  await page.unroute('**/capture/sync');
  await login();
  await waitUploaded();
  ok(true, 'next login: the item from before the logout uploaded');
  ok(await listedTimes(`Logout-${tag}`) === 1, 'next login: listed once');
  await until(cachedCapture, '/capture cached again');
  ok(true, 'next login: /capture is cached again without visiting it');

  // ---- 4. Pangolin's two shapes
  for (const [shape, answer, amount] of [
    ['302 to an external login', { status: 302, headers: { location: 'https://auth.example.invalid/login' } }, '12,70'],
    ['200 HTML login page', { status: 200, contentType: 'text/html', body: '<!doctype html><title>Login</title><form></form>' }, '15,10'],
  ]) {
    const name = `Pangolin-${amount}-${tag}`;
    await page.goto(`${base}/capture`);
    await page.route(syncRoute, (r) => r.fulfill(answer));
    await record(name, amount);
    await page.locator('[data-login]').waitFor({ state: 'visible', timeout: 15000 });
    ok(await queueSize() === 1, `Pangolin ${shape}: login prompt shows, item kept`);
    await page.unroute(syncRoute);
    await page.reload();
    await waitUploaded();
    ok(await listedTimes(name) === 1,
      `Pangolin ${shape}: uploads once the wall is gone`);
  }

  // ---- 4b. the login wall in front of /capture itself, online.
  // context.route, not page.route: the service worker's own fetch of
  // /capture is what meets the wall, and page.route cannot see it.
  const wall = { status: 302, headers: { location: 'https://auth.example.invalid/login' } };
  await until(cachedCapture, '/capture cached before the wall');
  await context.route(`${base}/capture`, (r) => r.fulfill(wall));
  await page.route(syncRoute, (r) => r.fulfill(wall));
  await page.goto(`${base}/capture`);
  ok(page.url() === `${base}/capture` && await page.locator('form[data-capture]').isVisible(),
    'login wall on /capture, online: the cached form opens');
  await record(`Abroad-${tag}`, '16,30');
  await page.locator('[data-login]').waitFor({ state: 'visible', timeout: 15000 });
  ok(await queueSize() === 1, 'login wall on /capture: the capture queues');
  await context.unroute(`${base}/capture`);
  await page.unroute(syncRoute);
  await page.reload();
  await waitUploaded();
  ok(await listedTimes(`Abroad-${tag}`) === 1, 'login wall gone: uploads once');

  // ---- 5. storage full while offline
  await page.goto(`${base}/capture`);
  await context.setOffline(true);
  await page.evaluate(() => {
    IDBObjectStore.prototype.put = () => { throw new DOMException('full', 'QuotaExceededError'); };
  });
  await record(`Quota-${tag}`, '13,80');
  await page.locator('[data-error]').waitFor({ state: 'visible', timeout: 5000 });
  ok((await page.textContent('[data-error]')).includes('kevés a tárhely')
    && await page.inputValue('#f-amount') === '13,80'
    && await page.inputValue('#f-merchant') === `Quota-${tag}`
    && page.url() === `${base}/capture`, 'storage full offline: says so, keeps the typed entry');
  await context.setOffline(false);
  await page.reload();   // the real put again
  ok(await queueSize() === 0, 'storage full offline: nothing half-queued');

  // ---- 6. another user's item: a count line, nothing of its content
  await page.route(syncRoute, (r) => r.fulfill({
    status: 409, contentType: 'application/json',
    body: JSON.stringify({ client_uuid: JSON.parse(r.request().postData()).client_uuid, error: 'x' }),
  }));
  await record(`Refused-${tag}`, '19,90');
  const others = page.locator('[data-refused] [data-others]');
  await others.waitFor({ state: 'visible', timeout: 15000 });
  ok((await others.textContent()).trim() === '1 tétel egy másik felhasználótól: csak ő töltheti fel',
    `refused 409: count line shows "${(await others.textContent()).trim()}"`);
  const box = (await page.textContent('[data-refused]')) || '';
  ok(!box.includes(`Refused-${tag}`) && !box.includes('19,90')
    && await page.locator('[data-refused] li').count() === 0
    && await page.locator('[data-refused] button').count() === 0,
  'refused 409: no amount, merchant or discard button on screen');
  await waitCount(1);
  ok((await counterText()).includes('nem tölthető fel'), `refused 409: counter says so ("${(await counterText()).trim()}")`);
  await page.unroute(syncRoute);
  await page.reload();   // its author is logged in after all: a page load retries it
  await waitUploaded();
  ok(await listedTimes(`Refused-${tag}`) === 1 && !(await others.isVisible()),
    'refused 409: uploads once its author is back, count line gone');
} catch (err) {
  ok(false, `aborted: ${err.message.split('\n')[0]}`);
}
ok(errors.length === 0, `no page errors${errors.length ? `: ${errors.join(' | ')}` : ''}`);
await browser.close();
process.exit(failed ? 1 : 0);
