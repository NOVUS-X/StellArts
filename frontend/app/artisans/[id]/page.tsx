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
} from "../../../components/ui/card";
import { api, type ArtisanProfileResponse } from "../../../lib/api";
import { useAuth } from "../../../context/AuthContext";
import { ArrowLeft, MapPin, Star, Wrench } from "lucide-react";

export default function ArtisanProfilePage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const id = Number(params.id);
  const [profile, setProfile] = useState<ArtisanProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (Number.isNaN(id)) {
      setError("Invalid artisan");
      setLoading(false);
      return;
    }
    api.artisans
      .getProfile(id)
      .then(setProfile)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load profile")
      )
      .finally(() => setLoading(false));
  }, [id]);

  function handleBookNow() {
    if (!isAuthenticated) {
      router.push(`/login?redirect=/book/${id}`);
      return;
    }
    router.push(`/book/${id}`);
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-white">
        <Navbar />
        <main className="pt-24 pb-16 px-4 max-w-3xl mx-auto">
          <p className="text-gray-500">Loading profile…</p>
        </main>
        <Footer />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="min-h-screen bg-white">
        <Navbar />
        <main className="pt-24 pb-16 px-4 max-w-3xl mx-auto">
          <p className="text-red-600">{error || "Artisan not found"}</p>
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
      <main className="pt-24 pb-16 px-4 max-w-3xl mx-auto">
        <Link
          href="/artisans"
          className="inline-flex items-center text-gray-600 hover:text-blue-600 mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to artisans
        </Link>

        <Card>
          <CardContent className="p-8">
            <div className="flex items-start gap-6">
              <div className="w-20 h-20 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
                <Wrench className="w-10 h-10 text-blue-600" />
              </div>
              <div className="min-w-0 flex-1">
                <h1 className="text-2xl font-bold text-gray-900">
                  {profile.name || "Artisan"}
                </h1>
                {profile.specialty && (
                  <p className="text-gray-600 mt-1">{profile.specialty}</p>
                )}
                {profile.location && (
                  <p className="text-sm text-gray-500 flex items-center gap-1 mt-2">
                    <MapPin className="w-4 h-4" />
                    {profile.location}
                  </p>
                )}
                <div className="flex items-center gap-4 mt-3">
                  {profile.average_rating != null && (
                    <span className="flex items-center gap-1 text-amber-600">
                      <Star className="w-4 h-4 fill-current" />
                      {Number(profile.average_rating).toFixed(1)}
                    </span>
                  )}
                  {profile.rate != null && (
                    <span className="font-semibold text-gray-900">
                      ${Number(profile.rate).toFixed(0)}/hr
                    </span>
                  )}
                </div>
              </div>
            </div>
            {profile.bio && (
              <div className="mt-6 pt-6 border-t border-gray-200">
                <h2 className="font-semibold text-gray-900 mb-2">About</h2>
                <p className="text-gray-600">{profile.bio}</p>
              </div>
            )}
            {profile.portfolio && profile.portfolio.length > 0 && (
              <div className="mt-6 pt-6 border-t border-gray-200">
                <h2 className="font-semibold text-gray-900 mb-2">Portfolio</h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  {profile.portfolio.map((item) => (
                    <div
                      key={item.id}
                      className="aspect-square bg-gray-100 rounded-lg overflow-hidden"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={item.image}
                        alt={item.title || "Portfolio"}
                        className="w-full h-full object-cover"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="mt-8 pt-6 border-t border-gray-200">
              <Button
                size="lg"
                className="bg-blue-600 hover:bg-blue-700"
                onClick={handleBookNow}
              >
                Book Now
              </Button>
            </div>
          </CardContent>
        </Card>
      </main>
      <Footer />
    </div>
  );
}
