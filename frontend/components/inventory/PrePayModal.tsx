"use client";

import { Button } from "../ui/button";

export interface PrePayItem {
  name: string;
  pre_pay_url: string;
  store_name: string;
  store_address: string;
}

export interface PrePayModalProps {
  item: PrePayItem | null;
  onClose: () => void;
}

export function PrePayModal({ item, onClose }: PrePayModalProps) {
  if (!item) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="prepay-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative w-full max-w-sm rounded-lg bg-white shadow-xl p-6 mx-4">
        {/* Close button */}
        <button
          onClick={onClose}
          aria-label="Close modal"
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-700 transition-colors text-xl leading-none"
        >
          ×
        </button>

        {/* Header */}
        <div className="mb-4">
          <p className="text-xs font-bold uppercase tracking-wider text-blue-600 mb-1">
            Pre-Pay for Part
          </p>
          <h2
            id="prepay-modal-title"
            className="text-lg font-bold text-gray-900 pr-6"
          >
            {item.name}
          </h2>
        </div>

        {/* Store info */}
        <div className="rounded-md bg-gray-50 border border-gray-100 px-4 py-3 mb-6">
          <p className="text-sm font-semibold text-gray-800">{item.store_name}</p>
          <p className="text-xs text-gray-500 mt-0.5">{item.store_address}</p>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-2">
          <Button
            asChild
            className="w-full bg-blue-600 hover:bg-blue-700 text-white"
          >
            <a
              href={item.pre_pay_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Proceed to Pre-Pay →
            </a>
          </Button>
          <Button
            variant="outline"
            className="w-full"
            onClick={onClose}
          >
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
