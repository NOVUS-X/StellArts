"use client";

import Navbar from "../components/ui/Navbar";
import Footer from "../components/ui/Footer";
import Hero from "../components/home/Hero";
import FeatureGrid from "../components/home/FeatureGrid";
import UseCases from "../components/home/UseCases";

import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";

import { Shield, Zap, DollarSign, Users, ArrowRight } from "lucide-react";

export default function Home() {
  const whyStellar = [
    {
      icon: Shield,
      title: "Escrow & Smart Contracts",
      description: "Enables trustless transactions between strangers.",
    },
    {
      icon: DollarSign,
      title: "Low Transaction Costs",
      description: "Affordable even for micro-payments.",
    },
    {
      icon: Zap,
      title: "Fast Settlement",
      description: "Near-instant confirmation of bookings and payments.",
    },
    {
      icon: Users,
      title: "Financial Inclusion",
      description:
        "Accessible via mobile wallets, especially in emerging markets.",
    },
  ];

  return (
    <div className="min-h-screen bg-white">
      <Navbar />

      <main>
        {/* Hero */}
        <Hero />

        {/* Features */}
        <FeatureGrid />

        {/* Use Cases */}
        <UseCases />

        {/* Why Stellar */}
        <section className="py-20 bg-white" id="why-stellar">
          <div className="container mx-auto px-6 max-w-6xl">
            <div className="text-center mb-16">
              <span className="text-blue-600 font-semibold text-sm uppercase tracking-wide">
                Technology
              </span>
              <h2 className="text-4xl font-bold text-gray-900 mt-4">
                Why Stellar Blockchain?
              </h2>
              <p className="text-xl text-gray-600 mt-4 max-w-2xl mx-auto">
                Built on enterprise-grade blockchain technology for security and
                speed
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-8">
              {whyStellar.map((reason, index) => (
                <Card
                  key={index}
                  className="bg-gradient-to-br from-gray-50 to-blue-50 border-none shadow-lg"
                >
                  <CardContent className="p-8">
                    <div className="flex items-start space-x-4">
                      <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center flex-shrink-0">
                        <reason.icon className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <h3 className="text-xl font-bold text-gray-900 mb-2">
                          {reason.title}
                        </h3>
                        <p className="text-gray-600 leading-relaxed">
                          {reason.description}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-20 bg-gradient-to-br from-blue-600 to-blue-700">
          <div className="container mx-auto px-6 max-w-4xl text-center">
            <h2 className="text-4xl font-bold text-white mb-6">
              Ready to Get Started?
            </h2>
            <p className="text-xl text-blue-100 mb-10 max-w-2xl mx-auto">
              Join thousands of artisans and clients building trust through
              decentralized transactions
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button
                size="lg"
                className="bg-white text-blue-600 hover:bg-gray-100 text-lg px-8"
              >
                Get Started Now
                <ArrowRight className="ml-2 w-5 h-5" />
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="border-white text-white hover:bg-white/10 text-lg px-8"
              >
                View Documentation
              </Button>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
