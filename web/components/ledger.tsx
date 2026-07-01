import { createClient } from '@/lib/supabase/server';
import Ticker from '@/components/ticker';
import LedgerTable from '@/components/ledger-table';

export default async function Ledgers() {
  const supabase = await createClient();
  const { data: trades } = await supabase
    .from("trades")
    .select()
    .or('asset.eq.XXBT, asset.eq.XETH')
    .eq('status', 'available')
    .order('executed_at', { ascending: false });

  return (
    <>
    <Ticker />
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
      <LedgerTable trades={trades ?? []} />
    </table>
    </>
  );
}
