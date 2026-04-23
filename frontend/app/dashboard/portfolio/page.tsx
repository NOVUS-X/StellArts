"use client";

import PortfolioGallery from "@/components/portfolio/PortfolioGallery";

export default function PortfolioPage() {
  return (
    <div className="container mx-auto py-12">
      <div className="mb-10 text-center">
        <h1 className="text-4xl font-extrabold tracking-tight lg:text-5xl mb-4">
          Artisan Portfolio
        </h1>
        <p className="text-xl text-slate-500 max-w-2xl mx-auto">
          Manage and showcase your best work to potential clients.
        </p>
      </div>
      
      <PortfolioGallery />
    </div>
  );
}
