"use client";

import {
  Card,
  CardHeader,
  CardContent,
  CardTitle,
  CardDescription,
} from "../ui/card";
import { cn } from "../../lib/utils";

export interface InventoryItem {
  name: string;
  pre_pay_url: string;
  stale: boolean;
}

export interface StoreAlert {
  store_id: string;
  store_name: string;
  store_address: string;
  items: InventoryItem[];
}

export interface InventoryAlertBannerProps {
  alerts: StoreAlert[];
  onDismiss?: () => void;
}

export function InventoryAlertBanner({
  alerts,
  onDismiss,
}: InventoryAlertBannerProps) {
  if (alerts.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 w-full">
      {alerts.map((alert) => (
        <Card
          key={alert.store_id}
          className="w-full border border-blue-200 bg-blue-50 shadow-sm"
        >
          <CardHeader className="flex flex-row items-start justify-between pb-2 p-4">
            <div className="space-y-0.5 min-w-0">
              <CardTitle className="text-sm font-bold text-blue-900">
                Parts available on your route
              </CardTitle>
              <CardDescription className="text-xs text-blue-700 font-medium">
                {alert.store_name} · {alert.store_address}
              </CardDescription>
            </div>
            {onDismiss && (
              <button
                onClick={onDismiss}
                aria-label="Dismiss alert"
                className="shrink-0 ml-2 text-blue-400 hover:text-blue-700 transition-colors text-lg leading-none"
              >
                ×
              </button>
            )}
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <ul className="flex flex-col gap-2">
              {alert.items.map((item, idx) => (
                <li
                  key={idx}
                  className={cn(
                    "flex items-center justify-between rounded-md px-3 py-2 text-sm",
                    item.stale
                      ? "bg-amber-50 border border-amber-200"
                      : "bg-white border border-blue-100"
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-medium text-gray-800 truncate">
                      {item.name}
                    </span>
                    {item.stale && (
                      <span className="shrink-0 text-xs font-semibold text-amber-700 bg-amber-100 border border-amber-300 rounded px-1.5 py-0.5">
                        ⚠ Data may be outdated
                      </span>
                    )}
                  </div>
                  <a
                    href={item.pre_pay_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 ml-3 text-xs font-semibold text-blue-600 hover:text-blue-800 underline underline-offset-2 transition-colors"
                  >
                    Pre-pay →
                  </a>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
