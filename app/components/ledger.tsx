import { createClient } from '@/utils/supabase';
import { markTradeAsSold } from '@/app/actions/trades';

interface LedgersProps {
  btcBidPrice: number;
  ethBidPrice: number;
}

export default async function Ledgers({ btcBidPrice, ethBidPrice }: LedgersProps) {
  const supabase = await createClient();
  const { data: trades } = await supabase
    .from("trades")
    .select()
    .or('asset.eq.XXBT, asset.eq.XETH')
    .eq('status', 'available')
    .order('executed_at', { ascending: false });

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Base Ledger</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Asset</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Amount</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Price (USD)</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Buy</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Fee (USD)</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>P&L</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Gain %</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'center' }}>Action</th>
        </tr>
      </thead>
      <tbody>
        {trades?.map((trade) => {
          const bidPrice = trade.asset === 'XETH' ? ethBidPrice : btcBidPrice;
          const pnl = (trade.volume * bidPrice) - trade.cost_usd;
          const gainPct = (pnl / trade.cost_usd) * 100;
          return (
            <tr key={trade.base_ledger_id}>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{trade.base_ledger_id}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{trade.asset}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{trade.volume}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{trade.price_usd}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{trade.cost_usd}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{trade.fee_usd}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right', color: pnl >= 0 ? 'green' : 'red' }}>
                ${pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </td>
              <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right', color: gainPct >= 0 ? 'green' : 'red' }}>
                {gainPct.toFixed(2)}%
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
    </table>
  );
}
