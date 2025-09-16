self.addEventListener('install', event => {
  event.waitUntil(caches.open('stegtalk-v1').then(cache => cache.addAll([
    '/', '/stegtalk.html', '/manifest.json'
  ])));
});
self.addEventListener('fetch', event => {
  event.respondWith(caches.match(event.request).then(resp => resp || fetch(event.request)));
});
