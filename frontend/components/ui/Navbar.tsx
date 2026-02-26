'use client';

import { Button } from './button';
import Link from 'next/link';
import Image from 'next/image';
import { useWallet } from '../../context/WalletContext';
import { useAuth } from '../../context/AuthContext';

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

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200 w-full">
      <nav className=" mx-auto max-w-375 px-6 py-4">
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center">
            <div className="w-10 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <Image src="/Stellarts.png" alt="Stellarts Logo" width={100} height={100} />
            </div>
          </Link>
          <div className="hidden md:flex items-center space-x-8">
            <Link
              href="/#features"
              className="text-gray-600 hover:text-blue-600 transition-colors"
            >
              Features
            </Link>
            <Link
              href="/#use-cases"
              className="text-gray-600 hover:text-blue-600 transition-colors"
            >
              Use Cases
            </Link>
            <Link
              href="/#why-stellar"
              className="text-gray-600 hover:text-blue-600 transition-colors"
            >
              Why Stellar
            </Link>
            {isAuthenticated && (
              <Link
                href="/dashboard"
                className="text-gray-600 hover:text-blue-600 transition-colors"
              >
                Dashboard
              </Link>
            )}
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
        </div>
      </nav>
    </header>
  );
}