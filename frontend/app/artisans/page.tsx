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

function ArtisanSkeleton() {
  return (
    <Card className="h-full">
      <CardContent className="p-5">
        <div className="flex items-start gap-3 animate-pulse">
          <div className="w-12 h-12 rounded-full bg-gray-200 shrink-0" />
          <div className="min-w-0 flex-1 space-y-2 py-1">
            <div className="h-4 bg-gray-200 rounded w-3/4" />
            <div className="h-3 bg-gray-200 rounded w-1/2" />
            <div className="h-3 bg-gray-200 rounded w-1/4" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
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
  const [skill, setSkill] = useState("");
  const [minRating, setMinRating] = useState<number>(0);
  const [isAvailable, setIsAvailable] = useState<boolean>(false);

  // Debounced filters
  const [debouncedFilters, setDebouncedFilters] = useState({ skill, minRating, isAvailable });

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedFilters({ skill, minRating, isAvailable });
      setPage(1); // reset to page 1 on filter
    }, 500);
    return () => clearTimeout(handler);
  }, [skill, minRating, isAvailable]);

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
        skill: debouncedFilters.skill || undefined,
        min_rating: debouncedFilters.minRating || undefined,
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
    setSkill("");
    setMinRating(0);
    setIsAvailable(false);
  };

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
          Artisans near you ready to help.
        </p>

        {locationStatus === "denied" && (
           <div className="bg-amber-50 text-amber-800 p-4 rounded-lg mb-6 flex flex-wrap gap-4 justify-between items-center">
              <p>Location access denied. Displaying results for default location.</p>
              <Button variant="outline" size="sm" onClick={requestLocation}>Retry Location</Button>
           </div>
        )}

        {/* Filter Bar */}
        <div className="bg-gray-50 p-6 rounded-xl mb-8 flex flex-col md:flex-row gap-6 items-end">
          <div className="flex-1 w-full min-w-[200px]">
             <label className="block text-sm font-medium text-gray-700 mb-1">Specialty</label>
             <select 
               value={skill} 
               onChange={(e) => setSkill(e.target.value)}
               className="w-full rounded-md border border-gray-300 px-3 py-2.5 text-gray-900 focus:border-blue-600 focus:outline-none bg-white"
             >
               <option value="">Any Specialty</option>
               <option value="Plumber">Plumber</option>
               <option value="Electrician">Electrician</option>
               <option value="Carpenter">Carpenter</option>
               <option value="Painter">Painter</option>
               <option value="Mechanic">Mechanic</option>
             </select>
          </div>
          <div className="flex-1 w-full min-w-[200px]">
             <label className="block text-sm font-medium text-gray-700 mb-3 block">
               Min Rating ({minRating} Stars)
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
          <div className="flex items-center gap-3 w-full md:w-auto h-10">
             <input 
               type="checkbox"
               id="availableNow"
               checked={isAvailable}
               onChange={(e) => setIsAvailable(e.target.checked)}
               className="w-5 h-5 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
             />
             <label htmlFor="availableNow" className="text-sm font-medium text-gray-700 select-none cursor-pointer">
               Available Now
             </label>
          </div>
        </div>

        {error && (
          <p className="text-red-600 bg-red-50 p-4 rounded-lg mb-6">{error}</p>
        )}

        {loading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <ArtisanSkeleton key={i} />
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
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {artisans.map((a) => (
                <Link key={a.id} href={`/artisans/${a.id}`}>
                  <Card className="hover:shadow-lg transition-shadow h-full border hover:border-blue-200">
                    <CardContent className="p-5">
                      <div className="flex items-start gap-4">
                        <div className="w-14 h-14 rounded-full bg-blue-50 flex items-center justify-center shrink-0 border border-blue-100">
                          <Wrench className="w-6 h-6 text-blue-600" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <h2 className="font-semibold text-gray-900 truncate">
                            {a.business_name || specialtyStr(a)}
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
                    </CardContent>
                  </Card>
                </Link>
              ))}
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
      </main>
      <Footer />
    </div>
  );
}
