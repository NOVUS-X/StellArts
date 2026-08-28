"use client";

interface OfflineBannerProps {
  isOffline: boolean;
  lastSyncedAt: string | null;
}

export function OfflineBanner({ isOffline, lastSyncedAt }: OfflineBannerProps) {
  if (!isOffline) return null;

  const syncedLabel = lastSyncedAt
    ? new Date(lastSyncedAt).toLocaleString()
    : "an earlier session";

  return (
    <div
      role="status"
      className="w-full rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200"
    >
      You&rsquo;re offline — showing jobs last synced {syncedLabel}.
    </div>
  );
}
