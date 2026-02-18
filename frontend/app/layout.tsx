import * as React from 'react';
import "./globals.css";
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

const inter = Inter({ 
  subsets: ['latin'],
  display: 'swap',
  preload: false
});

export const metadata: Metadata = {
  title: 'Stellarts - Uber for Artisans | Built on Stellar Blockchain',
  icons: {
    icon: "/Stellarts.png",
  },
  description:
    'Connect with trusted artisans in your area. Stellarts is a decentralized marketplace platform leveraging Stellar blockchain for secure, transparent, and fast transactions.',
  openGraph: {
    images: [
      {
        url: '',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    images: [
      {
        url: '',
      },
    ],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
