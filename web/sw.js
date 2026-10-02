const CACHE_PREFIX = "otayori-desk-shell-";
const CACHE_NAME = `${CACHE_PREFIX}v15`;
const SHELL = ["/", "/app.css?v=20261002-1", "/app.js?v=20261002-5", "/policies.html", "/policies.js?v=20261002-1", "/manifest.webmanifest", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || !SHELL.includes(`${url.pathname}${url.search}`)) return;
  event.respondWith(fetch(event.request).then((response) => {
    if (response.ok) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)));
    }
    return response;
  }).catch(() => caches.open(CACHE_NAME).then((cache) => cache.match(event.request)).then((cached) => cached || Response.error())));
});

function sameOriginNotificationUrl(value) {
  try {
    const url = new URL(typeof value === "string" ? value : "/", self.location.origin);
    if (url.origin === self.location.origin && !url.username && !url.password) return url.href;
  } catch (_) { /* Invalid URLs fall back to this app. */ }
  return `${self.location.origin}/`;
}

self.addEventListener("message", (event) => {
  if (event.data?.type === "otayori-push-capabilities") event.ports?.[0]?.postMessage({ test_notification: true });
});

self.addEventListener("push", (event) => {
  let payload = {};
  try { payload = (event.data ? event.data.json() : {}) || {}; } catch (_) { /* keep the safe fallback */ }
  event.waitUntil(self.registration.showNotification("おたより desk", {
    body: payload.type === "test" ? "テスト通知です。この端末で通知を受け取れました。" : "新しい公開のお知らせがあります。原文をご確認ください。",
    icon: "/icon.svg",
    badge: "/icon.svg",
    data: { url: sameOriginNotificationUrl(payload.url) },
    tag: payload.type === "test" ? "otayori-desk-test" : "otayori-desk-update",
    renotify: true,
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = sameOriginNotificationUrl(event.notification.data?.url);
  event.waitUntil(clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
    const current = windows.find((window) => {
      try { return new URL(window.url).origin === self.location.origin && "focus" in window; } catch (_) { return false; }
    });
    if (current) return current.navigate(target).then(() => current.focus());
    return clients.openWindow(target);
  }));
});
