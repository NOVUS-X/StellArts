"use client";

import { useTranslation } from "react-i18next";
import { Card, CardContent } from "../ui/card";
import { MapPin, Globe, Wrench } from "lucide-react";

export default function UseCases() {
  const { t } = useTranslation();

  const useCases = [
    {
      icon: Wrench,
      title: t("useCases.forClients.title"),
      description: t("useCases.forClients.description"),
    },
    {
      icon: MapPin,
      title: t("useCases.forArtisans.title"),
      description: t("useCases.forArtisans.description"),
    },
    {
      icon: Globe,
      title: t("stellar.financialInclusion.title"),
      description: t("stellar.financialInclusion.description"),
    },
  ];

  return (
    <section className="py-20 bg-blue-600" id="use-cases">
      <div className="container mx-auto px-6 max-w-6xl">
        <div className="text-center mb-16">
          <span className="text-blue-200 font-semibold text-sm uppercase tracking-wide">
            {t("useCases.title")}
          </span>
          <h2 className="text-4xl font-bold text-white mt-4">
            {t("useCases.subtitle")}
          </h2>
          <p className="text-xl text-blue-100 mt-4 max-w-2xl mx-auto">
            {t("hero.description")}
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {useCases.map((useCase, index) => (
            <Card
              key={index}
              className="bg-white/10 backdrop-blur-sm border-white/20 hover:bg-white/20 transition-all"
            >
              <CardContent className="p-8">
                <div className="w-14 h-14 bg-white rounded-2xl flex items-center justify-center mb-6">
                  <useCase.icon className="w-7 h-7 text-blue-600" />
                </div>
                <h3 className="text-xl font-bold text-white mb-3">
                  {useCase.title}
                </h3>
                <p className="text-blue-100 leading-relaxed">
                  {useCase.description}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
