// Minimal service worker — exists only to satisfy PWA/TWA installability criteria.
// This app is a session-cookie-authenticated dashboard with constantly changing data,
// so it deliberately does NOT cache API responses or pages (that would risk serving
// stale or cross-account data). It's a pass-through: every request just goes to the
// network exactly as if there were no service worker at all.
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
