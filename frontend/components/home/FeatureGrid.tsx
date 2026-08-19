"use client";

import { useTranslation } from "react-i18next";
import { Card, CardContent } from "../ui/card";
import { MapPin, Shield, Zap, Star, Globe, Users } from "lucide-react";

export default function FeatureGrid() {
  const { t } = useTranslation();

  const features = [
    {
      icon: MapPin,
      title: t("features.decentralized.title"),
      description: t("features.decentralized.description"),
    },
    {
      icon: Users,
      title: t("features.matching.title"),
      description: t("features.matching.description"),
    },
    {
      icon: Shield,
      title: t("features.booking.title"),
      description: t("features.booking.description"),
    },
    {
      icon: Star,
      title: t("features.reviews.title"),
      description: t("features.reviews.description"),
    },
    {
      icon: Globe,
      title: t("features.tracking.title"),
      description: t("features.tracking.description"),
    },
    {
      icon: Zap,
      title: t("features.analytics.title"),
      description: t("features.analytics.description"),
    },
  ];

  return (
    <section className="py-20 bg-muted/50" id="features">
      <div className="container mx-auto px-6 max-w-6xl">
        <div className="text-center mb-16">
          <span className="text-blue-600 dark:text-blue-400 font-semibold text-sm uppercase tracking-wide">
            {t("nav.features")}
          </span>
          <h2 className="text-4xl font-bold text-foreground mt-4">
            {t("features.title")}
          </h2>
          <p className="text-xl text-muted-foreground mt-4 max-w-2xl mx-auto">
            {t("features.subtitle")}
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {features.map((feature, index) => (
            <Card
              key={index}
              className="bg-card border-none shadow-lg hover:shadow-xl transition-all hover:-translate-y-1"
            >
              <CardContent className="p-8">
                <div className="w-14 h-14 bg-blue-100 dark:bg-blue-900/30 rounded-2xl flex items-center justify-center mb-6">
                  <feature.icon className="w-7 h-7 text-blue-600 dark:text-blue-400" />
                </div>
                <h3 className="text-xl font-bold text-foreground mb-3">
                  {feature.title}
                </h3>
                <p className="text-muted-foreground leading-relaxed">
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
