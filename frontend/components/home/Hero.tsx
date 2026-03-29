"use client";

import { useEffect, useState } from "react";
import { Button } from "../ui/button";
import { motion } from "framer-motion";
import { Wrench, Zap, Star, ArrowRight, Shield } from "lucide-react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ArtisanCounts {
  plumbers: number;
  electricians: number;
  carpenters: number;
  painters: number;
  [key: string]: number;
}

function formatCount(n: number | undefined): string {
  if (n === undefined || n === 0) return "Global";
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K+`;
  return `${n} Active`;
}

export default function Hero() {
  const [counts, setCounts] = useState<ArtisanCounts | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/artisans/counts`)
      .then((r) => r.json())
      .then((data) => setCounts(data))
      .catch(() => setCounts(null));
  }, []);

  return (
    <section className="relative pt-32 pb-24 overflow-hidden">
      {/* Background Glows */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-600/20 rounded-full blur-[128px] -z-10" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-[128px] -z-10" />

      <div className="container mx-auto px-6 max-w-7xl">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8 }}
            className="space-y-8"
          >
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm font-medium">
              <Shield className="w-4 h-4" />
              <span>Secured by Stellar Blockchain</span>
            </div>
            
            <h1 className="text-5xl lg:text-7xl font-bold tracking-tight leading-[1.1]">
              The Future of <br />
              <span className="text-gradient">Local Services</span>
            </h1>
            
            <p className="text-xl text-slate-400 leading-relaxed max-w-xl">
              Connect with verified artisans, secure payments via escrow, and 
              experience the power of decentralized trust. The marketplace 
              where quality meets transparency.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 pt-4">
              <Button
                asChild
                size="lg"
                className="bg-primary hover:bg-primary/90 text-white text-lg px-8 h-14 shadow-[0_0_20px_rgba(59,130,246,0.3)] transition-all hover:scale-105"
              >
                <Link href="/artisans">
                  Explore Artisans
                  <ArrowRight className="ml-2 w-5 h-5" />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="glass border-white/10 hover:bg-white/5 text-white text-lg px-8 h-14 transition-all"
              >
                <Link href="/register?role=artisan">List Your Services</Link>
              </Button>
            </div>

            <div className="flex items-center space-x-6 pt-8 border-t border-white/5">
              <div className="flex -space-x-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="w-10 h-10 rounded-full border-2 border-[#050B18] bg-slate-800" />
                ))}
              </div>
              <div className="text-sm">
                <p className="text-white font-medium">Join 2,000+ artisans</p>
                <p className="text-slate-500">Already building their future on StellArts</p>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="relative"
          >
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "Plumbers", icon: Wrench, count: counts?.plumbers, color: "text-blue-400" },
                { label: "Electricians", icon: Zap, count: counts?.electricians, color: "text-yellow-400", delay: 0.1 },
                { label: "Carpenters", icon: Wrench, count: counts?.carpenters, color: "text-orange-400", delay: 0.2 },
                { label: "Painters", icon: Star, count: counts?.painters, color: "text-purple-400", delay: 0.3 },
              ].map((card, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 + (card.delay || 0) }}
                  className="glass-card p-6 rounded-2xl group hover:border-blue-500/30 transition-all cursor-default"
                >
                  <div className={`w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                    <card.icon className={`w-6 h-6 ${card.color}`} />
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-white font-semibold">{card.label}</h3>
                    <p className="text-slate-500 text-sm">{formatCount(card.count)}</p>
                  </div>
                </motion.div>
              ))}
            </div>
            
            {/* Visual Decoration */}
            <div className="absolute -top-12 -right-12 w-24 h-24 bg-blue-500/20 rounded-full blur-3xl" />
            <div className="absolute -bottom-12 -left-12 w-24 h-24 bg-indigo-500/20 rounded-full blur-3xl" />
          </motion.div>
        </div>
      </div>
    </section>
  );
}