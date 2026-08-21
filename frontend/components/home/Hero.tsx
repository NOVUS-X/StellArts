"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "../ui/button";
import { Card, CardContent } from "../ui/card";
import { Wrench, Zap, Star, ArrowRight } from "lucide-react";
import Link from "next/link";
import Stats from "./Stats";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ArtisanCounts {
  plumbers: number;
  electricians: number;
  carpenters: number;
  painters: number;
  [key: string]: number;
}

export default function Hero() {
  const { t } = useTranslation();
  const [counts, setCounts] = useState<ArtisanCounts | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/artisans/counts`)
      .then((r) => r.json())
      .then((data) => setCounts(data))
      .catch(() => setCounts(null));
  }, []);

  function formatCount(n: number | undefined): string {
    if (n === undefined || n === 0) return t("artisans.comingSoon");
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K+`;
    return `${n} ${t("artisans.available")}`;
  }

  return (
    <section className="min-h-screen flex items-center pt-20 pb-20 px-6 bg-background">
      <div className="container mx-auto max-w-6xl">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div className="space-y-8">
            <div className="inline-block">
              <span className="px-4 py-2 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full text-sm font-medium">
                {t("hero.badge")}
              </span>
            </div>
            <h1 className="text-5xl lg:text-6xl font-bold text-foreground leading-tight">
              {t("hero.title")}
              <span className="block text-blue-600 dark:text-blue-400 mt-2">
                {t("hero.subtitle")}
              </span>
            </h1>
            <p className="text-xl text-muted-foreground leading-relaxed">
              {t("hero.description")}
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              <Button
                asChild
                size="lg"
                className="bg-blue-600 hover:bg-blue-700 text-white text-lg px-8"
              >
                <Link href="/artisans">
                  {t("hero.findArtisan")}
                  <ArrowRight className="ml-2 w-5 h-5" />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="border-blue-600 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 text-lg px-8"
              >
                <Link href="/register?role=artisan">
                  {t("hero.joinAsArtisan")}
                </Link>
              </Button>
            </div>
            <Stats />
          </div>

          <div className="relative">
            <div className="aspect-square bg-gradient-to-br from-accent to-blue-100 dark:from-accent dark:to-blue-900/30 rounded-3xl p-8 flex items-center justify-center">
              <div className="grid grid-cols-2 gap-4 w-full">
                {[
                  {
                    label: t("artisans.plumbers"),
                    icon: Wrench,
                    key: "plumbers",
                    fallback: t("artisans.nearYou"),
                  },
                  {
                    label: t("artisans.electricians"),
                    icon: Zap,
                    key: "electricians",
                    fallback: t("artisans.onDemand"),
                  },
                  {
                    label: t("artisans.carpenters"),
                    icon: Wrench,
                    key: "carpenters",
                    fallback: t("artisans.verified"),
                  },
                  {
                    label: t("artisans.painters"),
                    icon: Star,
                    key: "painters",
                    fallback: t("artisans.topRated"),
                  },
                ].map(({ label, icon: Icon, key, fallback }, i) => (
                  <Card
                    key={key}
                    className={`bg-card shadow-lg hover:shadow-xl transition-shadow${i % 2 === 1 ? " mt-8" : ""}`}
                  >
                    <CardContent className="p-6">
                      <Icon className="w-8 h-8 text-blue-600 dark:text-blue-400 mb-3" />
                      <div className="text-sm font-medium text-foreground">
                        {label}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {counts ? formatCount(counts[key]) : fallback}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
