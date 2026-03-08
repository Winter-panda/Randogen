const CACHE_NAME = "randogen-v1";
const STATIC_ASSETS = [
  "/",
  "/index.html",
  "/manifest.json"
];

// Install: cache static shell
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch strategy:
// - API calls (/api/*): network-first, fall back to cache
// - Tile images (openstreetmap): cache-first with 7-day TTL
// - Everything else: network-first, fall back to cache
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET and chrome-extension requests
  if (request.method !== "GET" || url.protocol === "chrome-extension:") return;

  // API calls: network first, no offline fallback (data must be fresh)
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(request).catch(() => new Response(JSON.stringify({ error: "Hors ligne" }), {
        headers: { "Content-Type": "application/json" }
      }))
    );
    return;
  }

  // OSM tiles: cache-first with background refresh
  if (url.hostname.endsWith("tile.openstreetmap.org")) {
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(request);
        if (cached) return cached;
        const response = await fetch(request);
        if (response.ok) cache.put(request, response.clone());
        return response;
      })
    );
    return;
  }

  // App shell and static assets: network-first, fall back to cache
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          caches.open(CACHE_NAME).then((cache) => cache.put(request, response.clone()));
        }
        return response;
      })
      .catch(() => caches.match(request).then((cached) => cached ?? caches.match("/index.html")))
  );
});
