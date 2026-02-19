import { createClient } from '@/utils/supabase';

interface LedgersProps {
  bidPrice: number;
}

export default async function Ledgers({ bidPrice }: LedgersProps) {
  const supabase = await createClient();
  const { data: sales } = await supabase
    .from("sales")
    .select();

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Ref ID</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Asset</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Amount</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Buy</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Purchase Price</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>P&L</th>
        </tr>
      </thead>
      <tbody>
        {sales?.map((sale) => {
          const pnl = (sale.amount_non_zusd * bidPrice) - sale.amount_zusd;
          return (
            <tr key={sale.refid}>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{sale.refid}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{sale.asset}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{sale.amount_non_zusd}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{sale.amount_zusd}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{sale.purchase_price}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right', color: pnl >= 0 ? 'green' : 'red' }}>
                ${pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
