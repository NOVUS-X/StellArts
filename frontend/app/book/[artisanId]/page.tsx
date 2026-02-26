"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "../../../components/ui/Navbar";
import Footer from "../../../components/ui/Footer";
import { Button } from "../../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { api, type ArtisanProfileResponse, type BookingCreate } from "../../../lib/api";
import { useAuth } from "../../../context/AuthContext";

export default function BookArtisanPage() {
  const params = useParams();
  const router = useRouter();
  const { token, isAuthenticated } = useAuth();
  const artisanId = Number(params.artisanId);
  const [profile, setProfile] = useState<ArtisanProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [service, setService] = useState("");
  const [date, setDate] = useState("");
  const [estimatedCost, setEstimatedCost] = useState("");
  const [estimatedHours, setEstimatedHours] = useState("");
  const [location, setLocation] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!isAuthenticated) {
      router.push(`/login?redirect=/book/${artisanId}`);
      return;
    }
    if (Number.isNaN(artisanId)) {
      setError("Invalid artisan");
      setLoading(false);
      return;
    }
    api.artisans
      .getProfile(artisanId)
      .then(setProfile)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load artisan")
      )
      .finally(() => setLoading(false));
  }, [artisanId, isAuthenticated, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !profile) return;
    setError("");
    setSubmitting(true);
    try {
      const body: BookingCreate = {
        artisan_id: artisanId,
        service: service.trim() || "Service request",
        date: new Date(date).toISOString(),
        estimated_cost: parseFloat(estimatedCost) || 0,
        estimated_hours: estimatedHours ? parseFloat(estimatedHours) : undefined,
        location: location.trim() || undefined,
        notes: notes.trim() || undefined,
      };
      await api.bookings.create(body, token);
      router.push("/dashboard/bookings");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create booking");
    } finally {
      setSubmitting(false);
    }
  }

  if (!isAuthenticated) return null;

  if (loading) {
    return (
      <div className="min-h-screen bg-white">
        <Navbar />
        <main className="pt-24 pb-16 px-4 max-w-2xl mx-auto">
          <p className="text-gray-500">Loading…</p>
        </main>
        <Footer />
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="min-h-screen bg-white">
        <Navbar />
        <main className="pt-24 pb-16 px-4 max-w-2xl mx-auto">
          <p className="text-red-600">{error}</p>
          <Link href="/artisans" className="text-blue-600 hover:underline mt-4 inline-block">
            Back to artisans
          </Link>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="pt-24 pb-16 px-4 max-w-2xl mx-auto">
        <Link
          href={profile ? `/artisans/${artisanId}` : "/artisans"}
          className="inline-flex items-center text-gray-600 hover:text-blue-600 mb-6"
        >
          ← Back
        </Link>
        <Card>
          <CardHeader>
            <CardTitle>Book {profile?.name || "Artisan"}</CardTitle>
            <CardDescription>
              Submit your booking request. The artisan will confirm availability.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <p className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
                  {error}
                </p>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Service description *
                </label>
                <input
                  type="text"
                  required
                  value={service}
                  onChange={(e) => setService(e.target.value)}
                  placeholder="e.g. Plumbing repair for kitchen sink"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Date & time *
                </label>
                <input
                  type="datetime-local"
                  required
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Estimated cost (XLM/USD) *
                  </label>
                  <input
                    type="number"
                    required
                    min="0"
                    step="0.01"
                    value={estimatedCost}
                    onChange={(e) => setEstimatedCost(e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Estimated hours
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.5"
                    value={estimatedHours}
                    onChange={(e) => setEstimatedHours(e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Location
                </label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="Address for the job"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notes
                </label>
                <textarea
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Additional details"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600"
                />
              </div>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Submitting…" : "Create booking"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
      <Footer />
    </div>
  );
}
