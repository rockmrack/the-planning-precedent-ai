'use client';

import { useEffect, useState } from 'react';
import { Download, X, RefreshCw, Wifi, WifiOff } from 'lucide-react';
import {
  registerServiceWorker,
  setupInstallPrompt,
  showInstallPrompt,
  canShowInstallPrompt,
  isOnline,
  addConnectionListeners,
  isInstalledPWA
} from '@/lib/pwa';

interface PWAProviderProps {
  children: React.ReactNode;
}

export function PWAProvider({ children }: PWAProviderProps) {
  const [showInstallBanner, setShowInstallBanner] = useState(false);
  const [showUpdateBanner, setShowUpdateBanner] = useState(false);
  const [online, setOnline] = useState(true);
  const [showOfflineBanner, setShowOfflineBanner] = useState(false);

  useEffect(() => {
    // Register service worker
    registerServiceWorker();

    // Setup install prompt
    setupInstallPrompt();

    // Check initial online status
    setOnline(isOnline());

    // Listen for install prompt availability
    const handleInstallAvailable = () => {
      // Don't show if already installed
      if (!isInstalledPWA()) {
        setShowInstallBanner(true);
      }
    };

    // Listen for updates
    const handleUpdateAvailable = () => {
      setShowUpdateBanner(true);
    };

    // Connection listeners
    const cleanupConnection = addConnectionListeners(
      () => {
        setOnline(true);
        setShowOfflineBanner(false);
      },
      () => {
        setOnline(false);
        setShowOfflineBanner(true);
        // Auto-hide after 5 seconds
        setTimeout(() => setShowOfflineBanner(false), 5000);
      }
    );

    window.addEventListener('pwa-install-available', handleInstallAvailable);
    window.addEventListener('pwa-update-available', handleUpdateAvailable);

    return () => {
      window.removeEventListener('pwa-install-available', handleInstallAvailable);
      window.removeEventListener('pwa-update-available', handleUpdateAvailable);
      cleanupConnection();
    };
  }, []);

  const handleInstall = async () => {
    const installed = await showInstallPrompt();
    if (installed) {
      setShowInstallBanner(false);
    }
  };

  const handleUpdate = () => {
    window.location.reload();
  };

  const dismissInstall = () => {
    setShowInstallBanner(false);
    // Don't show again for 24 hours
    localStorage.setItem('pwa-install-dismissed', Date.now().toString());
  };

  // Check if install was recently dismissed
  useEffect(() => {
    const dismissed = localStorage.getItem('pwa-install-dismissed');
    if (dismissed) {
      const dismissedTime = parseInt(dismissed);
      const dayInMs = 24 * 60 * 60 * 1000;
      if (Date.now() - dismissedTime < dayInMs) {
        setShowInstallBanner(false);
      }
    }
  }, [showInstallBanner]);

  return (
    <>
      {children}

      {/* Offline Banner */}
      {showOfflineBanner && (
        <div className="fixed top-0 left-0 right-0 z-50 animate-slide-down">
          <div className="bg-amber-500 text-white px-4 py-3 flex items-center justify-center gap-2 text-sm">
            <WifiOff className="w-4 h-4" />
            <span>You&apos;re offline. Some features may be limited.</span>
            <button
              onClick={() => setShowOfflineBanner(false)}
              className="ml-4 p-1 hover:bg-amber-600 rounded"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Online Restored Banner */}
      {online && !showOfflineBanner && (
        <div className="hidden">
          {/* Could show a "Back online" toast here */}
        </div>
      )}

      {/* Update Available Banner */}
      {showUpdateBanner && (
        <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 z-50 animate-slide-up">
          <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-4">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                <RefreshCw className="w-5 h-5 text-blue-600" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-slate-900">Update Available</h3>
                <p className="text-sm text-slate-600 mt-1">
                  A new version is available. Reload to get the latest features.
                </p>
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={handleUpdate}
                    className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Reload Now
                  </button>
                  <button
                    onClick={() => setShowUpdateBanner(false)}
                    className="px-4 py-2 text-slate-600 text-sm hover:text-slate-800 transition-colors"
                  >
                    Later
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Install PWA Banner */}
      {showInstallBanner && canShowInstallPrompt() && (
        <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 z-50 animate-slide-up">
          <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-xl shadow-lg p-4 text-white">
            <button
              onClick={dismissInstall}
              className="absolute top-2 right-2 p-1 hover:bg-white/10 rounded transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                <Download className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">Install Planning AI</h3>
                <p className="text-sm text-blue-100 mt-1">
                  Get quick access from your home screen with offline support.
                </p>
                <button
                  onClick={handleInstall}
                  className="mt-3 px-4 py-2 bg-white text-blue-600 text-sm font-medium rounded-lg hover:bg-blue-50 transition-colors"
                >
                  Install App
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Connection Status Indicator (for development/debugging) */}
      {process.env.NODE_ENV === 'development' && (
        <div className="fixed bottom-4 left-4 z-40">
          <div className={`px-2 py-1 rounded text-xs flex items-center gap-1 ${
            online ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
          }`}>
            {online ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {online ? 'Online' : 'Offline'}
          </div>
        </div>
      )}

      <style jsx global>{`
        @keyframes slide-down {
          from {
            transform: translateY(-100%);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }

        @keyframes slide-up {
          from {
            transform: translateY(100%);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }

        .animate-slide-down {
          animation: slide-down 0.3s ease-out;
        }

        .animate-slide-up {
          animation: slide-up 0.3s ease-out;
        }
      `}</style>
    </>
  );
}
