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
import { Wrench, MapPin, Star, Sparkles } from "lucide-react";
import Price from "../../components/ui/Price";

const DEFAULT_LAT = 51.5074;
const DEFAULT_LON = -0.1278;

function SkeletonBlock({
  className,
}: {
  className: string;
}) {
  return <div className={`skeleton-shimmer rounded-full ${className}`} aria-hidden="true" />;
}

function ArtisanSkeletonCard() {
  return (
    <Card className="h-full overflow-hidden border-gray-200 bg-white/90 shadow-sm">
      <CardContent className="p-5">
        <div className="space-y-4">
          <div className="flex items-start gap-4">
            <div className="skeleton-shimmer h-14 w-14 shrink-0 rounded-2xl" />
            <div className="min-w-0 flex-1 space-y-2.5 pt-1">
              <SkeletonBlock className="h-4 w-2/3 rounded-md" />
              <SkeletonBlock className="h-3 w-1/2 rounded-md" />
              <SkeletonBlock className="h-3 w-1/3 rounded-md" />
            </div>
          </div>
          <div className="space-y-3">
            <SkeletonBlock className="h-3 w-full rounded-md" />
            <SkeletonBlock className="h-3 w-5/6 rounded-md" />
          </div>
          <div className="flex items-center justify-between pt-2">
            <SkeletonBlock className="h-5 w-20 rounded-full" />
            <SkeletonBlock className="h-5 w-16 rounded-full" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function MapSkeleton() {
  return (
    <Card className="overflow-hidden border-blue-100 bg-white shadow-sm">
      <CardContent className="p-0">
        <div className="relative h-[320px] overflow-hidden bg-[linear-gradient(135deg,#eff6ff_0%,#dbeafe_45%,#f8fafc_100%)]">
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.55)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.55)_1px,transparent_1px)] bg-[size:48px_48px]" />
          <div className="absolute inset-0 skeleton-wave opacity-70" />
          <div className="absolute left-6 top-6 w-[calc(100%-3rem)] rounded-2xl bg-white/80 p-4 shadow-sm backdrop-blur-sm">
            <SkeletonBlock className="mb-3 h-4 w-28 rounded-md" />
            <SkeletonBlock className="h-3 w-40 rounded-md" />
          </div>
          <div className="absolute left-[18%] top-[36%] h-4 w-4 rounded-full bg-white/70 shadow-[0_0_0_6px_rgba(255,255,255,0.35)]" />
          <div className="absolute left-[46%] top-[52%] h-5 w-5 rounded-full bg-white/80 shadow-[0_0_0_8px_rgba(255,255,255,0.32)]" />
          <div className="absolute left-[68%] top-[30%] h-3.5 w-3.5 rounded-full bg-white/70 shadow-[0_0_0_6px_rgba(255,255,255,0.3)]" />
          <div className="absolute bottom-6 left-6 right-6 grid grid-cols-3 gap-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="rounded-xl bg-white/75 p-3 shadow-sm backdrop-blur-sm">
                <SkeletonBlock className="mb-2 h-3 w-16 rounded-md" />
                <SkeletonBlock className="h-3 w-12 rounded-md" />
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ArtisanMapPanel({
  artisans,
  loading,
  hasResults,
}: {
  artisans: ArtisanItem[];
  loading: boolean;
  hasResults: boolean;
}) {
  if (loading && !hasResults) {
    return <MapSkeleton />;
  }

  const mappedArtisans = artisans
    .filter((artisan) => artisan.latitude != null && artisan.longitude != null)
    .slice(0, 6);

  return (
    <Card className="overflow-hidden border-blue-100 bg-white shadow-sm">
      <CardContent className="p-0">
        <div className="relative h-[320px] overflow-hidden bg-[linear-gradient(145deg,#eff6ff_0%,#dbeafe_42%,#f8fafc_100%)]">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.18),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(14,165,233,0.14),transparent_30%)]" />
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.52)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.52)_1px,transparent_1px)] bg-[size:48px_48px]" />
          <div className="absolute left-6 top-6 z-10 max-w-[calc(100%-3rem)] rounded-2xl bg-white/88 px-4 py-3 shadow-sm backdrop-blur-sm">
            <p className="text-sm font-semibold text-gray-900">Nearby map view</p>
            <p className="mt-1 text-sm text-gray-500">
              {artisans.length > 0
                ? `${artisans.length} artisan${artisans.length === 1 ? "" : "s"} in this search`
                : "No mappable artisans yet"}
            </p>
          </div>

          <div className="absolute inset-x-0 bottom-0 top-0">
            {mappedArtisans.length > 0 ? (
              mappedArtisans.map((artisan, index) => {
                const x = 18 + (index % 3) * 24 + (index % 2) * 5;
                const y = 26 + Math.floor(index / 3) * 28 + (index % 2) * 8;
                return (
                  <div
                    key={artisan.id}
                    className="absolute -translate-x-1/2 -translate-y-1/2 transition-all duration-500"
                    style={{ left: `${x}%`, top: `${y}%` }}
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-full border-4 border-white bg-blue-600 text-white shadow-lg shadow-blue-200/80">
                      <Wrench className="h-4 w-4" />
                    </div>
                    <div className="mt-2 min-w-28 rounded-xl bg-white/90 px-3 py-2 text-xs font-medium text-gray-700 shadow-sm backdrop-blur-sm">
                      <p className="truncate">{artisan.business_name || "Artisan"}</p>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
                <div className="rounded-2xl bg-white/88 px-5 py-4 shadow-sm backdrop-blur-sm">
                  <p className="text-sm font-semibold text-gray-900">Map coordinates unavailable</p>
                  <p className="mt-1 text-sm text-gray-500">
                    Results still load below while location details catch up.
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="absolute bottom-4 left-4 right-4 z-10">
            <div className="grid grid-cols-3 gap-3">
              {artisans.slice(0, 3).map((artisan) => (
                <div key={artisan.id} className="rounded-xl bg-white/85 px-3 py-2 shadow-sm backdrop-blur-sm">
                  <p className="truncate text-xs font-semibold text-gray-900">
                    {artisan.business_name || specialtyLabel(artisan)}
                  </p>
                  <p className="mt-1 truncate text-xs text-gray-500">
                    {artisan.location || "Location pending"}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {loading && (
            <div className="absolute inset-0 z-20 bg-white/45 backdrop-blur-[2px] transition-opacity duration-300">
              <div className="absolute inset-0 skeleton-wave opacity-70" />
              <div className="absolute right-4 top-4 rounded-full bg-white/90 px-3 py-1 text-xs font-medium text-gray-700 shadow-sm">
                Refreshing results...
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

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
  const [locationStatus, setLocationStatus] = useState<"pending" | "granted" | "denied">("pending");

  const [page, setPage] = useState(1);
  const pageSize = 12;

  // Filters
  const [specialties, setSpecialties] = useState<string[]>([]);
  const [minRating, setMinRating] = useState<number>(0);
  const [maxPrice, setMaxPrice] = useState<number | "">("");
  const [minExperience, setMinExperience] = useState<number | "">("");
  const [isAvailable, setIsAvailable] = useState<boolean>(false);

  // Debounced filters
  const [debouncedFilters, setDebouncedFilters] = useState({ specialties, minRating, maxPrice, minExperience, isAvailable });

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedFilters({ specialties, minRating, maxPrice, minExperience, isAvailable });
      setPage(1); // reset to page 1 on filter
    }, 500);
    return () => clearTimeout(handler);
  }, [specialties, minRating, maxPrice, minExperience, isAvailable]);

  const requestLocation = () => {
    if (typeof window === "undefined" || !navigator.geolocation) {
       setLocationStatus("denied");
       setLat(DEFAULT_LAT);
       setLon(DEFAULT_LON);
       return;
    }
    setLocationStatus("pending");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude);
        setLon(pos.coords.longitude);
        setLocationStatus("granted");
      },
      () => {
        setLat(DEFAULT_LAT);
        setLon(DEFAULT_LON);
        setLocationStatus("denied");
      }
    );
  };

  useEffect(() => {
    requestLocation();
  }, []);

  useEffect(() => {
    if (lat === null || lon === null) return;
    let isMounted = true;
    setLoading(true);
    setError("");

    api.artisans
      .nearby(lat, lon, { 
        page, 
        page_size: pageSize,
        specialties: debouncedFilters.specialties.length > 0 ? debouncedFilters.specialties : undefined,
        min_rating: debouncedFilters.minRating || undefined,
        max_price: debouncedFilters.maxPrice !== "" ? Number(debouncedFilters.maxPrice) : undefined,
        min_experience: debouncedFilters.minExperience !== "" ? Number(debouncedFilters.minExperience) : undefined,
        is_available: debouncedFilters.isAvailable ? true : undefined,
      })
      .then((res) => {
        if (!isMounted) return;
        setArtisans(res.items);
        setTotal(res.total);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Failed to load artisans");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [lat, lon, page, debouncedFilters]);

  const clearFilters = () => {
    setSpecialties([]);
    setMinRating(0);
    setMaxPrice("");
    setMinExperience("");
    setIsAvailable(false);
  };

  const hasLoadedResults = artisans.length > 0 || total > 0;
  const showInitialSkeleton = loading && !hasLoadedResults && !error;

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#ffffff_0%,#f8fbff_100%)]">
      <Navbar />
      <main className="pt-24 pb-16 px-4 max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Find an Artisan
        </h1>
        <p className="text-gray-600 mb-8">
          Artisans near you ready to help.
        </p>

        {locationStatus === "denied" && (
           <div className="bg-amber-50 text-amber-800 p-4 rounded-lg mb-6 flex flex-wrap gap-4 justify-between items-center">
              <p>Location access denied. Displaying results for default location.</p>
              <Button variant="outline" size="sm" onClick={requestLocation}>Retry Location</Button>
           </div>
        )}

        {/* Filter Sidebar & Main Content Layout */}
        <div className="flex flex-col md:flex-row gap-8 items-start">
          {/* Sidebar */}
          <aside className="w-full md:w-72 shrink-0 space-y-6 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm sticky top-28">
            <div>
              <h2 className="text-lg font-bold text-gray-900 mb-4">Filters</h2>
              <div className="space-y-6">
                
                {/* Specialties */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-3">Specialties</label>
                  <div className="space-y-2.5 max-h-48 overflow-y-auto pr-2">
                    {["Plumber", "Electrician", "Carpenter", "Painter", "Mechanic"].map((spec) => (
                      <label key={spec} className="flex items-center gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={specialties.includes(spec)}
                          onChange={(e) => {
                            if (e.target.checked) setSpecialties([...specialties, spec]);
                            else setSpecialties(specialties.filter(s => s !== spec));
                          }}
                          className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-600">{spec}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Min Rating */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-3">
                    Min Rating {minRating > 0 ? `(${minRating} Stars)` : "(Any)"}
                  </label>
                  <input 
                    type="range"
                    min="0"
                    max="5"
                    step="1"
                    value={minRating}
                    onChange={(e) => setMinRating(Number(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                  />
                </div>

                {/* Max Price */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Max Hourly Rate ($)</label>
                  <input
                    type="number"
                    min="0"
                    placeholder="Any price"
                    value={maxPrice}
                    onChange={(e) => setMaxPrice(e.target.value ? Number(e.target.value) : "")}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>

                {/* Min Experience */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Min Experience (Years)</label>
                  <input
                    type="number"
                    min="0"
                    placeholder="Any experience"
                    value={minExperience}
                    onChange={(e) => setMinExperience(e.target.value ? Number(e.target.value) : "")}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>

                {/* Availability */}
                <label className="flex items-center gap-3 cursor-pointer pt-2">
                  <input 
                    type="checkbox"
                    checked={isAvailable}
                    onChange={(e) => setIsAvailable(e.target.checked)}
                    className="w-5 h-5 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm font-medium text-gray-700">Available Now</span>
                </label>
              </div>
            </div>
            
            <Button onClick={clearFilters} variant="outline" className="w-full mt-6">
              Clear Filters
            </Button>
          </aside>

          {/* Main Content */}
          <div className="flex-1 min-w-0">
            {error && (
              <p className="text-red-600 bg-red-50 p-4 rounded-lg mb-6">{error}</p>
            )}

            <section className="mb-8 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-2xl border border-blue-100 bg-white/90 p-5 shadow-sm backdrop-blur-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-600">
                      Search Results
                    </p>
                    <h2 className="mt-2 text-2xl font-semibold text-gray-900">
                      {showInitialSkeleton ? "Finding artisans near you" : `${total} artisans available`}
                    </h2>
                    <p className="mt-2 text-sm text-gray-500">
                      {loading
                        ? hasLoadedResults
                          ? "Updating the list with your latest filters."
                          : "Loading cards and map markers for this area."
                        : "Browse detailed cards while the map keeps nearby context in view."}
                    </p>
                  </div>
                  <div className="rounded-full bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700">
                    {locationStatus === "granted" ? "Live location" : "Fallback location"}
                  </div>
                </div>
              </div>
              <ArtisanMapPanel artisans={artisans} loading={loading} hasResults={hasLoadedResults} />
            </section>

            {showInitialSkeleton ? (
              <div className="grid sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                {Array.from({ length: 6 }).map((_, i) => (
                  <ArtisanSkeletonCard key={i} />
                ))}
              </div>
            ) : artisans.length === 0 ? (
              <div className="text-center py-16 bg-gray-50 rounded-xl border border-gray-100">
                 <Sparkles className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                 <h3 className="text-lg font-medium text-gray-900">No artisans found</h3>
                 <p className="text-gray-500 mt-2 mb-6">Try adjusting your filters to find what you&apos;re looking for.</p>
                 <Button onClick={clearFilters} variant="outline" className="px-6">Clear Filters</Button>
              </div>
            ) : (
              <>
                <div className="relative">
                  <div
                    className={`grid sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-6 transition-opacity duration-300 ${
                      loading ? "opacity-70" : "opacity-100"
                    }`}
                  >
                  {artisans.map((a) => (
                    <Link key={a.id} href={`/artisans/${a.id}`}>
                      <Card className="group h-full border border-gray-200 bg-white/95 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-blue-200 hover:shadow-lg">
                        <CardContent className="p-5">
                          <div className="space-y-4">
                            <div className="flex items-start gap-4">
                              <div className="w-14 h-14 rounded-2xl bg-blue-50 flex items-center justify-center shrink-0 border border-blue-100 transition-colors duration-300 group-hover:bg-blue-100">
                              <Wrench className="w-6 h-6 text-blue-600" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <h2 className="font-semibold text-gray-900 truncate">
                                {a.business_name || specialtyLabel(a)}
                              </h2>
                              <p className="text-sm text-gray-500 flex items-center gap-1.5 mt-1">
                                <MapPin className="w-3.5 h-3.5" />
                                <span className="truncate">{a.location || "Location not set"}</span>
                              </p>
                              <div className="flex items-center gap-4 mt-2">
                                {a.rating != null && (
                                  <p className="text-sm text-amber-600 flex items-center gap-1 font-medium">
                                    <Star className="w-4 h-4 fill-amber-500 text-amber-500" />
                                    {Number(a.rating).toFixed(1)}
                                  </p>
                                )}
                                {a.hourly_rate != null && (
                                  <p className="text-sm font-semibold text-gray-700">
                                    <Price amount={Number(a.hourly_rate)} />/hr
                                  </p>
                                )}
                              </div>
                            </div>
                          </div>
                            <div className="flex flex-wrap items-center gap-2 pt-1">
                              {a.is_available && (
                                <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                                  Available now
                                </span>
                              )}
                              {a.distance_km != null && (
                                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600">
                                  {Number(a.distance_km).toFixed(1)} km away
                                </span>
                              )}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </Link>
                  ))}
                  </div>
                  {loading && (
                    <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-3xl">
                      <div className="absolute inset-0 bg-white/28 backdrop-blur-[1.5px]" />
                      <div className="absolute inset-0 skeleton-wave opacity-55" />
                    </div>
                  )}
                </div>
                {total > pageSize && (
                  <div className="flex justify-center gap-3 mt-10">
                    <Button
                      variant="outline"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => p - 1)}
                      className="w-24"
                    >
                      Previous
                    </Button>
                    <div className="flex items-center px-4 py-2 bg-gray-50 rounded-md text-sm font-medium text-gray-700">
                      Page {page} of {Math.ceil(total / pageSize)}
                    </div>
                    <Button
                      variant="outline"
                      disabled={page >= Math.ceil(total / pageSize)}
                      onClick={() => setPage((p) => p + 1)}
                      className="w-24"
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
