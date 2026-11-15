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
  const CACHE = 'haztartas-v2';   // same name as in sw.js
  const RETRY_MS = 15000;
  const FETCH_TIMEOUT_MS = 20000;
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

  // One transaction: everything fn asks for happens, or none of it does.
  async function tx(mode, fn) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const t = db.transaction(STORE, mode);
      let req;
      try {
        req = fn(t.objectStore(STORE));
      } catch (err) {
        try { t.abort(); } catch (e) { /* already finished */ }
        db.close();
        reject(err);
        return;
      }
      t.oncomplete = () => { db.close(); resolve(req.result); };
      t.onerror = t.onabort = () => { db.close(); reject(t.error); };
    });
  }

  const byAge = (a, b) => (a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0);
  const all = async () => (await tx('readonly', (s) => s.getAll())).sort(byAge);
  const get = (key) => tx('readonly', (s) => s.get(key));
  const put = (item) => tx('readwrite', (s) => s.put(item));
  const remove = (key) => tx('readwrite', (s) => s.delete(key));
  // The fixed copy in and the refused one out together, so a failure can
  // never leave both queued (two entries) or neither (a lost one).
  const putReplacing = (item, old) => tx('readwrite', (s) => {
    if (old) s.delete(old);
    return s.put(item);
  });
  // A stored refusal (403, 409, 422) means the server said no to this item
  // as it is; everything else is simply waiting for a connection or a login.
  const refused = (item) => !!item.status;

  // ------------------------------------------------------------ on screen
  let waiting = 0;

  async function showCount() {
    let items;
    try { items = await all(); } catch (err) { return; }
    const no = items.filter(refused);
    waiting = items.length - no.length;
    const parts = [];
    if (waiting) parts.push((S.pending || '{n}').replace('{n}', waiting));
    if (no.length) parts.push((S.refused || '{n}').replace('{n}', no.length));
    $$('[data-pending]').forEach((el) => {
      el.textContent = parts.join(' · ');
      el.classList.toggle('is-on', items.length > 0);
    });
    showRefused(no);
  }

  // On /capture: every refused item with its reason and a way off the phone.
  // Built here rather than in the template: the cached page cannot know.
  function showRefused(items) {
    const form = document.querySelector('form[data-capture]');
    if (!form) return;
    let box = document.querySelector('[data-refused]');
    if (!box) {
      box = document.createElement('section');
      box.className = 'refused';
      box.dataset.refused = '';
      const title = document.createElement('p');
      title.className = 'hint';
      title.textContent = S.refused_title || '';
      box.append(title, document.createElement('ul'));
      form.before(box);
    }
    const list = box.querySelector('ul');
    list.replaceChildren(...items.map((item) => {
      const p = item.payload || {};
      const li = document.createElement('li');
      const what = document.createElement('span');
      const reason = item.status === 409 ? S.other_user : item.error;
      what.textContent = [`${p.amount || ''} ${p.currency || ''}`.trim(), p.merchant, p.date]
        .filter(Boolean).join(' · ') + (reason ? ` - ${reason}` : '');
      const drop = document.createElement('button');
      drop.type = 'button';
      drop.className = 'btn btn--quiet';
      drop.textContent = S.discard || '';
      drop.addEventListener('click', async () => {
        if (!window.confirm(S.discard_confirm || '')) return;
        await remove(item.client_uuid);
        if (item.client_uuid === editing) blank(form);
        await showCount();
      });
      li.append(what, drop);
      return li;
    }));
    box.hidden = items.length === 0;
  }

  const showLogin = (on) => $$('[data-login]').forEach((el) => { el.hidden = !on; });

  function notice(text) {
    $$('[data-notice]').forEach((el) => { el.textContent = text || ''; el.hidden = !text; });
  }

  // ------------------------------------------------------------ upload
  let editing = null;   // the client_uuid of a failed item now back in the form
  let running = null;
  let again = null;   // null, 'waiting' or 'all': what to run once more

  // One item at a time, oldest first. Resolves to {client_uuid: answer} for
  // the items the server answered.
  async function upload(waitingOnly) {
    const answers = {};
    for (const item of await all()) {
      if (waitingOnly && refused(item)) continue;
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
          // A hung connection would otherwise hold the whole queue.
          signal: AbortSignal.timeout ? AbortSignal.timeout(FETCH_TIMEOUT_MS) : undefined,
        });
      } catch (err) {
        return answers;   // offline or timed out: keep everything, try again later
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
  // not left waiting for the next `online` event. waitingOnly skips items the
  // server refused: the timer retries those for nothing every 15 s otherwise;
  // a page load and the `online` event still retry them (a missing rate can
  // arrive, the other user can log back in).
  async function sync(waitingOnly = false) {
    const want = waitingOnly ? 'waiting' : 'all';
    if (running) {
      if (again !== 'all') again = want;
      return running;
    }
    const merged = {};
    running = (async () => {
      let mode = want;
      do {
        again = null;
        try { Object.assign(merged, await upload(mode === 'waiting')); } catch (err) { /* no IndexedDB */ }
        mode = again;
      } while (mode);
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
    const item = items.find((i) => refused(i) && i.status !== 409
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
        await putReplacing(item, editing);   // the queue first; the network is optional
      } catch (err) {
        // No IndexedDB, or the phone is full. Online, the plain form post
        // still saves it; offline that would only reach an error page and
        // lose what was typed, so say so and keep the form as it is.
        if (navigator.onLine === false) showError(form, S.no_storage);
        else form.submit();
        return;
      }
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
  // Whoever reaches /login is logged out (a logout, an expired session): the
  // cached capture form was the previous user's, so it goes. The queue stays.
  // Done on arrival rather than on the logout click, so a logout that never
  // reached the server keeps the form, and an expiry clears it too.
  async function clearCache() {
    if (!('caches' in window)) return;
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
  }

  // A logged-in page puts /capture into the cache if it is not there (after
  // a login), so the form is there offline without first visiting it online.
  async function warmCache() {
    if (!('caches' in window) || await caches.match('/capture')) return;
    const res = await fetch('/capture', { redirect: 'manual', credentials: 'same-origin' });
    if (res.ok && res.type === 'basic' && !res.redirected) {
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
    const onLogin = window.location.pathname === '/login';
    if (onLogin) clearCache().catch(() => {});
    const form = document.querySelector('form[data-capture]');
    if (form) {
      wireForm(form);
      if (!(await restoreFailed(form))) form.elements.date.value = today();
    }
    await showCount();
    window.addEventListener('online', () => sync());
    // navigator.onLine only says a network interface is up: shop wifi with no
    // uplink, or a signal that comes back, fires no `online` event at all.
    // So while something waits, try again every so often as well.
    setInterval(() => { if (waiting > 0) sync(true); }, RETRY_MS);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') sync();
    });
    await sync();
    if (!onLogin) warmCache().catch(() => {});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
