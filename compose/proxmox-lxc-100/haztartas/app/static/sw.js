// The capture form survives a dead connection; nothing else does. Only
// /capture and /static/* are ever cached: no household data at rest beyond
// the categories and wallets the capture form lists.
//
// The cache name is also in capture.js (its warm-up fills it). Change both
// together, and bump it whenever this file changes: activate then drops the
// old cache, so a deploy cannot leave an installed phone on stale assets.
const CACHE = 'haztartas-v2';
const STATIC = ['/static/tokens.css', '/static/app.css', '/static/capture.js',
  '/static/htmx.min.js'];
// Shops have bad signal: a connection that answers nothing for this long gets
// the cached form, while the network reply still refreshes the cache.
const CAPTURE_WAIT_MS = 3000;

// A logged-out /capture is a 303 to /login. Caching that (or the login page
// it leads to) under /capture would replace the form with a login screen.
const cacheable = (res) => res && res.ok && res.type === 'basic' && !res.redirected;

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    // cache: 'reload' skips the HTTP cache, which may still hold the
    // previous deploy's files.
    await cache.addAll(STATIC.map((u) => new Request(u, { cache: 'reload' })));
    try {
      const res = await fetch('/capture', {
        redirect: 'manual', credentials: 'same-origin', cache: 'reload',
      });
      if (cacheable(res)) await cache.put('/capture', res);
    } catch (err) { /* offline or logged out: the next online visit caches it */ }
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

function networkFirst(request, key, wait) {
  const fromCache = () => caches.match(key, { ignoreSearch: true });
  // no-cache: revalidate with the server rather than take the HTTP cache's
  // copy, or "network first" could still be last deploy's file.
  const network = fetch(request, { cache: 'no-cache' }).then(async (res) => {
    if (cacheable(res)) {
      try {
        await (await caches.open(CACHE)).put(key, res.clone());
      } catch (err) { /* storage full: the good network answer still stands */ }
    }
    return res;
  });
  return new Promise((resolve) => {
    let done = false;
    const finish = (res) => { if (!done && res) { done = true; resolve(res); } };
    const timer = wait ? setTimeout(async () => finish(await fromCache()), wait) : null;
    network
      .then((res) => { clearTimeout(timer); finish(res); })
      .catch(async () => { clearTimeout(timer); finish((await fromCache()) || Response.error()); });
  });
}

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname === '/capture') {
    e.respondWith(networkFirst(e.request, '/capture', CAPTURE_WAIT_MS));
  } else if (url.pathname.startsWith('/static/')) {
    e.respondWith(networkFirst(e.request, url.pathname, 0));
  }
});
