'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

export type Currency = 'XLM' | 'USD' | 'EUR' | 'GBP' | 'NGN';

interface CurrencyContextType {
  currency: Currency;
  setCurrency: (currency: Currency) => void;
  rates: Record<string, number>;
  loading: boolean;
  convert: (amount: number) => number;
  format: (amountInXLM: number) => string;
}

const CurrencyContext = createContext<CurrencyContextType | undefined>(undefined);

const COINGECKO_URL = 'https://api.coingecko.com/api/v3/simple/price?ids=stellar&vs_currencies=usd,eur,gbp,ngn';

export const CurrencyProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currency, setCurrencyState] = useState<Currency>('XLM');
  const [rates, setRates] = useState<Record<string, number>>({ XLM: 1 });
  const [loading, setLoading] = useState(true);

  const fetchRates = useCallback(async () => {
    try {
      const response = await fetch(COINGECKO_URL);
      const data = await response.json();
      if (data.stellar) {
        setRates({
          XLM: 1,
          USD: data.stellar.usd,
          EUR: data.stellar.eur,
          GBP: data.stellar.gbp,
          NGN: data.stellar.ngn,
        });
      }
    } catch (error) {
      console.error('Failed to fetch rates:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Load preference from local storage
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('stellarts_currency');
      if (saved) {
        setCurrencyState(saved as Currency);
      }
    }
    
    fetchRates();
    const interval = setInterval(fetchRates, 5 * 60 * 1000); // Update every 5 mins
    return () => clearInterval(interval);
  }, [fetchRates]);

  const setCurrency = (c: Currency) => {
    setCurrencyState(c);
    if (typeof window !== 'undefined') {
      localStorage.setItem('stellarts_currency', c);
    }
  };

  const convert = (amount: number) => {
    if (currency === 'XLM') return amount;
    const rate = rates[currency] || 0;
    return amount * rate;
  };

  const format = (amountInXLM: number) => {
    if (currency === 'XLM') {
       return `${amountInXLM.toLocaleString(undefined, { maximumFractionDigits: 4 })} XLM`;
    }

    const converted = convert(amountInXLM);
    
    // For fiat currencies, use standard Intl formatting
    try {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency === 'NGN' ? 'NGN' : currency,
      }).format(converted);
    } catch (e) {
      // Fallback if locale/currency pair fails
      const symbols: Record<string, string> = { USD: '$', EUR: '€', GBP: '£', NGN: '₦' };
      return `${symbols[currency] || ''}${converted.toFixed(2)}`;
    }
  };

  return (
    <CurrencyContext.Provider value={{ currency, setCurrency, rates, loading, convert, format }}>
      {children}
    </CurrencyContext.Provider>
  );
};

export const useCurrency = () => {
  const context = useContext(CurrencyContext);
  if (!context) throw new Error('useCurrency must be used within CurrencyProvider');
  return context;
};
