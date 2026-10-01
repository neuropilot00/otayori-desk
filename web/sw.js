const CACHE_NAME = "otayori-desk-shell-v6";
const SHELL = ["/", "/app.css?v=20261001-11", "/app.js?v=20261001-11", "/manifest.webmanifest", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  event.respondWith(fetch(event.request).then((response) => {
    const copy = response.clone();
    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
    return response;
  }).catch(() => caches.match(event.request).then((cached) => cached || caches.match("/"))));
});

self.addEventListener("push", (event) => {
  let payload = { title: "おたより desk", body: "新しい学校のお知らせがあります。", url: "/" };
  try { payload = { ...payload, ...(event.data ? event.data.json() : {}) }; } catch (_) { /* keep the safe fallback */ }
  event.waitUntil(self.registration.showNotification(payload.title, {
    body: payload.body,
    icon: "/icon.svg",
    badge: "/icon.svg",
    data: { url: payload.url || "/" },
    tag: "otayori-desk-update",
    renotify: true,
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/", self.location.origin).href;
  event.waitUntil(clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
    const current = windows.find((window) => "focus" in window);
    if (current) { current.navigate(target); return current.focus(); }
    return clients.openWindow(target);
  }));
});
