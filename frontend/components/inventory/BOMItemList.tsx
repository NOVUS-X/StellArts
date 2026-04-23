"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type BOMItem } from "../../lib/api";
import { useAuth } from "../../context/AuthContext";

interface BOMItemListProps {
  jobId: string;
}

export default function BOMItemList({ jobId }: BOMItemListProps) {
  const { token } = useAuth();
  const [items, setItems] = useState<BOMItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updating, setUpdating] = useState<Set<string>>(new Set());

  const fetchItems = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const data = await api.inventory.getBOMItems(jobId, token);
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load BOM items");
    } finally {
      setLoading(false);
    }
  }, [jobId, token]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  const handleToggle = async (item: BOMItem) => {
    if (!token || updating.has(item.id)) return;

    const newValue = !item.client_supplied;

    // Optimistic update
    setItems((prev: BOMItem[]) =>
      prev.map((i: BOMItem) =>
        i.id === item.id ? { ...i, client_supplied: newValue } : i
      )
    );
    setUpdating((prev: Set<string>) => new Set(prev).add(item.id));

    try {
      const updated = await api.inventory.updateSupplyOverride(
        jobId,
        item.id,
        newValue,
        token
      );
      setItems((prev: BOMItem[]) =>
        prev.map((i: BOMItem) => (i.id === updated.id ? updated : i))
      );
    } catch (err) {
      // Revert on failure
      setItems((prev: BOMItem[]) =>
        prev.map((i: BOMItem) =>
          i.id === item.id ? { ...i, client_supplied: item.client_supplied } : i
        )
      );
      setError(
        err instanceof Error ? err.message : "Failed to update supply override"
      );
    } finally {
      setUpdating((prev: Set<string>) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-500">
        Loading BOM items…
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4">
        {error}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No BOM items found for this job.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((item: BOMItem) => (
        <div
          key={item.id}
          className="flex items-center justify-between bg-white border border-gray-100 rounded-lg p-4 shadow-sm"
        >
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-gray-900 truncate">
              {item.part_name}
            </p>
            <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
              {item.part_number && (
                <span>Part #: {item.part_number}</span>
              )}
              <span>Qty: {item.quantity}</span>
            </div>
          </div>

          <label className="flex items-center gap-2 ml-4 cursor-pointer select-none shrink-0">
            <span className="text-sm text-gray-600 font-medium">
              Client will supply
            </span>
            <input
              type="checkbox"
              checked={item.client_supplied}
              onChange={() => handleToggle(item)}
              disabled={updating.has(item.id)}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:opacity-50 cursor-pointer"
            />
          </label>
        </div>
      ))}
    </div>
  );
}
