"use client";

import { useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ArtisanCounts {
    plumbers: number;
    electricians: number;
    carpenters: number;
    painters: number;
}

export interface PlatformStats {
    artisan_count: number;
    completed_bookings: number;
    average_rating: number | null;
}

export interface UseArtisanCountsResult {
    counts: ArtisanCounts | null;
    loading: boolean;
    error: boolean;
}

export interface UsePlatformStatsResult {
    stats: PlatformStats | null;
    loading: boolean;
    error: boolean;
}


const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export function formatCount(n: number | null | undefined, fallback: string): string {
    if (n == null) return fallback;
    if (n === 0) return "Coming soon";
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K+ available`;
    return `${n} available`;
}

export function useArtisanCounts(): UseArtisanCountsResult {
    const [counts, setCounts] = useState<ArtisanCounts | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
        let cancelled = false;

        fetch(`${BASE_URL}/api/v1/artisans/counts`)
            .then((res) => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json() as Promise<ArtisanCounts>;
            })
            .then((data) => {
                if (!cancelled) {
                    setCounts(data);
                    setLoading(false);
                }
            })
            .catch(() => {
                if (!cancelled) {
                    setError(true);
                    setLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, []);

    return { counts, loading, error };
}

export function usePlatformStats(): UsePlatformStatsResult {
    const [stats, setStats] = useState<PlatformStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
        let cancelled = false;

        fetch(`${BASE_URL}/api/v1/stats`)
            .then((res) => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json() as Promise<PlatformStats>;
            })
            .then((data) => {
                if (!cancelled) {
                    setStats(data);
                    setLoading(false);
                }
            })
            .catch(() => {
                if (!cancelled) {
                    setError(true);
                    setLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, []);

    return { stats, loading, error };
}