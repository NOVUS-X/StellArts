'use client';

import { useCurrency } from '../../context/CurrencyContext';

interface PriceProps {
  amount: number;
  className?: string;
}

/**
 * Reusable component for displaying prices.
 * Handles automatic conversion from XLM to the user's selected currency
 * and applies localized formatting.
 */
export default function Price({ amount, className = "" }: PriceProps) {
  const { format } = useCurrency();
  
  return (
    <span className={className}>
      {format(amount)}
    </span>
  );
}
