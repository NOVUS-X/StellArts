"use client";

import { motion } from "framer-motion";
import { MapPin, Shield, Zap, Star, Globe, Users } from "lucide-react";

const features = [
  {
    icon: MapPin,
    title: "Artisan Discovery",
    description:
      "Search and book artisans within your area, filtered by skills, ratings, and availability.",
    color: "text-blue-400",
    glow: "group-hover:shadow-blue-500/20"
  },
  {
    icon: Users,
    title: "Geolocation Matching",
    description:
      "Uber-like system that intelligently maps clients to nearby artisans.",
    color: "text-indigo-400",
    glow: "group-hover:shadow-indigo-500/20"
  },
  {
    icon: Shield,
    title: "Secure Escrow Payments",
    description:
      "Clients deposit payments into escrow. Funds are released automatically once work is confirmed.",
    color: "text-emerald-400",
    glow: "group-hover:shadow-emerald-500/20"
  },
  {
    icon: Star,
    title: "Reputation & Reviews",
    description:
      "Ratings and feedback stored immutably to help build trust in the community.",
    color: "text-yellow-400",
    glow: "group-hover:shadow-yellow-500/20"
  },
  {
    icon: Globe,
    title: "Multi-currency Support",
    description:
      "Transact in your preferred local currency or stablecoin using Stellar's built-in DEX.",
    color: "text-purple-400",
    glow: "group-hover:shadow-purple-500/20"
  },
  {
    icon: Zap,
    title: "Low Fees & Fast Settlement",
    description:
      "Near-instant payments with minimal transaction costs powered by Stellar.",
    color: "text-orange-400",
    glow: "group-hover:shadow-orange-500/20"
  },
];

export default function FeatureGrid() {
  return (
    <section className="relative py-24" id="features">
      <div className="container mx-auto px-6 max-w-7xl">
        <div className="text-center mb-20">
          <motion.span 
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-primary font-semibold text-sm uppercase tracking-widest"
          >
            Capabilities
          </motion.span>
          <motion.h2 
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="text-4xl md:text-5xl font-bold text-white mt-4"
          >
            Everything You Need
          </motion.h2>
          <motion.p 
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="text-xl text-slate-400 mt-6 max-w-2xl mx-auto"
          >
            Powerful features designed to create trust, transparency, and
            seamless transactions.
          </motion.p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {features.map((feature, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1 }}
              className={`glass-card p-10 rounded-3xl group transition-all hover:-translate-y-2 ${feature.glow} hover:border-white/10`}
            >
              <div className={`w-14 h-14 bg-white/5 rounded-2xl flex items-center justify-center mb-8 group-hover:scale-110 transition-transform`}>
                <feature.icon className={`w-7 h-7 ${feature.color}`} />
              </div>
              <h3 className="text-2xl font-bold text-white mb-4">
                {feature.title}
              </h3>
              <p className="text-slate-400 leading-relaxed text-lg">
                {feature.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
