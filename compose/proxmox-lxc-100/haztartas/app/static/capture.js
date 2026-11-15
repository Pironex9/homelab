// The offline capture queue. Loaded on every page: it keeps the pending
// counter current, uploads whatever is queued, and on /capture turns the form
// into a write-to-IndexedDB-first submit that never depends on the network.
//
// An item leaves the queue only on a 2xx JSON answer that echoes its
// client_uuid. A login redirect (Pangolin abroad, an expired session) or any
// other answer keeps it; the server treats a repeated client_uuid as the same
// upload, so a retry after a lost response never duplicates an entry.
(() => {
  const DB = 'haztartas';
  const STORE = 'queue';
  const CACHE = 'haztartas-v1';   // same name as in sw.js
  const RETRY_MS = 15000;
  const strings = document.getElementById('queue-strings');
  const S = strings ? JSON.parse(strings.textContent) : {};
  const $$ = (sel) => document.querySelectorAll(sel);

  // ------------------------------------------------------------ IndexedDB
  // Store `queue`, key client_uuid. A value is {client_uuid, kind, payload,
  // created_at, blob, error?, needs_rate?, status?}: `kind` and `blob` are
  // there so photo and audio join the same store later without a migration.
  function openDb() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'client_uuid' });
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function tx(mode, fn) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const t = db.transaction(STORE, mode);
      const req = fn(t.objectStore(STORE));
      t.oncomplete = () => { db.close(); resolve(req.result); };
      t.onerror = t.onabort = () => { db.close(); reject(t.error); };
    });
  }

  const byAge = (a, b) => (a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0);
  const all = async () => (await tx('readonly', (s) => s.getAll())).sort(byAge);
  const get = (key) => tx('readonly', (s) => s.get(key));
  const put = (item) => tx('readwrite', (s) => s.put(item));
  const remove = (key) => tx('readwrite', (s) => s.delete(key));

  // ------------------------------------------------------------ on screen
  let pending = 0;

  async function showCount() {
    let n = 0;
    try { n = (await all()).length; } catch (err) { return; }
    pending = n;
    $$('[data-pending]').forEach((el) => {
      el.textContent = (S.pending || '{n}').replace('{n}', n);
      el.classList.toggle('is-on', n > 0);
    });
  }

  const showLogin = (on) => $$('[data-login]').forEach((el) => { el.hidden = !on; });

  function notice(text) {
    $$('[data-notice]').forEach((el) => { el.textContent = text || ''; el.hidden = !text; });
  }

  // ------------------------------------------------------------ upload
  let editing = null;   // the client_uuid of a failed item now back in the form
  let running = null;
  let again = false;

  // One item at a time, oldest first. Resolves to {client_uuid: answer} for
  // the items the server answered.
  async function upload() {
    const answers = {};
    for (const item of await all()) {
      // Skip the one being fixed in the form, and one the form has replaced
      // since this run listed the queue.
      if (item.client_uuid === editing || !(await get(item.client_uuid))) continue;
      let res;
      try {
        res = await fetch('/capture/sync', {
          method: 'POST',
          redirect: 'manual',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ ...item.payload, client_uuid: item.client_uuid }),
        });
      } catch (err) {
        return answers;   // offline: keep everything, try again later
      }
      if (res.status === 401 || res.type === 'opaqueredirect') {
        showLogin(true);
        return answers;
      }
      let body = null;
      if ((res.headers.get('content-type') || '').includes('application/json')) {
        try { body = await res.json(); } catch (err) { body = null; }
      }
      if (!body || body.client_uuid !== item.client_uuid) {
        // Not this app answering: an auth wall's page, a proxy error page.
        if (res.ok) showLogin(true);
        return answers;
      }
      showLogin(false);
      answers[item.client_uuid] = { ...body, http: res.status };
      if (res.ok) {
        await remove(item.client_uuid);
      } else if (res.status >= 500) {
        return answers;
      } else if (await get(item.client_uuid)) {
        // Refused on its merits (bad amount, no rate, another user's item):
        // it stays queued, says why, and is retried, since a missing rate can
        // arrive later and the other user can log back in.
        await put({ ...item, error: body.error, needs_rate: !!body.needs_rate, status: res.status });
      }
      await showCount();
    }
    return answers;
  }

  // Calls during a run make it run once more, so an item queued mid-run is
  // not left waiting for the next `online` event.
  async function sync() {
    if (running) { again = true; return running; }
    const merged = {};
    running = (async () => {
      do {
        again = false;
        try { Object.assign(merged, await upload()); } catch (err) { /* no IndexedDB */ }
      } while (again);
      await showCount();
      return merged;
    })();
    try { return await running; } finally { running = null; }
  }

  // ------------------------------------------------------------ the form
  // Entry dates are calendar dates in Bratislava, whatever the phone's zone.
  const today = () => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Bratislava' }).format(new Date());

  function newUuid() {
    if (crypto.randomUUID) return crypto.randomUUID();
    // Plain-http LAN access is not a secure context; getRandomValues still works.
    const b = crypto.getRandomValues(new Uint8Array(16));
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
    return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
  }

  function showRate(form, on) {
    const box = form.querySelector('[data-rate]');
    if (!box) return;
    const input = box.querySelector('input');
    const label = box.querySelector('label');
    box.hidden = !on;
    input.disabled = !on;
    input.required = on;
    if (on && label && label.dataset.label) {
      label.textContent = label.dataset.label.replace('{currency}', form.elements.currency.value);
    }
  }

  function showError(form, text) {
    const el = form.querySelector('[data-error]');
    if (el) { el.textContent = text || ''; el.hidden = !text; }
  }

  function blank(form) {
    form.reset();
    form.elements.date.value = today();
    showRate(form, false);
    showError(form, '');
    editing = null;
  }

  function fill(form, payload) {
    for (const el of form.elements) {
      if (!el.name) continue;
      const value = payload[el.name] ?? '';
      if (el.type === 'radio' || el.type === 'checkbox') el.checked = el.value === value;
      else if (el.name in payload) el.value = value;
    }
  }

  // A refused item of this user goes back into the form to be fixed; saving
  // it queues the fixed copy under a fresh uuid and drops the refused one
  // (the server never stored it, so nothing can duplicate).
  async function restoreFailed(form) {
    let items = [];
    try { items = await all(); } catch (err) { return false; }
    // 409 is another user's item: theirs to upload, not this form's to edit.
    const item = items.find((i) => i.status && i.status !== 409
      && i.payload.user_id === form.dataset.user);
    if (!item) return false;
    blank(form);
    fill(form, item.payload);
    editing = item.client_uuid;
    showRate(form, item.needs_rate || !!item.payload.manual_rate);
    showError(form, `${S.fix || ''} ${item.error || ''}`.trim());
    return true;
  }

  function wireForm(form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = Object.fromEntries(new FormData(form));
      payload.user_id = form.dataset.user;
      const item = {
        client_uuid: newUuid(), kind: 'manual', payload,
        created_at: new Date().toISOString(), blob: null,
      };
      try {
        await put(item);   // the queue first; the network is optional
      } catch (err) {
        form.submit();     // no IndexedDB: the plain online form post
        return;
      }
      if (editing) await remove(editing);
      blank(form);
      notice(S.saved);
      await showCount();
      const answer = (await sync())[item.client_uuid];
      if (answer && answer.status === 'confirmed') {
        window.location.assign('/');
      } else if (answer && answer.status === 'draft') {
        notice(S.draft);
      } else if (answer && answer.http >= 400) {
        notice('');
        await restoreFailed(form);
      }
    });
    form.elements.currency.addEventListener('change', () => {
      const box = form.querySelector('[data-rate]');
      if (box && !box.hidden) showRate(form, true);
    });
  }

  // ------------------------------------------------------------ the rest
  // Logout clears the cached capture form (the next person on this phone gets
  // their own), never the queue: an item not yet uploaded is not lost by it.
  let leaving = false;
  let warming = Promise.resolve();
  document.addEventListener('submit', (e) => {
    const f = e.target;
    if (f.getAttribute('action') !== '/logout' || !('caches' in window)) return;
    e.preventDefault();
    // No warm-up may put the form back: none starts from here on, and one
    // already running (its fetch goes through sw.js, which caches as well)
    // finishes before the cache is emptied.
    leaving = true;
    warming
      .then(() => caches.keys())
      .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .catch(() => {})
      .finally(() => f.submit());
  }, true);

  // A logged-in page puts /capture into the cache if a logout emptied it, so
  // the form is there offline without first visiting it online.
  async function warmCache() {
    if (!('caches' in window) || window.location.pathname === '/login') return;
    if (leaving || await caches.match('/capture')) return;
    const res = await fetch('/capture', { redirect: 'manual', credentials: 'same-origin' });
    if (res.ok && res.type === 'basic' && !res.redirected && !leaving) {
      await (await caches.open(CACHE)).put('/capture', res);
    }
  }

  async function start() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
    if (navigator.storage && navigator.storage.persist) {
      navigator.storage.persisted()
        .then((yes) => yes || navigator.storage.persist())
        .catch(() => {});
    }
    const form = document.querySelector('form[data-capture]');
    if (form) {
      wireForm(form);
      if (!(await restoreFailed(form))) form.elements.date.value = today();
    }
    await showCount();
    window.addEventListener('online', sync);
    // navigator.onLine only says a network interface is up: shop wifi with no
    // uplink, or a signal that comes back, fires no `online` event at all.
    // So while something waits, try again every so often as well.
    setInterval(() => { if (pending > 0) sync(); }, RETRY_MS);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') sync();
    });
    await sync();
    warming = warmCache().catch(() => {});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
