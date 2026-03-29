import { cn } from "../../lib/utils";
import type { InventoryCheckResult } from "../../lib/api";

interface InventoryResultsPanelProps {
  results: InventoryCheckResult[];
}

export function InventoryResultsPanel({ results }: InventoryResultsPanelProps) {
  if (results.length === 0) {
    return (
      <p className="text-sm text-gray-500 py-4 text-center">
        No inventory data yet
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {results.map((result) => (
        <div
          key={result.id}
          className="border border-gray-100 rounded-lg p-4 bg-white shadow-sm"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-gray-900 truncate">
                {result.store_name}
              </p>
              {result.store_address && (
                <p className="text-xs text-gray-500 truncate">{result.store_address}</p>
              )}
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              {result.status === "stale" && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-50 text-amber-700 border border-amber-200">
                  Stale
                </span>
              )}
              <span
                className={cn(
                  "px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border",
                  result.available
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : "bg-red-50 text-red-700 border-red-200"
                )}
              >
                {result.available ? "Available" : "Unavailable"}
              </span>
            </div>
          </div>
          {result.pre_pay_url && (
            <div className="mt-3">
              <a
                href={result.pre_pay_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block text-xs font-medium text-blue-600 hover:text-blue-800 underline"
              >
                Pre-pay at {result.store_name} →
              </a>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
