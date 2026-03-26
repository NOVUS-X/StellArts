'use client';

import { Twitter, Github, Linkedin } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';

export default function Footer() {
  return (
    <footer className="bg-[#050B18] text-slate-400 py-20 border-t border-white/5">
      <div className="container mx-auto px-6 max-w-7xl">
        <div className="grid md:grid-cols-4 gap-12 mb-16">
          <div className="space-y-6">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-white/5 rounded-xl flex items-center justify-center border border-white/10">
                <Image src="/Stellarts.png" alt="Stellarts Logo" width={32} height={32} />
              </div>
              <span className="text-2xl font-bold text-white tracking-tight">StellArts</span>
            </div>
            <p className="text-lg leading-relaxed">
              Empowering artisans through decentralized trust and near-instant blockchain settlements.
            </p>
          </div>
          <div>
            <h4 className="font-bold text-white text-lg mb-6">Product</h4>
            <ul className="space-y-4">
              <li>
                <Link href="/#features" className="hover:text-primary transition-colors">
                  Features
                </Link>
              </li>
              <li>
                <Link href="/#use-cases" className="hover:text-primary transition-colors">
                  Use Cases
                </Link>
              </li>
              <li>
                <Link href="/artisans" className="hover:text-primary transition-colors">
                  Find Artisans
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="font-bold text-white text-lg mb-6">Support</h4>
            <ul className="space-y-4">
              <li>
                <Link href="#" className="hover:text-primary transition-colors">
                  Documentation
                </Link>
              </li>
              <li>
                <Link href="#" className="hover:text-primary transition-colors">
                  Help Center
                </Link>
              </li>
              <li>
                <Link href="#" className="hover:text-primary transition-colors">
                  Terms of Service
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="font-bold text-white text-lg mb-6">Connect</h4>
            <div className="flex space-x-4">
              {[
                { icon: Twitter, href: "#" },
                { icon: Github, href: "https://github.com/StellArts" },
                { icon: Linkedin, href: "#" }
              ].map((social, idx) => (
                <Link
                  key={idx}
                  href={social.href}
                  className="w-12 h-12 glass rounded-xl flex items-center justify-center hover:bg-white/10 transition-all hover:scale-110"
                >
                  <social.icon className="w-6 h-6 text-white" />
                </Link>
              ))}
            </div>
          </div>
        </div>
        <div className="border-t border-white/5 pt-10 text-center">
          <p className="text-slate-500">© {new Date().getFullYear()} StellArts. Built with ❤️ on Stellar.</p>
        </div>
      </div>
    </footer>
  );
}