"use client";

import * as React from "react";
import { api, type BookingResponse } from "../lib/api";
import { readActiveJobs, saveActiveJobs } from "../lib/offlineJobsCache";

const ACTIVE_STATUSES = new Set(["pending", "confirmed", "in_progress"]);

interface UseActiveJobsResult {
  jobs: BookingResponse[];
  isLoading: boolean;
  isOffline: boolean;
  lastSyncedAt: string | null;
  error: string | null;
  refetch: () => void;
}

/**
 * Fetches the artisan's active (non-terminal) bookings. On network failure
 * (e.g. no cellular signal), falls back to the last successful result cached
 * in IndexedDB so the job list stays visible offline.
 *
 * `token` is intentionally accepted as a param rather than pulled from
 * AuthContext here, since that context's shape wasn't available to wire up —
 * pass it from whichever component has access to the authenticated session.
 */
export function useActiveJobs(token: string | null): UseActiveJobsResult {
  const [jobs, setJobs] = React.useState<BookingResponse[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isOffline, setIsOffline] = React.useState(false);
  const [lastSyncedAt, setLastSyncedAt] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [refetchTick, setRefetchTick] = React.useState(0);

  React.useEffect(() => {
    if (!token) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    (async () => {
      setIsLoading(true);
      setError(null);

      try {
        const bookings = await api.bookings.myBookings(token);
        const active = bookings.filter((b) => ACTIVE_STATUSES.has(b.status));

        if (cancelled) return;

        setJobs(active);
        setIsOffline(false);
        setLastSyncedAt(new Date().toISOString());
        await saveActiveJobs(active);
      } catch (err) {
        if (cancelled) return;

        // Network (or server) failure — fall back to last cached snapshot.
        const cached = await readActiveJobs();

        if (cached) {
          setJobs(cached.jobs);
          setLastSyncedAt(cached.cachedAt);
          setIsOffline(true);
          setError(null);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load jobs");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, refetchTick]);

  const refetch = React.useCallback(() => setRefetchTick((t) => t + 1), []);

  return { jobs, isLoading, isOffline, lastSyncedAt, error, refetch };
}
