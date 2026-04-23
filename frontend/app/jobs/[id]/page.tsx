"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "../../../components/ui/Navbar";
import Footer from "../../../components/ui/Footer";
import BOMItemList from "../../../components/inventory/BOMItemList";
import { useAuth } from "../../../context/AuthContext";

export default function JobPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const id = params?.id as string;

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace(`/login?redirect=/jobs/${id}`);
    }
  }, [isAuthenticated, isLoading, router, id]);

  if (isLoading || !isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="pt-24 pb-16 px-4 max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Bill of Materials
        </h1>
        <p className="text-gray-600 mb-8">
          Mark items you will supply so the artisan knows what to source.
        </p>
        <BOMItemList jobId={id} />
      </main>
      <Footer />
    </div>
  );
}
