// Service Worker para PWA - Cache básico
const CACHE_NAME = 'geoportal-v120'; // ⬅️ INCREMENTAR ESTE NÚMERO CADA VEZ QUE ACTUALICES
const urlsToCache = [
  './',
  './style.css',
  './img/logo/logo.png'
];

function offlineFallback(request, isDataRequest = false) {
  if (isDataRequest) {
    return new Response(JSON.stringify({ error: 'offline', ok: false }), {
      status: 503,
      headers: { 'Content-Type': 'application/json; charset=utf-8' }
    });
  }

  if (request && request.destination === 'document') {
    return caches.match('./index.html').then(cached => {
      if (cached) return cached;
      return new Response('Sin conexión', {
        status: 503,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' }
      });
    });
  }

  return Promise.resolve(new Response('', { status: 503, statusText: 'Offline' }));
}

// Instalar Service Worker y cachear recursos
self.addEventListener('install', event => {
  // Activar el nuevo SW inmediatamente para evitar servir HTML viejo en cache.
  self.skipWaiting();
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('✅ Cache abierto:', CACHE_NAME);
        return cache.addAll(urlsToCache);
      })
      .catch(error => {
        console.warn('SW: install sin cache completo (continuando):', error);
      })
  );
});

// Interceptar peticiones con estrategia Network First para archivos críticos
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') {
    return;
  }

  const url = new URL(event.request.url);
  if (!url.protocol.startsWith('http')) {
    return;
  }

  const pathname = url.pathname.toLowerCase();
  const isGeojson = pathname.endsWith('.geojson');
  const isJson = pathname.endsWith('.json');
  const isManifest = pathname.endsWith('/manifest.json') || pathname.endsWith('manifest.json');
  const isDataRequest = isGeojson || isJson || isManifest;
  
  // Network First para index.html y archivos .geojson (siempre obtener la última versión)
  if (pathname.endsWith('index.html') || isDataRequest) {
    const responsePromise = fetch(event.request)
        .then(async response => {
          // Evitar cachear JSON/GeoJSON pesados para no saturar memoria/cuota en iOS
          if (!isDataRequest && response && response.ok) {
            const responseClone = response.clone();
            try {
              const cache = await caches.open(CACHE_NAME);
              await cache.put(event.request, responseClone);
            } catch (error) {
              console.warn('SW: no se pudo guardar en cache', event.request.url, error);
            }
          }
          return response;
        })
        .catch(() => {
          // Si falla la red, intentar desde cache sin relanzar fetch en catch
          return caches.match(event.request)
          .catch(() => null)
          .then(cached => {
            if (cached) return cached;
            return offlineFallback(event.request, isDataRequest);
          });
        });

    event.respondWith(
      Promise.resolve(responsePromise)
        .catch(() => offlineFallback(event.request, isDataRequest))
    );
  } 
  // Cache First para otros recursos (imágenes, CSS, etc.)
  else {
    const responsePromise = caches.match(event.request)
        .catch(() => null)
        .then(response => {
          if (response) {
            return response;
          }
          return fetch(event.request)
            .then(networkResponse => {
              if (networkResponse && networkResponse.ok) {
                const clone = networkResponse.clone();
                caches.open(CACHE_NAME)
                  .then(cache => cache.put(event.request, clone))
                  .catch(() => {});
              }
              return networkResponse;
            })
            .catch(() => offlineFallback(event.request, false));
        });

    event.respondWith(
      Promise.resolve(responsePromise)
        .catch(() => offlineFallback(event.request, false))
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
