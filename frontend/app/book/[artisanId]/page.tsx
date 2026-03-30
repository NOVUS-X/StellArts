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
import { Wrench, MapPin, Star, CheckCircle } from "lucide-react";

export default function BookArtisanPage() {
  const params = useParams();
  const router = useRouter();
  const { token, isAuthenticated } = useAuth();
  const artisanId = Number(params.artisanId);
  const [profile, setProfile] = useState<ArtisanProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successBookingId, setSuccessBookingId] = useState<string | null>(null);

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

  // Auto-calculate expected cost based on artisan's hourly rate
  useEffect(() => {
    if (profile?.rate && estimatedHours) {
      const hours = parseFloat(estimatedHours);
      if (!Number.isNaN(hours) && hours > 0) {
        setEstimatedCost((profile.rate * hours).toFixed(2));
      } else {
        setEstimatedCost("");
      }
    }
  }, [profile?.rate, estimatedHours]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !profile) return;
    setError("");

    // Validate date is in the future
    const selectedDate = new Date(date);
    if (selectedDate <= new Date()) {
       setError("Booking date must be in the future.");
       return;
    }

    setSubmitting(true);
    try {
      const body: BookingCreate = {
        artisan_id: artisanId,
        service: service.trim() || "Service request",
        date: selectedDate.toISOString(),
        estimated_cost: parseFloat(estimatedCost) || 0,
        estimated_hours: estimatedHours ? parseFloat(estimatedHours) : undefined,
        location: location.trim() || undefined,
        notes: notes.trim() || undefined,
      };
      const res = await api.bookings.create(body, token);
      setSuccessBookingId(res.id);
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
          <p className="text-gray-500 animate-pulse">Loading booking details…</p>
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

  if (successBookingId) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="pt-24 pb-16 px-4 max-w-lg mx-auto text-center">
          <Card className="border-green-200">
            <CardContent className="pt-8 pb-8 flex flex-col items-center">
               <CheckCircle className="w-16 h-16 text-green-500 mb-4" />
               <h2 className="text-3xl font-bold text-gray-900 mb-2">Booking Confirmed!</h2>
               <p className="text-gray-600 mb-6">
                 Your request has been sent to {profile?.name}. They will review your booking soon.
               </p>
               <div className="bg-green-50 text-green-800 border border-green-200 px-6 py-4 rounded-lg mb-8 w-full">
                 <p className="text-sm uppercase tracking-wide font-semibold mb-1 opacity-80">Booking ID</p>
                 <p className="font-mono text-xl">{successBookingId}</p>
               </div>
               <div className="flex gap-4">
                 <Button onClick={() => router.push("/dashboard/bookings")} className="bg-blue-600 hover:bg-blue-700">
                   View Bookings
                 </Button>
                 <Button variant="outline" onClick={() => router.push("/artisans")}>
                   Explore Artisans
                 </Button>
               </div>
            </CardContent>
          </Card>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="pt-24 pb-16 px-4 max-w-2xl mx-auto">
        <Link
          href={profile ? `/artisans/${artisanId}` : "/artisans"}
          className="inline-flex items-center text-gray-500 hover:text-blue-600 mb-6 font-medium"
        >
          ← Back to Profile
        </Link>
        
        {/* Artisan Summary Card */}
        {profile && (
          <Card className="mb-8 border-gray-200 shadow-sm">
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="w-16 h-16 rounded-full bg-blue-50 flex items-center justify-center shrink-0 border border-blue-100">
                  <Wrench className="w-8 h-8 text-blue-600" />
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className="text-xl font-bold text-gray-900 truncate">
                    {profile.name || "Artisan"}
                  </h2>
                  <p className="text-gray-600 mt-0.5">{profile.specialty}</p>
                  <p className="text-sm text-gray-500 flex items-center gap-1.5 mt-1.5">
                    <MapPin className="w-4 h-4" />
                    <span className="truncate">{profile.location || "Location undefined"}</span>
                  </p>
                  <div className="flex items-center gap-4 mt-3">
                    {profile.average_rating != null && (
                      <span className="flex items-center gap-1.5 text-amber-600 font-medium text-sm">
                        <Star className="w-4 h-4 fill-amber-500 text-amber-500" />
                        {Number(profile.average_rating).toFixed(1)}
                      </span>
                    )}
                    {profile.rate != null && (
                      <span className="font-semibold text-gray-700 bg-gray-100 px-2 py-1 rounded text-sm">
                        ${Number(profile.rate).toFixed(0)}/hr
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <Card className="shadow-lg border-gray-200">
          <CardHeader className="border-b bg-white rounded-t-lg">
            <CardTitle>Request a Service</CardTitle>
            <CardDescription>
              Fill out the details below to request a booking from this artisan. 
              {profile?.rate && " The cost will be automatically estimated based on their hourly rate."}
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <p className="text-sm font-medium text-red-600 bg-red-50 p-4 rounded-lg border border-red-100">
                  {error}
                </p>
              )}
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Service description <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={service}
                  onChange={(e) => setService(e.target.value)}
                  placeholder="e.g. Plumbing repair for kitchen sink"
                  className="w-full rounded-md border border-gray-300 px-4 py-2.5 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-colors"
                />
              </div>
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Date & time <span className="text-red-500">*</span>
                </label>
                <input
                  type="datetime-local"
                  required
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-4 py-2.5 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-colors"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                    Estimated hours <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    min="0.5"
                    step="0.5"
                    required
                    value={estimatedHours}
                    onChange={(e) => setEstimatedHours(e.target.value)}
                    placeholder="e.g. 2.5"
                    className="w-full rounded-md border border-gray-300 px-4 py-2.5 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                    Estimated cost (USD) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    required
                    min="0"
                    step="0.01"
                    value={estimatedCost}
                    onChange={(e) => setEstimatedCost(e.target.value)}
                    readOnly={!!profile?.rate} // Readonly if rate is available to auto-calc
                    className={`w-full rounded-md border border-gray-300 px-4 py-2.5 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-colors ${profile?.rate ? "bg-gray-100 text-gray-500 cursor-not-allowed" : ""}`}
                    placeholder={profile?.rate ? "Auto-calculated" : "0.00"}
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Location <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="Address where the work is needed"
                  className="w-full rounded-md border border-gray-300 px-4 py-2.5 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-colors"
                />
              </div>
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Additional Notes
                </label>
                <textarea
                  rows={4}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Any specific details, access instructions, or tools needed"
                  className="w-full rounded-md border border-gray-300 px-4 py-2.5 text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-colors resize-y"
                />
              </div>
              
              <div className="pt-4">
                <Button type="submit" size="lg" className="w-full bg-blue-600 hover:bg-blue-700 text-lg shadow-md font-semibold" disabled={submitting}>
                  {submitting ? "Submitting Booking…" : "Confirm & Send Request"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </main>
      <Footer />
    </div>
  );
}
