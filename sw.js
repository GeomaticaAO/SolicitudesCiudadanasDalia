// Service Worker para PWA - Cache básico
const CACHE_NAME = 'geoportal-v98'; // ⬅️ INCREMENTAR ESTE NÚMERO CADA VEZ QUE ACTUALICES
const urlsToCache = [
  './',
  './style.css',
  './img/logo/logo.png'
];

// Instalar Service Worker y cachear recursos
self.addEventListener('install', event => {
  // NO forzar activación inmediata - esperar a que termine la sesión actual
  // self.skipWaiting(); // DESACTIVADO para evitar recargas automáticas
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('✅ Cache abierto:', CACHE_NAME);
        return cache.addAll(urlsToCache);
      })
  );
});

// Interceptar peticiones con estrategia Network First para archivos críticos
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Network First para index.html y archivos .geojson (siempre obtener la última versión)
  if (url.pathname.endsWith('index.html') || 
      url.pathname.endsWith('Index.html') || 
      url.pathname.endsWith('.geojson')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // Clonar respuesta para cachear
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseClone);
          });
          return response;
        })
        .catch(() => {
          // Si falla la red, intentar desde cache
          return caches.match(event.request);
        })
    );
  } 
  // Cache First para otros recursos (imágenes, CSS, etc.)
  else {
    event.respondWith(
      caches.match(event.request)
        .then(response => {
          if (response) {
            return response;
          }
          return fetch(event.request);
        })
    );
  }
});

// Limpiar caches antiguos y tomar control inmediatamente
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('🗑️ Eliminando cache antiguo:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      // Tomar control de todas las páginas inmediatamente
      return self.clients.claim();
    })
  );
});
