'use client';

import { useEffect, useState } from 'react';
import { markTradeAsSold } from '@/app/actions/trades';
import type { TickerData } from '@/utils/kraken';

interface Trade {
  base_ledger_id: string;
  asset: string;
  volume: number;
  price_usd: number;
  cost_usd: number;
  fee_usd: number;
}

export default function LedgerTable({ trades }: { trades: Trade[] }) {
  const [tickers, setTickers] = useState<TickerData | null>(null);

  useEffect(() => {
    const fetchPrices = async () => {
      try {
        const res = await fetch('/api/ticker');
        if (res.ok) setTickers(await res.json());
      } catch {}
    };

    fetchPrices();
    const interval = setInterval(fetchPrices, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <tbody>
      {trades.map((trade) => {
        const bidPrice = tickers
          ? trade.asset === 'XETH'
            ? tickers.eth.bidPrice
            : tickers.btc.bidPrice
          : null;
        const pnl = bidPrice !== null ? (trade.volume * bidPrice) - trade.cost_usd - trade.fee_usd : null;
        const gainPct = pnl !== null ? (pnl / trade.cost_usd) * 100 : null;
        return (
          <tr key={trade.base_ledger_id}>
            <td style={{ border: '1px solid #ddd', padding: '8px' }}>{trade.base_ledger_id}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px' }}>{trade.asset}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{trade.volume}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{trade.price_usd}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{trade.cost_usd}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{trade.fee_usd}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right', color: pnl !== null ? (pnl >= 0 ? 'green' : 'red') : undefined }}>
              {pnl !== null ? `$${pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
            </td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right', color: gainPct !== null ? (gainPct >= 0 ? 'green' : 'red') : undefined }}>
              {gainPct !== null ? `${gainPct.toFixed(2)}%` : '—'}
            </td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'center' }}>
              <form action={markTradeAsSold.bind(null, trade.base_ledger_id)}>
                <button type="submit" style={{ padding: '4px 12px', cursor: 'pointer' }}>
                  Trade
                </button>
              </form>
            </td>
          </tr>
        );
      })}
    </tbody>
  );
}
