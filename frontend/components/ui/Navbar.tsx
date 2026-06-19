'use client';

import { useState, useEffect } from 'react';
import { useTheme } from 'next-themes';
import { Button } from './button';
import Link from 'next/link';
import Image from 'next/image';
import { useWallet } from '../../context/WalletContext';
import { useAuth } from '../../context/AuthContext';
import CurrencySelector from './CurrencySelector';
import NotificationBell from './NotificationBell';
import { Menu, X, Sun, Moon } from 'lucide-react';

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) return <div className="w-9 h-9" />;

  return (
    <button
      onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
      aria-label="Toggle dark mode"
      className="p-2 rounded-md text-gray-600 hover:text-blue-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-blue-400 dark:hover:bg-gray-800 transition-colors"
    >
      {resolvedTheme === 'dark' ? (
        <Sun className="w-5 h-5" />
      ) : (
        <Moon className="w-5 h-5" />
      )}
    </button>
  );
}

function WalletButton() {
  const { address, isConnected, connect, disconnect } = useWallet();

  if (isConnected && address) {
    const short = `${address.slice(0, 4)}...${address.slice(-4)}`;
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm font-mono text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 px-3 py-1 rounded-full">
          {short}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={disconnect}
          className="border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300"
        >
          Disconnect
        </Button>
      </div>
    );
  }

  return (
    <Button
      onClick={connect}
      className="bg-blue-600 hover:bg-blue-700 text-white"
    >
      Connect Wallet
    </Button>
  );
}

export default function Navbar() {
  const { isAuthenticated, logout } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-700 w-full">
      <nav className="mx-auto max-w-6xl px-6 py-4">
        <div className="flex items-center justify-between">

          {/* Logo */}
          <Link href="/" className="flex items-center">
            <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center overflow-hidden">
              <Image
                src="/Stellarts.png"
                alt="Stellarts Logo"
                width={40}
                height={40}
                className="object-contain"
              />
            </div>
            <span className="ml-2 text-xl font-bold text-gray-900 dark:text-gray-100 hidden md:block">
              Stellarts
            </span>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center space-x-8">
            <Link href="/#features" className="text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400">
              Features
            </Link>
            <Link href="/#use-cases" className="text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400">
              Use Cases
            </Link>
            <Link href="/#why-stellar" className="text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400">
              Why Stellar
            </Link>

            {isAuthenticated && (
              <Link href="/dashboard" className="text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400">
                Dashboard
              </Link>
            )}

            <CurrencySelector />

            {isAuthenticated && <NotificationBell />}

            <ThemeToggle />

            <WalletButton />

            {isAuthenticated && (
              <Button
                variant="outline"
                size="sm"
                onClick={logout}
                className="border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300"
              >
                Log out
              </Button>
            )}
          </div>

          {/* Mobile Controls */}
          <div className="md:hidden flex items-center gap-2">
            <CurrencySelector />
            <ThemeToggle />
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="p-2 text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400"
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
          <div className="md:hidden mt-4 pt-4 pb-4 border-t border-gray-200 dark:border-gray-700 space-y-4">
            <Link href="/#features" onClick={() => setIsMenuOpen(false)} className="block text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400">
              Features
            </Link>
            <Link href="/#use-cases" onClick={() => setIsMenuOpen(false)} className="block text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400">
              Use Cases
            </Link>
            <Link href="/#why-stellar" onClick={() => setIsMenuOpen(false)} className="block text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400">
              Why Stellar
            </Link>

            {isAuthenticated && (
              <Link href="/dashboard" onClick={() => setIsMenuOpen(false)} className="block text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400">
                Dashboard
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
                className="w-full border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300"
              >
                Log out
              </Button>
            )}
          </div>
        )}
      </nav>
    </header>
  );
}