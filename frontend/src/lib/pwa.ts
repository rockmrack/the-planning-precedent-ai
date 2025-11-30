/**
 * PWA Utilities
 * Service worker registration and offline support
 */

// Check if service workers are supported
export function isServiceWorkerSupported(): boolean {
  return 'serviceWorker' in navigator;
}

// Register the service worker
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!isServiceWorkerSupported()) {
    console.log('[PWA] Service workers not supported');
    return null;
  }

  try {
    const registration = await navigator.serviceWorker.register('/sw.js', {
      scope: '/'
    });

    console.log('[PWA] Service worker registered:', registration.scope);

    // Handle updates
    registration.addEventListener('updatefound', () => {
      const newWorker = registration.installing;
      if (newWorker) {
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            // New content is available
            console.log('[PWA] New content available');
            dispatchEvent(new CustomEvent('pwa-update-available'));
          }
        });
      }
    });

    return registration;
  } catch (error) {
    console.error('[PWA] Service worker registration failed:', error);
    return null;
  }
}

// Unregister service worker (for development)
export async function unregisterServiceWorker(): Promise<boolean> {
  if (!isServiceWorkerSupported()) {
    return false;
  }

  try {
    const registration = await navigator.serviceWorker.ready;
    const success = await registration.unregister();
    console.log('[PWA] Service worker unregistered:', success);
    return success;
  } catch (error) {
    console.error('[PWA] Unregistration failed:', error);
    return false;
  }
}

// Check if the app is running as installed PWA
export function isInstalledPWA(): boolean {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    (window.navigator as any).standalone === true
  );
}

// Check online status
export function isOnline(): boolean {
  return navigator.onLine;
}

// Add online/offline listeners
export function addConnectionListeners(
  onOnline: () => void,
  onOffline: () => void
): () => void {
  window.addEventListener('online', onOnline);
  window.addEventListener('offline', onOffline);

  return () => {
    window.removeEventListener('online', onOnline);
    window.removeEventListener('offline', onOffline);
  };
}

// Request background sync
export async function requestBackgroundSync(tag: string): Promise<boolean> {
  if (!('sync' in ServiceWorkerRegistration.prototype)) {
    console.log('[PWA] Background sync not supported');
    return false;
  }

  try {
    const registration = await navigator.serviceWorker.ready;
    await (registration as any).sync.register(tag);
    console.log('[PWA] Background sync registered:', tag);
    return true;
  } catch (error) {
    console.error('[PWA] Background sync failed:', error);
    return false;
  }
}

// Request notification permission
export async function requestNotificationPermission(): Promise<NotificationPermission> {
  if (!('Notification' in window)) {
    console.log('[PWA] Notifications not supported');
    return 'denied';
  }

  const permission = await Notification.requestPermission();
  console.log('[PWA] Notification permission:', permission);
  return permission;
}

// Subscribe to push notifications
export async function subscribeToPush(vapidPublicKey: string): Promise<PushSubscription | null> {
  if (!('PushManager' in window)) {
    console.log('[PWA] Push not supported');
    return null;
  }

  try {
    const registration = await navigator.serviceWorker.ready;

    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
    });

    console.log('[PWA] Push subscription:', subscription);
    return subscription;
  } catch (error) {
    console.error('[PWA] Push subscription failed:', error);
    return null;
  }
}

// Convert VAPID key to Uint8Array
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }

  return outputArray;
}

// IndexedDB for offline storage
const DB_NAME = 'PlanningPrecedentAI';
const DB_VERSION = 1;

export async function openOfflineDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;

      // Store for pending offline actions
      if (!db.objectStoreNames.contains('pending-actions')) {
        db.createObjectStore('pending-actions', { keyPath: 'id', autoIncrement: true });
      }

      // Store for cached search results
      if (!db.objectStoreNames.contains('cached-searches')) {
        const searchStore = db.createObjectStore('cached-searches', { keyPath: 'query' });
        searchStore.createIndex('timestamp', 'timestamp', { unique: false });
      }

      // Store for saved cases offline
      if (!db.objectStoreNames.contains('saved-cases-offline')) {
        const casesStore = db.createObjectStore('saved-cases-offline', { keyPath: 'reference' });
        casesStore.createIndex('savedAt', 'savedAt', { unique: false });
      }
    };
  });
}

// Save search results for offline access
export async function cacheSearchResults(query: string, results: any[]): Promise<void> {
  const db = await openOfflineDB();
  const tx = db.transaction('cached-searches', 'readwrite');
  const store = tx.objectStore('cached-searches');

  store.put({
    query,
    results,
    timestamp: Date.now()
  });

  await tx.complete;
  db.close();
}

// Get cached search results
export async function getCachedSearchResults(query: string): Promise<any[] | null> {
  const db = await openOfflineDB();
  const tx = db.transaction('cached-searches', 'readonly');
  const store = tx.objectStore('cached-searches');

  const request = store.get(query);

  return new Promise((resolve, reject) => {
    request.onsuccess = () => {
      const result = request.result;
      db.close();
      resolve(result ? result.results : null);
    };
    request.onerror = () => {
      db.close();
      reject(request.error);
    };
  });
}

// Queue action for when back online
export async function queueOfflineAction(type: string, data: any): Promise<void> {
  const db = await openOfflineDB();
  const tx = db.transaction('pending-actions', 'readwrite');
  const store = tx.objectStore('pending-actions');

  store.add({
    type,
    data,
    timestamp: Date.now()
  });

  await tx.complete;
  db.close();

  // Request background sync
  await requestBackgroundSync(`sync-${type}`);
}

// Save case for offline access
export async function saveCaseOffline(caseData: any): Promise<void> {
  const db = await openOfflineDB();
  const tx = db.transaction('saved-cases-offline', 'readwrite');
  const store = tx.objectStore('saved-cases-offline');

  store.put({
    ...caseData,
    savedAt: Date.now()
  });

  await tx.complete;
  db.close();
}

// Get offline saved cases
export async function getOfflineSavedCases(): Promise<any[]> {
  const db = await openOfflineDB();
  const tx = db.transaction('saved-cases-offline', 'readonly');
  const store = tx.objectStore('saved-cases-offline');

  const request = store.getAll();

  return new Promise((resolve, reject) => {
    request.onsuccess = () => {
      db.close();
      resolve(request.result || []);
    };
    request.onerror = () => {
      db.close();
      reject(request.error);
    };
  });
}

// Install prompt handling
let deferredPrompt: any = null;

export function setupInstallPrompt(): void {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    dispatchEvent(new CustomEvent('pwa-install-available'));
    console.log('[PWA] Install prompt available');
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    console.log('[PWA] App installed');
  });
}

export async function showInstallPrompt(): Promise<boolean> {
  if (!deferredPrompt) {
    console.log('[PWA] No install prompt available');
    return false;
  }

  deferredPrompt.prompt();
  const { outcome } = await deferredPrompt.userChoice;
  console.log('[PWA] Install prompt outcome:', outcome);

  deferredPrompt = null;
  return outcome === 'accepted';
}

export function canShowInstallPrompt(): boolean {
  return deferredPrompt !== null;
}
