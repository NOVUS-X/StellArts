"use client";

import Navbar from "../components/ui/Navbar";
import Footer from "../components/ui/Footer";
import Hero from "../components/home/Hero";
import FeatureGrid from "../components/home/FeatureGrid";
import UseCases from "../components/home/UseCases";

import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import Link from "next/link";
import { Shield, Zap, DollarSign, Users, ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function Home() {
  const { t } = useTranslation();

  const whyStellar = [
    {
      icon: Shield,
      title: t("stellar.escrow.title"),
      description: t("stellar.escrow.description"),
    },
    {
      icon: DollarSign,
      title: t("stellar.lowCost.title"),
      description: t("stellar.lowCost.description"),
    },
    {
      icon: Zap,
      title: t("stellar.fastSettlement.title"),
      description: t("stellar.fastSettlement.description"),
    },
    {
      icon: Users,
      title: t("stellar.financialInclusion.title"),
      description: t("stellar.financialInclusion.description"),
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main>
        <Hero />
        <FeatureGrid />
        <UseCases />

        {/* Why Stellar */}
        <section className="py-20 bg-background" id="why-stellar">
          <div className="container mx-auto px-6 max-w-6xl">
            <div className="text-center mb-16">
              <span className="text-blue-600 dark:text-blue-400 font-semibold text-sm uppercase tracking-wide">
                {t("stellar.badge")}
              </span>
              <h2 className="text-4xl font-bold text-foreground mt-4">
                {t("stellar.title")}
              </h2>
              <p className="text-xl text-muted-foreground mt-4 max-w-2xl mx-auto">
                {t("stellar.subtitle")}
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-8">
              {whyStellar.map((reason, index) => (
                <Card
                  key={index}
                  className="bg-gradient-to-br from-muted/50 to-blue-50 dark:to-blue-900/20 border-none shadow-lg"
                >
                  <CardContent className="p-8">
                    <div className="flex items-start space-x-4">
                      <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center flex-shrink-0">
                        <reason.icon className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <h3 className="text-xl font-bold text-foreground mb-2">
                          {reason.title}
                        </h3>
                        <p className="text-muted-foreground leading-relaxed">
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
              {t("cta.title")}
            </h2>
            <p className="text-xl text-blue-100 mb-10 max-w-2xl mx-auto">
              {t("cta.description")}
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button
                asChild
                size="lg"
                className="bg-white text-blue-600 hover:bg-gray-100 text-lg px-8"
              >
                <Link href="/register">
                  {t("cta.getStarted")}
                  <ArrowRight className="ml-2 w-5 h-5" />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="border-white text-white hover:bg-white/10 text-lg px-8"
              >
                <Link
                  href="https://developers.stellar.org/docs"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t("cta.docs")}
                </Link>
              </Button>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
