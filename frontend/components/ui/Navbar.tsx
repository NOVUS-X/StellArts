'use client';

import { Button } from './button';
import Link from 'next/link';
import Image from 'next/image';
import { useWallet } from '../../context/WalletContext';
import { useAuth } from '../../context/AuthContext';
import { motion } from 'framer-motion';

function WalletButton() {
  const { address, isConnected, connect, disconnect } = useWallet();

  if (isConnected && address) {
    const short = `${address.slice(0, 4)}...${address.slice(-4)}`;
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm font-mono text-blue-400 bg-blue-500/10 border border-blue-500/20 px-3 py-1 rounded-full">
          {short}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={disconnect}
          className="glass border-white/10 text-white hover:bg-white/5"
        >
          Disconnect
        </Button>
      </div>
    );
  }

  return (
    <Button
      onClick={connect}
      className="bg-primary hover:bg-primary/90 text-white shadow-[0_0_15px_rgba(59,130,246,0.5)] transition-all hover:scale-105"
    >
      Connect Wallet
    </Button>
  );
}

export default function Navbar() {
  const { isAuthenticated, logout } = useAuth();

  return (
    <motion.header 
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      className="fixed top-0 left-0 right-0 z-50 glass border-b border-white/5 w-full"
    >
      <nav className="container mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center group">
            <div className="w-12 h-12 bg-white/5 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform border border-white/10">
              <Image src="/Stellarts.png" alt="Stellarts Logo" width={40} height={40} className="object-contain" />
            </div>
            <span className="ml-3 text-xl font-bold text-white tracking-tight group-hover:text-primary transition-colors">StellArts</span>
          </Link>
          
          <div className="hidden md:flex items-center space-x-8">
            <Link
              href="/#features"
              className="text-slate-400 hover:text-white transition-colors text-sm font-medium"
            >
              Features
            </Link>
            <Link
              href="/#use-cases"
              className="text-slate-400 hover:text-white transition-colors text-sm font-medium"
            >
              Use Cases
            </Link>
            <Link
              href="/#why-stellar"
              className="text-slate-400 hover:text-white transition-colors text-sm font-medium"
            >
              Why Stellar
            </Link>
            {isAuthenticated && (
              <Link
                href="/dashboard"
                className="text-slate-400 hover:text-white transition-colors text-sm font-medium"
              >
                Dashboard
              </Link>
            )}
            
            <div className="h-6 w-px bg-white/10 mx-2" />
            
            <WalletButton />
            
            {isAuthenticated ? (
              <Button
                variant="outline"
                size="sm"
                onClick={logout}
                className="glass border-white/10 text-white hover:bg-white/5"
              >
                Log out
              </Button>
            ) : (
              <Button asChild variant="ghost" className="text-white hover:bg-white/5">
                <Link href="/login">Login</Link>
              </Button>
            )}
          </div>
        </div>
      </nav>
    </motion.header>
  );
}