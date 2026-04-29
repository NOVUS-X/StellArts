"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Navbar from "../../components/ui/Navbar";
import Footer from "../../components/ui/Footer";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { api, type ArtisanItem } from "../../lib/api";
import { Wrench, MapPin, Star, Sparkles } from "lucide-react";
import Price from "../../components/ui/Price";

const DEFAULT_LAT = 51.5074;
const DEFAULT_LON = -0.1278;

function specialtyLabel(artisan: ArtisanItem) {
  const s = artisan.specialties;
  if (Array.isArray(s)) return s[0] ?? "Artisan";
  if (typeof s === "string") return s;
  return "Artisan";
}

export default function ArtisansPage() {
  const [artisans, setArtisans] = useState<ArtisanItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [lat, setLat] = useState<number | null>(null);
  const [lon, setLon] = useState<number | null>(null);

  const [page, setPage] = useState(1);
  const pageSize = 12;

  // Filters
  const [specialties, setSpecialties] = useState<string[]>([]);
  const [minRating, setMinRating] = useState(0);
  const [maxPrice, setMaxPrice] = useState<number | "">("");
  const [minExperience, setMinExperience] = useState<number | "">("");
  const [isAvailable, setIsAvailable] = useState(false);

  const [debouncedFilters, setDebouncedFilters] = useState({
    specialties,
    minRating,
    maxPrice,
    minExperience,
    isAvailable,
  });

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedFilters({
        specialties,
        minRating,
        maxPrice,
        minExperience,
        isAvailable,
      });
      setPage(1);
    }, 500);
    return () => clearTimeout(handler);
  }, [specialties, minRating, maxPrice, minExperience, isAvailable]);

  useEffect(() => {
    if (!navigator.geolocation) {
      setLat(DEFAULT_LAT);
      setLon(DEFAULT_LON);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude);
        setLon(pos.coords.longitude);
      },
      () => {
        setLat(DEFAULT_LAT);
        setLon(DEFAULT_LON);
      }
    );
  }, []);

  useEffect(() => {
    if (lat === null || lon === null) return;

    setLoading(true);
    setError("");

    api.artisans
      .nearby(lat, lon, {
        page,
        page_size: pageSize,
        specialties: debouncedFilters.specialties.length
          ? debouncedFilters.specialties
          : undefined,
        min_rating: debouncedFilters.minRating || undefined,
        max_price:
          debouncedFilters.maxPrice !== ""
            ? Number(debouncedFilters.maxPrice)
            : undefined,
        min_experience:
          debouncedFilters.minExperience !== ""
            ? Number(debouncedFilters.minExperience)
            : undefined,
        is_available: debouncedFilters.isAvailable || undefined,
      })
      .then((res) => {
        setArtisans(res.items);
        setTotal(res.total);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load artisans");
      })
      .finally(() => setLoading(false));
  }, [lat, lon, page, debouncedFilters]);

  const clearFilters = () => {
    setSpecialties([]);
    setMinRating(0);
    setMaxPrice("");
    setMinExperience("");
    setIsAvailable(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="pt-24 pb-16 px-4 max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">Find an Artisan</h1>
        <p className="text-gray-600 mb-8">Artisans near you ready to help.</p>

        <div className="flex flex-col md:flex-row gap-8 items-start">
          
          {/* Sidebar */}
          <aside className="w-full md:w-72 shrink-0 bg-white p-6 rounded-xl border">
            <h2 className="font-bold mb-4">Filters</h2>

            {/* Specialties */}
            <div className="mb-6">
              <p className="text-sm font-semibold mb-2">Specialties</p>
              {["Plumber", "Electrician", "Carpenter", "Painter", "Mechanic"].map((s) => (
                <label key={s} className="block text-sm">
                  <input
                    type="checkbox"
                    checked={specialties.includes(s)}
                    onChange={(e) =>
                      e.target.checked
                        ? setSpecialties([...specialties, s])
                        : setSpecialties(specialties.filter((x) => x !== s))
                    }
                  />{" "}
                  {s}
                </label>
              ))}
            </div>

            {/* Rating */}
            <div className="mb-6">
              <p className="text-sm font-semibold">Min Rating: {minRating}</p>
              <input
                type="range"
                min="0"
                max="5"
                value={minRating}
                onChange={(e) => setMinRating(Number(e.target.value))}
              />
            </div>

            {/* Price */}
            <div className="mb-6">
              <p className="text-sm font-semibold">Max Price</p>
              <input
                type="number"
                value={maxPrice}
                onChange={(e) =>
                  setMaxPrice(e.target.value ? Number(e.target.value) : "")
                }
                className="w-full border p-2"
              />
            </div>

            {/* Experience */}
            <div className="mb-6">
              <p className="text-sm font-semibold">Min Experience</p>
              <input
                type="number"
                value={minExperience}
                onChange={(e) =>
                  setMinExperience(e.target.value ? Number(e.target.value) : "")
                }
                className="w-full border p-2"
              />
            </div>

            {/* Availability */}
            <label className="block mb-4">
              <input
                type="checkbox"
                checked={isAvailable}
                onChange={(e) => setIsAvailable(e.target.checked)}
              />{" "}
              Available Now
            </label>

            <Button onClick={clearFilters} variant="outline">
              Clear Filters
            </Button>
          </aside>

          {/* Main Content */}
          <div className="flex-1">
            {error && <p className="text-red-500 mb-4">{error}</p>}

            {loading ? (
              <p>Loading...</p>
            ) : artisans.length === 0 ? (
              <div className="text-center py-10">
                <Sparkles className="mx-auto mb-2" />
                <p>No artisans found</p>
                <Button onClick={clearFilters}>Clear Filters</Button>
              </div>
            ) : (
              <>
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {artisans.map((a) => (
                    <Link key={a.id} href={`/artisans/${a.id}`}>
                      <Card>
                        <CardContent className="p-4">
                          <h2 className="font-semibold">
                            {a.business_name || specialtyLabel(a)}
                          </h2>

                          <p className="text-sm text-gray-500 flex items-center gap-1">
                            <MapPin size={14} /> {a.location}
                          </p>

                          {a.rating && (
                            <p className="text-sm flex items-center gap-1">
                              <Star size={14} /> {a.rating}
                            </p>
                          )}

                          {a.hourly_rate && (
                            <p className="font-semibold">
                              <Price amount={Number(a.hourly_rate)} /> /hr
                            </p>
                          )}
                        </CardContent>
                      </Card>
                    </Link>
                  ))}
                </div>

                {/* Pagination */}
                {total > pageSize && (
                  <div className="flex justify-center gap-4 mt-8">
                    <Button disabled={page <= 1} onClick={() => setPage(page - 1)}>
                      Prev
                    </Button>
                    <span>
                      {page} / {Math.ceil(total / pageSize)}
                    </span>
                    <Button
                      disabled={page >= Math.ceil(total / pageSize)}
                      onClick={() => setPage(page + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
