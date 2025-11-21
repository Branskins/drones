import { createClient } from '@/utils/supabase';

export default async function Ledgers() {
  const supabase = await createClient();
  const { data: ledgers } = await supabase
    .from("ledgers")
    .select()
    .limit(10);

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Ref ID</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Balance</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Amount</th>
        </tr>
      </thead>
      <tbody>
        {ledgers?.map((ledger) => (
          <tr key={ledger.ledger_id}>
            <td style={{ border: '1px solid #ddd', padding: '8px' }}>{ledger.refid}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{ledger.balance}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{ledger.amount}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
