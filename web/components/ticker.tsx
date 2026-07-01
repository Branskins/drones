'use client';

import { useEffect, useState } from 'react';
import type { TickerData } from '@/lib/kraken';

function PriceRow({ label, price }: { label: string; price: number }) {
  return (
    <p className="text-lg">
      <span className="font-semibold">{label}:</span>
      <span className="ml-2">
        ${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
    </p>
  );
}

export default function Ticker({ children }: { children?: React.ReactNode }) {
  const [tickers, setTickers] = useState<TickerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPrice = async () => {
      try {
        const response = await fetch('/api/ticker');
        if (!response.ok) throw new Error('Failed to fetch');
        const data = await response.json();
        setTickers(data);
        setError(null);
      } catch (err) {
        setError('Failed to load prices');
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
  if (!tickers) return null;

  return (
    <div className="p-6 bg-gray-100 rounded-lg">
      {children}
      <h2 className="text-2xl font-bold mb-4">Crypto Prices (Kraken)</h2>

      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-bold mb-1">Bitcoin (BTC)</h3>
          <div className="space-y-1 pl-2">
            <PriceRow label="Ask" price={tickers.btc.askPrice} />
            <PriceRow label="Bid" price={tickers.btc.bidPrice} />
            <p className="text-sm text-gray-600">
              24h Volume: {tickers.btc.volume24h.toLocaleString()} BTC
            </p>
          </div>
        </div>

        <div>
          <h3 className="text-lg font-bold mb-1">Ethereum (ETH)</h3>
          <div className="space-y-1 pl-2">
            <PriceRow label="Ask" price={tickers.eth.askPrice} />
            <PriceRow label="Bid" price={tickers.eth.bidPrice} />
            <p className="text-sm text-gray-600">
              24h Volume: {tickers.eth.volume24h.toLocaleString()} ETH
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
