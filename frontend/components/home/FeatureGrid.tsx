"use client";

import { Card, CardContent } from "../ui/card";
import { MapPin, Shield, Zap, Star, Globe, Users } from "lucide-react";

const features = [
  {
    icon: MapPin,
    title: "Artisan Discovery",
    description:
      "Search and book artisans within your area, filtered by skills, ratings, and availability.",
  },
  {
    icon: Users,
    title: "Geolocation Matching",
    description:
      "Uber-like system that intelligently maps clients to nearby artisans.",
  },
  {
    icon: Shield,
    title: "Secure Escrow Payments",
    description:
      "Clients deposit payments into escrow. Funds are released automatically once work is confirmed.",
  },
  {
    icon: Star,
    title: "Reputation & Reviews",
    description:
      "Ratings and feedback stored immutably to help build trust in the community.",
  },
  {
    icon: Globe,
    title: "Multi-currency Support",
    description:
      "Transact in your preferred local currency or stablecoin using Stellar's built-in DEX.",
  },
  {
    icon: Zap,
    title: "Low Fees & Fast Settlement",
    description:
      "Near-instant payments with minimal transaction costs powered by Stellar.",
  },
];

export default function FeatureGrid() {
  return (
    <section className="py-20 bg-gray-50" id="features">
      <div className="container mx-auto px-6 max-w-6xl">
        <div className="text-center mb-16">
          <span className="text-blue-600 font-semibold text-sm uppercase tracking-wide">
            Features
          </span>
          <h2 className="text-4xl font-bold text-gray-900 mt-4">
            Everything You Need
          </h2>
          <p className="text-xl text-gray-600 mt-4 max-w-2xl mx-auto">
            Powerful features designed to create trust, transparency, and
            seamless transactions
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {features.map((feature, index) => (
            <Card
              key={index}
              className="bg-white border-none shadow-lg hover:shadow-xl transition-all hover:-translate-y-1"
            >
              <CardContent className="p-8">
                <div className="w-14 h-14 bg-blue-100 rounded-2xl flex items-center justify-center mb-6">
                  <feature.icon className="w-7 h-7 text-blue-600" />
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-3">
                  {feature.title}
                </h3>
                <p className="text-gray-600 leading-relaxed">
                  {feature.description}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
