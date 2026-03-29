"use client";

import Navbar from "../components/ui/Navbar";
import Footer from "../components/ui/Footer";
import Hero from "../components/home/Hero";
import FeatureGrid from "../components/home/FeatureGrid";
import UseCases from "../components/home/UseCases";
import { Button } from "../components/ui/button";
import Link from "next/link";
import { Shield, Zap, DollarSign, Users, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";

export default function Home() {
  const whyStellar = [
    {
      icon: Shield,
      title: "Escrow & Smart Contracts",
      description: "Enables trustless transactions between strangers with automated safety.",
      color: "text-blue-400"
    },
    {
      icon: DollarSign,
      title: "Low Transaction Costs",
      description: "Fraction-of-a-cent fees make micro-payments viable for everyone.",
      color: "text-emerald-400"
    },
    {
      icon: Zap,
      title: "Fast Settlement",
      description: "Near-instant confirmation ensures money moves as fast as work happens.",
      color: "text-yellow-400"
    },
    {
      icon: Users,
      title: "Financial Inclusion",
      description: "Accessible globally via mobile wallets, bypassing traditional banking hurdles.",
      color: "text-purple-400"
    },
  ];

  return (
    <div className="min-h-screen">
      <Navbar />

      <main>
        <Hero />
        <FeatureGrid />
        <UseCases />

        {/* Why Stellar */}
        <section className="py-24" id="why-stellar">
          <div className="container mx-auto px-6 max-w-7xl">
            <div className="text-center mb-20">
              <motion.span 
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="text-primary font-semibold text-sm uppercase tracking-widest"
              >
                Technology
              </motion.span>
              <motion.h2 
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
                className="text-4xl md:text-5xl font-bold text-white mt-4"
              >
                Why Stellar Blockchain?
              </motion.h2>
              <motion.p 
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
                className="text-xl text-slate-400 mt-6 max-w-2xl mx-auto"
              >
                Built on enterprise-grade blockchain technology for security, 
                speed, and global reach.
              </motion.p>
            </div>

            <div className="grid md:grid-cols-2 gap-8">
              {whyStellar.map((reason, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, scale: 0.95 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.1 }}
                  className="glass-card p-10 rounded-3xl border-white/5 hover:border-white/10 transition-all hover:bg-white/[0.05]"
                >
                  <div className="flex items-start space-x-6">
                    <div className="w-14 h-14 bg-white/5 rounded-2xl flex items-center justify-center flex-shrink-0 border border-white/10">
                      <reason.icon className={`w-7 h-7 ${reason.color}`} />
                    </div>
                    <div>
                      <h3 className="text-2xl font-bold text-white mb-3">
                        {reason.title}
                      </h3>
                      <p className="text-slate-400 leading-relaxed text-lg">
                        {reason.description}
                      </p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-24">
          <div className="container mx-auto px-6 max-w-5xl">
            <motion.div 
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="relative p-12 md:p-20 rounded-[3rem] overflow-hidden text-center bg-gradient-to-br from-blue-600 to-indigo-700 shadow-2xl shadow-blue-500/20"
            >
              <div className="absolute top-0 left-0 w-full h-full bg-[url('/grid.svg')] opacity-10" />
              
              <div className="relative z-10 space-y-8">
                <h2 className="text-4xl md:text-6xl font-bold text-white max-w-3xl mx-auto">
                  Ready to Start Building Your Future?
                </h2>
                <p className="text-xl text-blue-100 max-w-2xl mx-auto leading-relaxed">
                  Join thousands of artisans and clients already building trust through
                  decentralized transactions and secure escrow payments.
                </p>
                <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
                  <Button
                    asChild
                    size="lg"
                    className="bg-white text-blue-600 hover:bg-white/90 text-lg px-10 h-16 rounded-2xl shadow-xl transition-all hover:scale-105"
                  >
                    <Link href="/register">
                      Get Started Now
                      <ArrowRight className="ml-2 w-5 h-5" />
                    </Link>
                  </Button>
                  <Button
                    asChild
                    size="lg"
                    variant="outline"
                    className="border-white/20 text-white hover:bg-white/10 text-lg px-10 h-16 rounded-2xl backdrop-blur-md transition-all"
                  >
                    <Link
                      href="https://developers.stellar.org/docs"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Documentation
                    </Link>
                  </Button>
                </div>
              </div>
              
              {/* Background Shapes */}
              <div className="absolute -top-24 -right-24 w-64 h-64 bg-white/10 rounded-full blur-3xl" />
              <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-white/5 rounded-full blur-3xl" />
            </motion.div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
