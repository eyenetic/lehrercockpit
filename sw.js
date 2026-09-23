/* Lehrercockpit service worker: shows push notifications. No offline caching. */

self.addEventListener('install', function () {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', function (event) {
  var data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { body: event.data ? event.data.text() : '' };
  }
  event.waitUntil(self.registration.showNotification(data.title || 'Lehrercockpit', {
    body: data.body || '',
    tag: data.tag || undefined,
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    data: { url: data.url || '/' },
  }));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var target = new URL((event.notification.data && event.notification.data.url) || '/', self.registration.scope).href;
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (windows) {
    for (var i = 0; i < windows.length; i++) {
      if (windows[i].url.indexOf(self.registration.scope) === 0 && 'focus' in windows[i]) {
        return windows[i].focus();
      }
    }
    return self.clients.openWindow(target);
  }));
});
