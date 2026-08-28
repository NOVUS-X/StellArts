import * as React from "react";
import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { WalletProvider } from "../context/WalletContext";
import { AuthProvider } from "../context/AuthContext";
import { CurrencyProvider } from "../context/CurrencyContext";
import { NotificationProvider } from "../context/NotificationContext";
import { ToastProvider } from "../context/ToastContext";
import { I18nProvider } from "../components/I18nProvider";
import { ServiceWorkerRegister } from "../components/ServiceWorkerRegister";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  title: "Stellarts - Uber for Artisans | Built on Stellar Blockchain",
  icons: {
    icon: "/Stellarts.png",
  },
  description:
    "Connect with trusted artisans in your area. Stellarts is a decentralized marketplace platform leveraging Stellar blockchain for secure, transparent, and fast transactions.",
  openGraph: {
    images: [
      {
        url: "",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    images: [
      {
        url: "",
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
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <ServiceWorkerRegister />
          <Toaster richColors position="top-right" />
          <I18nProvider>
            <AuthProvider>
              <WalletProvider>
                <CurrencyProvider>
                  <ToastProvider>
                    <NotificationProvider>{children}</NotificationProvider>
                  </ToastProvider>
                </CurrencyProvider>
              </WalletProvider>
            </AuthProvider>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
