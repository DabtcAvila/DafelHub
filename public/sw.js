// Dafel Technologies Service Worker - Ultra Performance Caching
// Version: 1.0.0

const CACHE_NAME = 'dafel-v1';
const STATIC_CACHE = 'dafel-static-v1';
const RUNTIME_CACHE = 'dafel-runtime-v1';

// Resources to cache immediately
const PRECACHE_URLS = [
  '/',
  '/login',
  '/favicon.svg',
  '/favicon.ico',
  '/manifest.json'
];

// Install event - precache critical resources
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('Service Worker: Precaching static resources');
        return cache.addAll(PRECACHE_URLS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME && cacheName !== STATIC_CACHE && cacheName !== RUNTIME_CACHE) {
            console.log('Service Worker: Deleting old cache', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - intelligent caching strategy
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip cross-origin requests
  if (url.origin !== location.origin) {
    return;
  }

  // Handle different types of requests
  if (request.destination === 'document') {
    // Network first for HTML pages
    event.respondWith(networkFirst(request));
  } else if (request.destination === 'image') {
    // Cache first for images
    event.respondWith(cacheFirst(request));
  } else if (request.url.includes('/_next/static/')) {
    // Cache first for static assets (they're immutable)
    event.respondWith(cacheFirst(request));
  } else if (request.url.includes('/api/')) {
    // Network only for API calls
    event.respondWith(fetch(request));
  } else {
    // Stale while revalidate for other resources
    event.respondWith(staleWhileRevalidate(request));
  }
});

// Network first strategy (for HTML pages)
async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('Network failed, trying cache:', error);
    const cachedResponse = await caches.match(request);
    return cachedResponse || new Response('Offline', { status: 503 });
  }
}

// Cache first strategy (for static assets)
async function cacheFirst(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('Failed to fetch:', request.url, error);
    return new Response('Resource not available', { status: 404 });
  }
}

// Stale while revalidate strategy
async function staleWhileRevalidate(request) {
  const cachedResponse = await caches.match(request);
  const fetchPromise = fetch(request).then(networkResponse => {
    if (networkResponse.ok) {
      const cache = caches.open(RUNTIME_CACHE);
      cache.then(c => c.put(request, networkResponse.clone()));
    }
    return networkResponse;
  }).catch(() => cachedResponse);

  return cachedResponse || fetchPromise;
}

// Background sync for critical actions
self.addEventListener('sync', event => {
  if (event.tag === 'background-sync') {
    event.waitUntil(doBackgroundSync());
  }
});

async function doBackgroundSync() {
  // Handle background sync tasks
  console.log('Background sync triggered');
}

// Push notifications support
self.addEventListener('push', event => {
  if (!event.data) return;

  const options = {
    body: event.data.text(),
    icon: '/icon-192.png',
    badge: '/favicon-32.png',
    tag: 'dafel-notification',
    requireInteraction: true
  };

  event.waitUntil(
    self.registration.showNotification('Dafel Technologies', options)
  );
});

// Notification click handler
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow('/')
  );
});