/**
 * IndexedDB-backed cache for the artisan's active jobs, used as the app-level
 * fallback when the network request in useActiveJobs fails. This is separate
 * from the Service Worker's HTTP cache — this one gives typed, structured
 * access from React without re-parsing a cached Response.
 */

import type { BookingResponse } from "./api";

const DB_NAME = "stellarts-offline";
const DB_VERSION = 1;
const STORE_NAME = "activeJobs";
const RECORD_KEY = "current";

interface CachedJobsRecord {
  jobs: BookingResponse[];
  cachedAt: string;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB not available"));
      return;
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function saveActiveJobs(jobs: BookingResponse[]): Promise<void> {
  try {
    const db = await openDb();
    const record: CachedJobsRecord = {
      jobs,
      cachedAt: new Date().toISOString(),
    };

    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      tx.objectStore(STORE_NAME).put(record, RECORD_KEY);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch (error) {
    // Non-fatal — worst case the user just doesn't get an offline fallback.
    console.warn("[offlineJobsCache] Failed to save jobs:", error);
  }
}

export async function readActiveJobs(): Promise<CachedJobsRecord | null> {
  try {
    const db = await openDb();

    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readonly");
      const request = tx.objectStore(STORE_NAME).get(RECORD_KEY);
      request.onsuccess = () => resolve(request.result ?? null);
      request.onerror = () => reject(request.error);
    });
  } catch (error) {
    console.warn("[offlineJobsCache] Failed to read jobs:", error);
    return null;
  }
}
