"use client";

import { useState } from "react";
import { Button } from "./button";
import Link from "next/link";
import Image from "next/image";
import { useWallet } from "../../context/WalletContext";
import { useAuth } from "../../context/AuthContext";
import CurrencySelector from "./CurrencySelector";
import NotificationBell from "./NotificationBell";
import { Menu, X } from "lucide-react";

function WalletButton() {
  const { address, isConnected, connect, disconnect } = useWallet();

  if (isConnected && address) {
    const short = `${address.slice(0, 4)}...${address.slice(-4)}`;
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm font-mono text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
          {short}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={disconnect}
          className="border-gray-300 text-gray-600"
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
    <header className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200 w-full">
      <nav className="mx-auto max-w-6xl px-6 py-4">
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center overflow-hidden">
              <Image
                src="/Stellarts.png"
                alt="Stellarts Logo"
                width={40}
                height={40}
                className="object-contain"
              />
            </div>
            <span className="ml-2 text-xl font-bold text-gray-900 hidden md:block">
              Stellarts
            </span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-8">
            <Link href="/#features" className="text-gray-600 hover:text-blue-600">
              Features
            </Link>
            <Link href="/#use-cases" className="text-gray-600 hover:text-blue-600">
              Use Cases
            </Link>
            <Link href="/#why-stellar" className="text-gray-600 hover:text-blue-600">
              Why Stellar
            </Link>

            {isAuthenticated && (
              <Link href="/dashboard" className="text-gray-600 hover:text-blue-600">
                Dashboard
              </Link>
            )}

            <CurrencySelector />

            {isAuthenticated && <NotificationBell />}

            <WalletButton />

            {isAuthenticated && (
              <Button
                variant="outline"
                size="sm"
                onClick={logout}
                className="border-gray-300 text-gray-600"
              >
                Log out
              </Button>
            )}
          </div>

          {/* Mobile Menu Button */}
          <div className="md:hidden flex items-center gap-4">
            <CurrencySelector />
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="p-2 text-gray-600 hover:text-blue-600 transition-colors"
              aria-label="Toggle menu"
            >
              {isMenuOpen ? (
                <X className="w-6 h-6" />
              ) : (
                <Menu className="w-6 h-6" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="md:hidden mt-4 pb-4 space-y-4 border-t border-gray-100 pt-4">
            <Link href="/#features" onClick={() => setIsMenuOpen(false)}>
              Features
            </Link>
            <Link href="/#use-cases" onClick={() => setIsMenuOpen(false)}>
              Use Cases
            </Link>
            <Link href="/#why-stellar" onClick={() => setIsMenuOpen(false)}>
              Why Stellar
            </Link>

            {isAuthenticated && (
              <Link href="/dashboard" onClick={() => setIsMenuOpen(false)}>
                Dashboard
              </Link>
            )}

            <WalletButton />

            {isAuthenticated && (
              <>
                <NotificationBell />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    logout();
                    setIsMenuOpen(false);
                  }}
                  className="w-full border-gray-300 text-gray-600"
                >
                  Log out
                </Button>
              </>
            )}
          </div>
        )}
      </nav>
    </header>
  );
}
