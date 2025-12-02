'use client';

import { useEffect, useState } from 'react';

interface PriceData {
  askPrice: number;
  bidPrice: number;
  lastPrice: number;
  volume24h: number;
}

export default function Ticker() {
  const [price, setPrice] = useState<PriceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPrice = async () => {
      try {
        const response = await fetch('/api/ticker');
        if (!response.ok) throw new Error('Failed to fetch');
        const data = await response.json();
        setPrice(data);
        setError(null);
      } catch (err) {
        setError('Failed to load price');
      } finally {
        setLoading(false);
      }
    };

    fetchPrice();
    
    const interval = setInterval(fetchPrice, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!price) return null;

  return (
    <div className="p-6 bg-gray-100 rounded-lg">
      <h2 className="text-2xl font-bold mb-4">Bitcoin Price (Kraken)</h2>
      <div className="space-y-2">
        <p className="text-lg">
          <span className="font-semibold">Sell Price:</span> 
          <span className="text-green-600 ml-2">
            ${price.askPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </p>
        <p className="text-lg">
          <span className="font-semibold">Buy Price:</span> 
          <span className="text-blue-600 ml-2">
            ${price.bidPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </p>
        <p className="text-sm text-gray-600">
          24h Volume: {price.volume24h.toLocaleString()} BTC
        </p>
      </div>
    </div>
  );
}