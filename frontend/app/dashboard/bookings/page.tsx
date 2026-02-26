"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "../../../components/ui/Navbar";
import Footer from "../../../components/ui/Footer";
import { Button } from "../../../components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { api, type BookingResponse } from "../../../lib/api";
import { useAuth } from "../../../context/AuthContext";
import { Calendar, ArrowLeft } from "lucide-react";

export default function DashboardBookingsPage() {
  const router = useRouter();
  const { token, isAuthenticated, isLoading } = useAuth();
  const [bookings, setBookings] = useState<BookingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login?redirect=/dashboard/bookings");
      return;
    }
    if (!token) return;
    setLoading(true);
    api.bookings
      .myBookings(token)
      .then(setBookings)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load bookings")
      )
      .finally(() => setLoading(false));
  }, [token, isAuthenticated, isLoading, router]);

  if (!isAuthenticated && !isLoading) return null;

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="pt-24 pb-16 px-4 max-w-4xl mx-auto">
        <Link
          href="/dashboard"
          className="inline-flex items-center text-gray-600 hover:text-blue-600 mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Dashboard
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">My Bookings</h1>
        <p className="text-gray-600 mb-8">
          View and manage your booking requests.
        </p>

        {error && (
          <p className="text-red-600 bg-red-50 p-4 rounded-lg mb-6">{error}</p>
        )}

        {loading ? (
          <p className="text-gray-500">Loading…</p>
        ) : bookings.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-gray-500">
              No bookings yet.{" "}
              <Link href="/artisans" className="text-blue-600 hover:underline">
                Find an artisan
              </Link>{" "}
              to create one.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {bookings.map((b) => (
              <Card key={b.id}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg">{b.service}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-sm text-gray-600 flex items-center gap-2">
                    <Calendar className="w-4 h-4" />
                    {b.date
                      ? new Date(b.date).toLocaleString()
                      : "Date not set"}
                  </p>
                  <p className="text-sm">
                    Cost:{" "}
                    {b.estimated_cost != null
                      ? `$${Number(b.estimated_cost).toFixed(2)}`
                      : "—"}
                  </p>
                  <p className="text-sm">
                    Status:{" "}
                    <span
                      className={
                        b.status === "completed"
                          ? "text-green-600"
                          : b.status === "cancelled"
                            ? "text-gray-500"
                            : "text-blue-600"
                      }
                    >
                      {b.status}
                    </span>
                  </p>
                  <Link
                    href={`/artisans/${b.artisan_id}`}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    View artisan
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
