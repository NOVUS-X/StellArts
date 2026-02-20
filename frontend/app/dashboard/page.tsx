"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../context/AuthContext";

export default function DashboardPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login?redirect=/dashboard");
      return;
    }
    if (user?.role === "artisan") {
      router.replace("/dashboard/bookings");
    } else {
      router.replace("/dashboard/bookings");
    }
  }, [isAuthenticated, isLoading, user?.role, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <p className="text-gray-500">Redirecting…</p>
    </div>
  );
}
