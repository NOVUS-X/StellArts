"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Navbar from "../../components/ui/Navbar";
import Footer from "../../components/ui/Footer";
import { Button } from "../../components/ui/button";
import {
  Card,
  CardContent,
} from "../../components/ui/card";
import { api, type ArtisanItem } from "../../lib/api";
import { Wrench, MapPin, Star } from "lucide-react";

const DEFAULT_LAT = 51.5074;
const DEFAULT_LON = -0.1278;

export default function ArtisansPage() {
  const [artisans, setArtisans] = useState<ArtisanItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lat, setLat] = useState(DEFAULT_LAT);
  const [lon, setLon] = useState(DEFAULT_LON);
  const [page, setPage] = useState(1);
  const pageSize = 10;

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setLat(pos.coords.latitude);
          setLon(pos.coords.longitude);
        },
        () => {}
      );
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    setError("");
    api.artisans
      .nearby(lat, lon, { page, page_size: pageSize })
      .then((res) => {
        setArtisans(res.items);
        setTotal(res.total);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load artisans"))
      .finally(() => setLoading(false));
  }, [lat, lon, page]);

  const specialtyStr = (a: ArtisanItem) => {
    const s = a.specialties;
    if (Array.isArray(s)) return s[0] ?? "Artisan";
    if (typeof s === "string") return s;
    return "Artisan";
  };

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="pt-24 pb-16 px-4 max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Find an Artisan
        </h1>
        <p className="text-gray-600 mb-8">
          Artisans near you (using your location or default).
        </p>

        {error && (
          <p className="text-red-600 bg-red-50 p-4 rounded-lg mb-6">{error}</p>
        )}

        {loading ? (
          <p className="text-gray-500">Loading…</p>
        ) : (
          <>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {artisans.map((a) => (
                <Link key={a.id} href={`/artisans/${a.id}`}>
                  <Card className="hover:shadow-lg transition-shadow h-full">
                    <CardContent className="p-5">
                      <div className="flex items-start gap-3">
                        <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
                          <Wrench className="w-6 h-6 text-blue-600" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <h2 className="font-semibold text-gray-900 truncate">
                            {a.business_name || specialtyStr(a)}
                          </h2>
                          <p className="text-sm text-gray-500 flex items-center gap-1 mt-0.5">
                            <MapPin className="w-3.5 h-3.5" />
                            {a.location || "Location not set"}
                          </p>
                          {a.rating != null && (
                            <p className="text-sm text-amber-600 flex items-center gap-1 mt-1">
                              <Star className="w-3.5 h-3.5 fill-current" />
                              {Number(a.rating).toFixed(1)}
                            </p>
                          )}
                          {a.hourly_rate != null && (
                            <p className="text-sm font-medium text-gray-700 mt-1">
                              ${Number(a.hourly_rate).toFixed(0)}/hr
                            </p>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
            {total > pageSize && (
              <div className="flex justify-center gap-2 mt-8">
                <Button
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </Button>
                <span className="flex items-center px-4 text-gray-600">
                  Page {page} of {Math.ceil(total / pageSize)}
                </span>
                <Button
                  variant="outline"
                  disabled={page >= Math.ceil(total / pageSize)}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </main>
      <Footer />
    </div>
  );
}
