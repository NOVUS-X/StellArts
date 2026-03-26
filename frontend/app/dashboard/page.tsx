"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../context/AuthContext";
import { Loader2 } from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login?redirect=/dashboard");
      return;
    }
    // Always redirect to dashboard/bookings for default view
    router.replace("/dashboard/bookings");
  }, [isAuthenticated, isLoading, router]);

  return (
    <div className="flex flex-col items-center justify-center p-20 text-gray-500">
       <Loader2 className="w-8 h-8 animate-spin mb-4 text-slate-400" />
       <p>Loading your workspace...</p>
    </div>
  );
}
