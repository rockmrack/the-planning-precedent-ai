import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Toaster } from 'react-hot-toast';
import { Providers } from './providers';

const inter = Inter({ subsets: ['latin'] });

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
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en-GB">
      <body className={inter.className}>
        <Providers>
          <div className="min-h-screen bg-slate-50">
            {children}
          </div>
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
