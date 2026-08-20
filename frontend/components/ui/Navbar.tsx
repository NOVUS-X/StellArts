"use client";

import { useState, useEffect } from "react";
import { useTheme } from "next-themes";
import { Button } from "./button";
import Link from "next/link";
import Image from "next/image";
import { useWallet } from "../../context/WalletContext";
import { useAuth } from "../../context/AuthContext";
import CurrencySelector from "./CurrencySelector";
import NotificationBell from "./NotificationBell";
import LanguageSwitcher from "./LanguageSwitcher";
import { Menu, X, Sun, Moon } from "lucide-react";
import { useTranslation } from "react-i18next";

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) return <div className="w-9 h-9" />;

  return (
    <button
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      aria-label="Toggle dark mode"
      className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
    >
      {resolvedTheme === "dark" ? (
        <Sun className="w-5 h-5" />
      ) : (
        <Moon className="w-5 h-5" />
      )}
    </button>
  );
}

function WalletButton() {
  const { address, isConnected, connect, disconnect } = useWallet();
  const { t } = useTranslation();

  if (isConnected && address) {
    const short = `${address.slice(0, 4)}...${address.slice(-4)}`;
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm font-mono text-muted-foreground bg-muted px-3 py-1 rounded-full">
          {short}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={disconnect}
          className="border-border text-muted-foreground hover:text-foreground"
        >
          {t("nav.disconnect")}
        </Button>
      </div>
    );
  }

  return (
    <Button
      onClick={connect}
      className="bg-blue-600 hover:bg-blue-700 text-white"
    >
      {t("nav.connectWallet")}
    </Button>
  );
}

export default function Navbar() {
  const { isAuthenticated, logout } = useAuth();
  const { t } = useTranslation();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-b border-border w-full">
      <nav className="mx-auto max-w-6xl px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center">
            <div className="w-10 h-10 bg-accent rounded-lg flex items-center justify-center overflow-hidden">
              <Image
                src="/Stellarts.png"
                alt="Stellarts Logo"
                width={40}
                height={40}
                className="object-contain"
              />
            </div>
            <span className="ml-2 text-xl font-bold text-foreground hidden md:block">
              Stellarts
            </span>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center space-x-8">
            <Link
              href="/#features"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              {t("nav.features")}
            </Link>
            <Link
              href="/#use-cases"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              {t("nav.useCases")}
            </Link>
            <Link
              href="/#why-stellar"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              {t("nav.whyStellar")}
            </Link>

            {isAuthenticated && (
              <Link
                href="/dashboard"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("nav.dashboard")}
              </Link>
            )}

            {isAuthenticated && (
              <Link
                href="/analytics"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("nav.analytics")}
              </Link>
            )}

            {isAuthenticated && (
              <Link
                href="/settings"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("nav.settings")}
              </Link>
            )}

            <CurrencySelector />

            <LanguageSwitcher />

            {isAuthenticated && <NotificationBell />}

            <ThemeToggle />

            <WalletButton />

            {isAuthenticated && (
              <Button
                variant="outline"
                size="sm"
                onClick={logout}
                className="border-border text-muted-foreground hover:text-foreground"
              >
                {t("nav.logout")}
              </Button>
            )}
          </div>

          {/* Mobile Controls */}
          <div className="md:hidden flex items-center gap-2">
            <CurrencySelector />
            <LanguageSwitcher />
            <ThemeToggle />
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="p-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              {isMenuOpen ? (
                <X className="w-6 h-6" />
              ) : (
                <Menu className="w-6 h-6" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {isMenuOpen && (
          <div className="md:hidden mt-4 pt-4 pb-4 border-t border-border space-y-4">
            <Link
              href="/#features"
              onClick={() => setIsMenuOpen(false)}
              className="block text-muted-foreground hover:text-foreground transition-colors"
            >
              {t("nav.features")}
            </Link>
            <Link
              href="/#use-cases"
              onClick={() => setIsMenuOpen(false)}
              className="block text-muted-foreground hover:text-foreground transition-colors"
            >
              {t("nav.useCases")}
            </Link>
            <Link
              href="/#why-stellar"
              onClick={() => setIsMenuOpen(false)}
              className="block text-muted-foreground hover:text-foreground transition-colors"
            >
              {t("nav.whyStellar")}
            </Link>

            {isAuthenticated && (
              <Link
                href="/dashboard"
                onClick={() => setIsMenuOpen(false)}
                className="block text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("nav.dashboard")}
              </Link>
            )}

            {isAuthenticated && (
              <Link
                href="/analytics"
                onClick={() => setIsMenuOpen(false)}
                className="block text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("nav.analytics")}
              </Link>
            )}

            {isAuthenticated && (
              <Link
                href="/settings"
                onClick={() => setIsMenuOpen(false)}
                className="block text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("nav.settings")}
              </Link>
            )}

            {isAuthenticated && (
              <div className="py-2">
                <NotificationBell />
              </div>
            )}

            <WalletButton />

            {isAuthenticated && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  logout();
                  setIsMenuOpen(false);
                }}
                className="w-full border-border text-muted-foreground hover:text-foreground"
              >
                {t("nav.logout")}
              </Button>
            )}
          </div>
        )}
      </nav>
    </header>
  );
}
