"use client";

import { motion } from "framer-motion";
import { MapPin, Globe, Wrench } from "lucide-react";

const useCases = [
  {
    icon: Wrench,
    title: "Urban Communities",
    description:
      "Quick discovery of trusted artisans for emergency home repairs in fast-paced cities.",
  },
  {
    icon: MapPin,
    title: "Small Towns",
    description: "Empowering local artisans to gain visibility beyond traditional personal networks.",
  },
  {
    icon: Globe,
    title: "Cross-border Work",
    description:
      "Migrant artisans can get verified and receive fair, instant payments securely and globally.",
  },
];

export default function UseCases() {
  return (
    <section className="py-24" id="use-cases">
      <div className="container mx-auto px-6 max-w-7xl">
        <div className="text-center mb-20">
          <motion.span 
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-primary font-semibold text-sm uppercase tracking-widest"
          >
            Use Cases
          </motion.span>
          <motion.h2 
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="text-4xl md:text-5xl font-bold text-white mt-4"
          >
            Real World Impact
          </motion.h2>
          <motion.p 
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="text-xl text-slate-400 mt-6 max-w-2xl mx-auto"
          >
            Empowering communities and individual livelihoods through technology.
          </motion.p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {useCases.map((useCase, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1 }}
              className="glass p-10 rounded-3xl border-white/5 hover:border-white/10 transition-all hover:bg-white/[0.05]"
            >
              <div className="w-14 h-14 bg-primary/10 rounded-2xl flex items-center justify-center mb-8">
                <useCase.icon className="w-7 h-7 text-primary" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-4">
                {useCase.title}
              </h3>
              <p className="text-slate-400 leading-relaxed text-lg">
                {useCase.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
