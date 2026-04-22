'use client';

import { useCurrency, Currency } from '../../context/CurrencyContext';
import { Globe } from 'lucide-react';

export default function CurrencySelector() {
  const { currency, setCurrency } = useCurrency();

  return (
    <div className="flex items-center gap-2 bg-white/50 backdrop-blur-sm border border-gray-200 hover:border-blue-300 rounded-full px-3 py-1.5 transition-all shadow-sm group">
      <Globe className="w-3.5 h-3.5 text-blue-500 group-hover:scale-110 transition-transform" />
      <select
        value={currency}
        onChange={(e) => setCurrency(e.target.value as Currency)}
        className="bg-transparent text-xs font-bold text-gray-700 outline-none cursor-pointer appearance-none uppercase tracking-wider"
      >
        <option value="XLM">XLM</option>
        <option value="USD">USD</option>
        <option value="EUR">EUR</option>
        <option value="GBP">GBP</option>
        <option value="NGN">NGN</option>
      </select>
      <div className="w-1.5 h-1.5 border-r-2 border-b-2 border-gray-400 rotate-45 -translate-y-0.5 ml-0.5 pointer-events-none"></div>
    </div>
  );
}
