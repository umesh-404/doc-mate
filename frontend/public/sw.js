/*
 * Doc-mate service worker — hand written, zero dependencies.
 *
 * Doc-mate runs in government hospitals and rural clinics where the link drops
 * without warning (PROJECT.md §1, §12.8). The rules below follow from that:
 *
 *   navigation   → network-first, then the cached copy of that exact route,
 *                  then a friendly static offline page.
 *   static asset → cache-first (immutable build output never changes in place).
 *   API GET      → stale-while-revalidate, stamped with the time it was
 *                  fetched so the UI can say how stale it is (§4 rule 5).
 *   API write    → never fails offline; falls through to the outbox.
 *   /auth/*      → NEVER cached. Tokens and identity stay out of Cache Storage.
 *
 * The app-side outbox (lib/offline/outbox.ts) owns replay. This worker only
 * enqueues writes that were made outside the app's own API client, which it
 * recognises by the absence of the X-Docmate-Outbox header. That keeps exactly
 * one component responsible for any given write and rules out double-submits.
 */

const VERSION = "v1";
const SHELL_CACHE = `docmate-shell-${VERSION}`;
const STATIC_CACHE = `docmate-static-${VERSION}`;
const API_CACHE = `docmate-api-${VERSION}`;
const CURRENT_CACHES = [SHELL_CACHE, STATIC_CACHE, API_CACHE];

/** Wall-clock stamp added to cached API responses so the UI can age them. */
const FETCHED_AT_HEADER = "x-docmate-fetched-at";

/** Cached clinical data older than this is dropped. Keep in sync with lib/offline/db.ts. */
const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000;

const OFFLINE_URL = "/offline.html";

/** App shell resources worth having before the first outage. */
const PRECACHE_URLS = [
  OFFLINE_URL,
  "/manifest.webmanifest",
  "/icons/icon.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

/* ------------------------------------------------------------------ */
/* IndexedDB — shared schema with lib/offline/db.ts                    */
/* ------------------------------------------------------------------ */

const DB_NAME = "docmate-offline";
const DB_VERSION = 1;

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("cache")) {
        db.createObjectStore("cache", { keyPath: "key" });
      }
      if (!db.objectStoreNames.contains("outbox")) {
        const s = db.createObjectStore("outbox", { keyPath: "id" });
        s.createIndex("state", "state");
      }
      if (!db.objectStoreNames.contains("meta")) {
        db.createObjectStore("meta", { keyPath: "k" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function idbPut(store, value) {
  return openDB().then(
    (db) =>
      new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readwrite");
        tx.objectStore(store).put(value);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      }),
  );
}

function idbGet(store, key) {
  return openDB().then(
    (db) =>
      new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readonly");
        const req = tx.objectStore(store).get(key);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      }),
  );
}

/* ------------------------------------------------------------------ */
/* Config: which origin is the API?                                    */
/* ------------------------------------------------------------------ */

/*
 * The API base URL is a build-time env var in the app, but this file is static.
 * The client posts it on registration; it is persisted so the value survives a
 * worker restart, and re-requested from a controlled client if it is missing.
 */
let apiOriginPromise = null;

function getApiOrigin() {
  if (!apiOriginPromise) {
    apiOriginPromise = idbGet("meta", "apiOrigin")
      .then((row) => (row && typeof row.v === "string" ? row.v : null))
      .catch(() => null);
  }
  return apiOriginPromise;
}

function setApiOrigin(origin) {
  apiOriginPromise = Promise.resolve(origin);
  return idbPut("meta", { k: "apiOrigin", v: origin }).catch(() => {});
}

/* ------------------------------------------------------------------ */
/* Install / activate                                                  */
/* ------------------------------------------------------------------ */

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      // Individually, so one 404 in the list cannot fail the whole install.
      .then((cache) =>
        Promise.all(
          PRECACHE_URLS.map((url) =>
            cache.add(new Request(url, { cache: "reload" })).catch(() => {}),
          ),
        ),
      )
      // A half-updated shell is worse than a brief reload, so the new worker
      // takes over immediately rather than waiting for every tab to close.
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith("docmate-") && !CURRENT_CACHES.includes(k))
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => purgeExpiredApiCache())
      .then(() => self.clients.claim()),
  );
});

/** Drop cached clinical responses past their TTL — PHI does not linger. */
async function purgeExpiredApiCache() {
  try {
    const cache = await caches.open(API_CACHE);
    const requests = await cache.keys();
    const cutoff = Date.now() - CACHE_TTL_MS;
    await Promise.all(
      requests.map(async (req) => {
        const res = await cache.match(req);
        const at = Number(res && res.headers.get(FETCHED_AT_HEADER));
        if (!at || at < cutoff) await cache.delete(req);
      }),
    );
  } catch {
    /* cache purge is best-effort; never block activation */
  }
}

/* ------------------------------------------------------------------ */
/* Messages from the app                                               */
/* ------------------------------------------------------------------ */

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "SET_API_ORIGIN" && typeof data.origin === "string") {
    event.waitUntil(setApiOrigin(data.origin));
  } else if (data.type === "SKIP_WAITING") {
    self.skipWaiting();
  } else if (data.type === "WIPE_CACHES") {
    // Sign-out: every byte of cached PHI goes, including the shell.
    event.waitUntil(
      caches
        .keys()
        .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
        .then(() => {
          if (event.ports && event.ports[0]) event.ports[0].postMessage({ ok: true });
        }),
    );
  }
});

/* ------------------------------------------------------------------ */
/* Background Sync — wake the app so it can replay the outbox          */
/* ------------------------------------------------------------------ */

self.addEventListener("sync", (event) => {
  if (event.tag !== "docmate-outbox") return;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      // Replay needs the user's bearer token, which lives in the page. If no
      // page is open the queue simply waits for the next launch — it is never
      // dropped. This is stated in the UI rather than papered over.
      for (const client of clients) client.postMessage({ type: "REPLAY_OUTBOX" });
    }),
  );
});

/* ------------------------------------------------------------------ */
/* Fetch routing                                                       */
/* ------------------------------------------------------------------ */

function isStaticAsset(url) {
  return (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname === "/manifest.webmanifest" ||
    /\.(?:css|js|woff2?|ttf|otf|png|jpg|jpeg|gif|svg|webp|ico)$/.test(url.pathname)
  );
}

/** Auth traffic is never cached — no tokens, no identity, in Cache Storage. */
function isAuthPath(url) {
  return url.pathname === "/auth" || url.pathname.startsWith("/auth/");
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.mode === "navigate") {
    event.respondWith(handleNavigate(req));
    return;
  }
  // Chrome extension / blob / data schemes are not ours to touch.
  if (!req.url.startsWith("http")) return;

  const url = new URL(req.url);

  if (url.origin === self.location.origin) {
    if (isStaticAsset(url)) {
      event.respondWith(cacheFirst(req, STATIC_CACHE));
    }
    // Everything else same-origin (RSC payloads, Next.js data) goes to the
    // network untouched — stale RSC is worse than a clean client-side failure.
    return;
  }

  event.respondWith(handleCrossOrigin(event, req, url));
});

async function handleCrossOrigin(event, req, url) {
  const apiOrigin = await getApiOrigin();
  if (!apiOrigin || url.origin !== apiOrigin) return fetch(req);
  if (isAuthPath(url)) return fetch(req);

  if (req.method === "GET") return staleWhileRevalidate(event, req);
  return passThroughOrQueue(req);
}

/* ---- navigation: network-first → cached route → offline page ---- */

async function handleNavigate(req) {
  try {
    const res = await fetch(req);
    if (res && res.ok) {
      const cache = await caches.open(SHELL_CACHE);
      // Awaited: the worker can be terminated the moment respondWith settles,
      // and a dropped write here is a route that will not open offline.
      await cache.put(req, res.clone());
    }
    return res;
  } catch {
    const cached = await caches.match(req, { ignoreSearch: true });
    if (cached) return cached;
    const offline = await caches.match(OFFLINE_URL);
    if (offline) return offline;
    return new Response("Offline", {
      status: 503,
      headers: { "Content-Type": "text/plain" },
    });
  }
}

/* ---- static: cache-first ---- */

async function cacheFirst(req, cacheName) {
  const cached = await caches.match(req);
  if (cached) return cached;
  const res = await fetch(req);
  if (res && res.ok) {
    const cache = await caches.open(cacheName);
    await cache.put(req, res.clone());
  }
  return res;
}

/* ---- API GET: stale-while-revalidate with a fetched-at stamp ---- */

/** Re-wrap a response so the cached copy carries the time it was fetched. */
async function stampResponse(res) {
  const body = await res.clone().arrayBuffer();
  const headers = new Headers(res.headers);
  headers.set(FETCHED_AT_HEADER, String(Date.now()));
  return new Response(body, {
    status: res.status,
    statusText: res.statusText,
    headers,
  });
}

async function staleWhileRevalidate(event, req) {
  const cache = await caches.open(API_CACHE);
  const cached = await cache.match(req);

  const network = fetch(req)
    .then(async (res) => {
      if (res && res.ok) {
        const stamped = await stampResponse(res);
        await cache.put(req, stamped.clone());
        return stamped;
      }
      return res;
    })
    .catch(() => null);

  if (cached) {
    // Serve the cached copy now; the refresh finishes in the background.
    event.waitUntil(network);
    return cached;
  }

  const fresh = await network;
  if (fresh) return fresh;
  return new Response(
    JSON.stringify({ detail: "Offline and no cached copy of this record." }),
    { status: 503, headers: { "Content-Type": "application/json" } },
  );
}

/* ---- API writes: pass through, or queue if the app did not ---- */

async function passThroughOrQueue(req) {
  // The app's own API client stamps its writes. Those are already the outbox's
  // responsibility, so letting the error surface is correct — the app enqueues
  // it with the client id its optimistic UI is keyed on.
  const ownedByApp = req.headers.get("x-docmate-outbox") === "app";
  try {
    return await fetch(req);
  } catch (err) {
    if (ownedByApp) throw err;
    try {
      await queueRawRequest(req);
    } catch {
      throw err;
    }
    return new Response(JSON.stringify({ queued: true }), {
      status: 202,
      headers: { "Content-Type": "application/json" },
    });
  }
}

/**
 * Store an unrecognised offline write verbatim so nothing is lost. The body is
 * kept as a Blob and the Content-Type preserved, which keeps a multipart
 * boundary intact. Authorization is deliberately NOT stored — replay attaches a
 * fresh token, so no credential is written to disk.
 */
async function queueRawRequest(req) {
  const clone = req.clone();
  const body = await clone.blob();
  const headers = {};
  for (const [k, v] of clone.headers.entries()) {
    if (k.toLowerCase() === "authorization") continue;
    headers[k] = v;
  }
  const now = Date.now();
  await idbPut("outbox", {
    id: (self.crypto && self.crypto.randomUUID && self.crypto.randomUUID()) ||
      `raw-${now}-${Math.random().toString(36).slice(2)}`,
    kind: "raw",
    state: "pending",
    attempts: 0,
    createdAt: now,
    nextAttemptAt: now,
    lastError: null,
    payload: { url: req.url, method: req.method, headers, body },
  });
}
