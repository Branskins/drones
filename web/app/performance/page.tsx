import { createClient } from '@/lib/supabase/server';

const cell: React.CSSProperties = { border: '1px solid #ddd', padding: '8px', textAlign: 'right' };
const cellL: React.CSSProperties = { ...cell, textAlign: 'left' };

function fmt(n: number | string | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return '-';
  return Number(n).toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export default async function Performance() {
  const supabase = await createClient();

  const [{ data: snapshots }, { data: lots }, { data: orders }, { data: events }] =
    await Promise.all([
      supabase.from('equity_snapshots').select().order('ts', { ascending: false }).limit(96),
      supabase.from('lots').select().in('state', ['open', 'exiting']).order('opened_at'),
      supabase.from('orders').select().in('state', ['pending', 'submitted', 'open'])
        .order('price', { ascending: false }),
      supabase.from('bot_events').select().order('ts', { ascending: false }).limit(30),
    ]);

  const latest = snapshots?.[0];
  const botLots = (lots ?? []).filter((l) => l.strategy !== 'legacy');
  const legacyLots = (lots ?? []).filter((l) => l.strategy === 'legacy');

  return (
    <div style={{ padding: '16px', display: 'grid', gap: '24px' }}>
      <h1>Bot performance</h1>

      <section>
        <h2>Latest snapshot {latest ? `(${latest.mode}, ${new Date(latest.ts).toLocaleString()})` : ''}</h2>
        {latest ? (
          <table style={{ borderCollapse: 'collapse' }}>
            <tbody>
              <tr>
                <th style={cellL}>Equity</th>
                <td style={cell}>${fmt(Number(latest.cash_usd) + Number(latest.inventory_value_usd))}</td>
                <th style={cellL}>Cash</th>
                <td style={cell}>${fmt(latest.cash_usd)}</td>
                <th style={cellL}>Inventory</th>
                <td style={cell}>${fmt(latest.inventory_value_usd)}</td>
              </tr>
              <tr>
                <th style={cellL}>Realized</th>
                <td style={cell}>${fmt(latest.realized_cum_usd)}</td>
                <th style={cellL}>Unrealized</th>
                <td style={cell}>${fmt(latest.unrealized_usd)}</td>
                <th style={cellL}>Fees paid</th>
                <td style={cell}>${fmt(latest.fees_cum_usd)}</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p>No snapshots yet — the bot has not run.</p>
        )}
      </section>

      <section>
        <h2>Open bot lots ({botLots.length})</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={cellL}>Strategy</th>
              <th style={cellL}>Asset</th>
              <th style={cell}>Volume</th>
              <th style={cell}>Cost $</th>
              <th style={cell}>Target</th>
              <th style={cellL}>State</th>
              <th style={cellL}>Opened</th>
            </tr>
          </thead>
          <tbody>
            {botLots.map((l) => (
              <tr key={l.id}>
                <td style={cellL}>{l.strategy}</td>
                <td style={cellL}>{l.asset}</td>
                <td style={cell}>{fmt(l.volume, 8)}</td>
                <td style={cell}>{fmt(l.cost_usd)}</td>
                <td style={cell}>{fmt(l.target_price)}</td>
                <td style={cellL}>{l.state}</td>
                <td style={cellL}>{new Date(l.opened_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Resting orders ({(orders ?? []).length})</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={cellL}>Mode</th>
              <th style={cellL}>Strategy</th>
              <th style={cellL}>Side</th>
              <th style={cell}>Price</th>
              <th style={cell}>Volume</th>
              <th style={cellL}>State</th>
              <th style={cellL}>Reason</th>
            </tr>
          </thead>
          <tbody>
            {(orders ?? []).map((o) => (
              <tr key={o.id}>
                <td style={cellL}>{o.mode}</td>
                <td style={cellL}>{o.strategy}</td>
                <td style={cellL}>{o.side}</td>
                <td style={cell}>{fmt(o.price, 1)}</td>
                <td style={cell}>{fmt(o.volume, 8)}</td>
                <td style={cellL}>{o.state}</td>
                <td style={cellL}>{o.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Legacy lot aging ({legacyLots.length} awaiting +1% net exit)</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={cellL}>Asset</th>
              <th style={cell}>Volume</th>
              <th style={cell}>Cost $</th>
              <th style={cell}>Target price</th>
              <th style={cellL}>Opened</th>
            </tr>
          </thead>
          <tbody>
            {legacyLots
              .sort((a, b) => Number(a.target_price) - Number(b.target_price))
              .map((l) => (
                <tr key={l.id}>
                  <td style={cellL}>{l.asset}</td>
                  <td style={cell}>{fmt(l.volume, 8)}</td>
                  <td style={cell}>{fmt(l.cost_usd)}</td>
                  <td style={cell}>{fmt(l.target_price)}</td>
                  <td style={cellL}>{new Date(l.opened_at).toLocaleDateString()}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Recent bot events</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={cellL}>Time</th>
              <th style={cellL}>Severity</th>
              <th style={cellL}>Kind</th>
              <th style={cellL}>Detail</th>
            </tr>
          </thead>
          <tbody>
            {(events ?? []).map((e) => (
              <tr key={e.id}>
                <td style={cellL}>{new Date(e.ts).toLocaleString()}</td>
                <td style={{ ...cellL, color: e.severity === 'error' ? '#c00' : e.severity === 'warn' ? '#b80' : undefined }}>
                  {e.severity}
                </td>
                <td style={cellL}>{e.kind}</td>
                <td style={cellL}>{e.detail ? JSON.stringify(e.detail) : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
