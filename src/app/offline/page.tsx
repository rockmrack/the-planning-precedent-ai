'use client';

import { WifiOff, RefreshCw, Home } from 'lucide-react';
import { useState, useEffect } from 'react';

export default function OfflinePage() {
  const [isOnline, setIsOnline] = useState(false);

  useEffect(() => {
    // Check online status
    setIsOnline(navigator.onLine);

    const handleOnline = () => {
      setIsOnline(true);
      // Redirect to home after a short delay
      setTimeout(() => {
        window.location.href = '/';
      }, 1000);
    };

    const handleOffline = () => {
      setIsOnline(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const handleRetry = () => {
    window.location.reload();
  };

  const handleGoHome = () => {
    window.location.href = '/';
  };

  if (isOnline) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Connection restored. Redirecting...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-lg p-8 text-center">
        {/* Offline Icon */}
        <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <WifiOff className="w-10 h-10 text-slate-400" />
        </div>

        {/* Title */}
        <h1 className="text-2xl font-bold text-slate-800 mb-2">
          You're Offline
        </h1>

        {/* Description */}
        <p className="text-slate-600 mb-8">
          It looks like you've lost your internet connection. Some features may be unavailable until you reconnect.
        </p>

        {/* Available Offline Features */}
        <div className="bg-blue-50 rounded-xl p-4 mb-8 text-left">
          <h2 className="font-semibold text-blue-800 mb-2">Available Offline:</h2>
          <ul className="text-sm text-blue-700 space-y-1">
            <li>• View saved planning cases</li>
            <li>• Browse cached search results</li>
            <li>• Read downloaded documents</li>
            <li>• Review your recent analyses</li>
          </ul>
        </div>

        {/* Action Buttons */}
        <div className="space-y-3">
          <button
            onClick={handleRetry}
            className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium"
          >
            <RefreshCw className="w-5 h-5" />
            Try Again
          </button>

          <button
            onClick={handleGoHome}
            className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-slate-100 text-slate-700 rounded-xl hover:bg-slate-200 transition-colors font-medium"
          >
            <Home className="w-5 h-5" />
            View Cached Content
          </button>
        </div>

        {/* Status Indicator */}
        <div className="mt-8 flex items-center justify-center gap-2 text-sm text-slate-500">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
          </span>
          Waiting for connection...
        </div>
      </div>
    </div>
  );
}
