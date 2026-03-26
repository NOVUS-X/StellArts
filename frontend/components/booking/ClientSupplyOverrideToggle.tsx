"use client";

import { useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";

interface ClientSupplyOverrideToggleProps {
  bookingId: string;
  currentValue: boolean;
  bookingStatus: string;
  token: string;
  onToggle?: (newValue: boolean) => void;
}

const ACTIVE_STATUSES = ["pending", "confirmed"];

export function ClientSupplyOverrideToggle({
  bookingId,
  currentValue,
  bookingStatus,
  token,
  onToggle,
}: ClientSupplyOverrideToggleProps) {
  const [checked, setChecked] = useState(currentValue);
  const [loading, setLoading] = useState(false);
  const isDisabled = !ACTIVE_STATUSES.includes(bookingStatus) || loading;

  async function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const newValue = e.target.checked;
    setLoading(true);
    try {
      await api.inventory.setSupplyOverride(bookingId, newValue, token);
      setChecked(newValue);
      toast.success("Supply override updated");
      onToggle?.(newValue);
    } catch {
      toast.error("Failed to update supply override");
    } finally {
      setLoading(false);
    }
  }

  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={checked}
        disabled={isDisabled}
        onChange={handleChange}
        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
      />
      <span className={`text-sm font-medium ${isDisabled ? "text-gray-400" : "text-gray-700"}`}>
        Client will supply materials
      </span>
    </label>
  );
}
