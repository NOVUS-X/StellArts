/**
 * StellArts Service Worker
 * - Cache-first for the Next.js app shell + static CSS/JS (_next/static, fonts).
 * - Network-first with offline fallback for page navigations.
 * - Network-first + cache fallback for the active-jobs API call, so artisans
 *   can view their last-known active jobs with no connectivity.
 */

const CACHE_VERSION = "v1";
const SHELL_CACHE = `stellarts-shell-${CACHE_VERSION}`;
const STATIC_CACHE = `stellarts-static-${CACHE_VERSION}`;
const API_CACHE = `stellarts-api-${CACHE_VERSION}`;

const OFFLINE_URL = "/offline.html";

// Endpoints we're willing to serve stale-from-cache when offline.
// Matched against pathname suffix so this works regardless of API origin.
const OFFLINE_READABLE_API_PATHS = ["/bookings/my-bookings"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      // Pre-cache the shell entry point + offline fallback so both are
      // available on first load, before any static asset requests happen.
      await cache.addAll(["/", OFFLINE_URL]);
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter(
            (key) => ![SHELL_CACHE, STATIC_CACHE, API_CACHE].includes(key),
          )
          .map((key) => caches.delete(key)),
      );
      await self.clients.claim();
    })(),
  );
});

function isStaticAsset(request) {
  const dest = request.destination;
  return (
    dest === "style" ||
    dest === "script" ||
    dest === "font" ||
    request.url.includes("/_next/static/")
  );
}

function isOfflineReadableApi(url) {
  return OFFLINE_READABLE_API_PATHS.some((path) => url.pathname.endsWith(path));
}

// Cache-first: fast repeat loads, static assets are content-hashed so
// staleness isn't a concern.
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(STATIC_CACHE);
    cache.put(request, response.clone());
  }
  return response;
}

// Network-first for navigations: always try fresh HTML, fall back to the
// cached shell, then to the offline page as a last resort.
async function networkFirstNavigation(request) {
  try {
    const response = await fetch(request);
    const cache = await caches.open(SHELL_CACHE);
    cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await caches.match(request);
    return cached || caches.match(OFFLINE_URL);
  }
}

// Network-first for the active-jobs API: fresh data when online, cached
// response when the network fails.
async function networkFirstApi(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw new Error("offline-and-no-cache");
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigation(request));
    return;
  }

  if (isStaticAsset(request)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  if (isOfflineReadableApi(url)) {
    event.respondWith(networkFirstApi(request));
    return;
  }
});
