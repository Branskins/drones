import { createClient } from '@/utils/supabase';

export default async function Ledgers() {
  const supabase = await createClient();
  const { data: sales } = await supabase
    .from("sales")
    .select()
    .limit(10);

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Ref ID</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Asset</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Amount</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Buy</th>
          <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>Purchase Price</th>
        </tr>
      </thead>
      <tbody>
        {sales?.map((sale) => (
          <tr key={sale.refid}>
            <td style={{ border: '1px solid #ddd', padding: '8px' }}>{sale.refid}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px' }}>{sale.asset}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{sale.amount_non_zusd}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{sale.amount_zusd}</td>
            <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>{sale.purchase_price}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
