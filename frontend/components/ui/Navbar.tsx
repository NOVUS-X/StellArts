'use client';

import { Button } from './button';

import Link from 'next/link';
import Image from 'next/image';

export default function Navbar() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200 w-full">
      <nav className=" mx-auto max-w-375 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center ">
            <div className="w-10 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <Image src="/Stellarts.png" alt="Stellarts Logo" width={100} height={100} />
            </div>
            
          </div>
          <div className="hidden md:flex items-center space-x-8">
            <Link
              href="#features"
              className="text-gray-600 hover:text-blue-600 transition-colors"
            >
              Features
            </Link>
            <Link
              href="#use-cases"
              className="text-gray-600 hover:text-blue-600 transition-colors"
            >
              Use Cases
            </Link>
            <Link
              href="#why-stellar"
              className="text-gray-600 hover:text-blue-600 transition-colors"
            >
              Why Stellar
            </Link>
            <Button className="bg-blue-600 hover:bg-blue-700 text-white">
              Get Started
            </Button>
          </div>
        </div>
      </nav>
    </header>
  );
}