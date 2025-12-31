import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Toaster } from 'react-hot-toast';
import { Providers } from './providers';
import { PWAProvider } from '@/components/pwa-provider';

const inter = Inter({ subsets: ['latin'] });

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#3b82f6' },
    { media: '(prefers-color-scheme: dark)', color: '#1e3a8a' }
  ]
};

export const metadata: Metadata = {
  title: 'Planning Precedent AI - Camden Council Planning Search',
  description:
    'Find winning precedents for your planning application. AI-powered search across 10 years of Camden Council planning decisions.',
  keywords: [
    'planning permission',
    'Camden Council',
    'planning precedents',
    'Hampstead',
    'Belsize Park',
    'conservation area',
    'planning application',
    'UK planning',
    'London Borough of Camden',
  ],
  authors: [{ name: 'Planning Precedent AI' }],
  creator: 'Planning Precedent AI',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Planning AI'
  },
  formatDetection: {
    telephone: false
  },
  openGraph: {
    title: 'Planning Precedent AI',
    description:
      'Find winning precedents for your planning application in Camden',
    type: 'website',
    locale: 'en_GB',
  },
  robots: {
    index: true,
    follow: true,
  },
  other: {
    'mobile-web-app-capable': 'yes',
    'apple-mobile-web-app-capable': 'yes',
    'apple-mobile-web-app-status-bar-style': 'default',
    'msapplication-TileColor': '#3b82f6',
    'msapplication-tap-highlight': 'no'
  }
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en-GB">
      <head>
        {/* PWA Icons */}
        <link rel="icon" href="/icons/icon-192x192.png" />
        <link rel="apple-touch-icon" href="/icons/icon-192x192.png" />
        <link rel="apple-touch-icon" sizes="152x152" href="/icons/icon-152x152.png" />
        <link rel="apple-touch-icon" sizes="180x180" href="/icons/icon-192x192.png" />
      </head>
      <body className={inter.className}>
        <Providers>
          <PWAProvider>
            <div className="min-h-screen bg-slate-50">
              {children}
            </div>
          </PWAProvider>
          <Toaster
            position="bottom-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#1e293b',
                color: '#fff',
              },
              success: {
                iconTheme: {
                  primary: '#22c55e',
                  secondary: '#fff',
                },
              },
              error: {
                iconTheme: {
                  primary: '#ef4444',
                  secondary: '#fff',
                },
              },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
