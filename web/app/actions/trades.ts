'use server';

import { createClient } from '@/lib/supabase/server';
import { addOrder } from '@/lib/kraken';
import { revalidatePath } from 'next/cache';

export async function markTradeAsSold(baseLedgerId: string) {
  const supabase = await createClient();

  // Optimistic lock: claim the lot by flipping available -> selling before any
  // order is placed. A concurrent call (double click, second session) matches
  // zero rows and stops here instead of firing a second live order.
  const { data: claimed, error: claimError } = await supabase
    .from('trades')
    .update({ status: 'selling' })
    .eq('base_ledger_id', baseLedgerId)
    .eq('status', 'available')
    .select('asset, volume');

  if (claimError) {
    throw new Error(`Failed to claim trade: ${claimError.message}`);
  }
  if (!claimed || claimed.length === 0) {
    throw new Error('Trade is not available (already sold or being sold)');
  }
  const trade = claimed[0];

  // Map Kraken asset codes to the pair format AddOrder expects
  const pairMap: Record<string, string> = {
    XXBT: 'XBTUSD',
    XETH: 'ETHUSD',
  };
  const pair = pairMap[trade.asset];
  if (!pair) {
    await releaseClaim(baseLedgerId);
    throw new Error(`Unsupported asset: ${trade.asset}`);
  }

  let order;
  try {
    // Place a market sell order on Kraken
    order = await addOrder({
      pair,
      type: 'sell',
      ordertype: 'market',
      volume: String(trade.volume),
    });
  } catch (err) {
    // No order was placed; release the lot so it can be retried.
    await releaseClaim(baseLedgerId);
    throw err;
  }

  console.log('Kraken order placed:', order.descr.order, '| txid:', order.txid);

  // Mark the trade as sold in Supabase. Do NOT release the claim on failure
  // here — the live order exists, so the lot must never return to 'available'.
  const { error: updateError } = await supabase
    .from('trades')
    .update({ status: 'sold', order_txid: order.txid[0] })
    .eq('base_ledger_id', baseLedgerId);

  if (updateError) {
    throw new Error(
      `Kraken order ${order.txid[0]} placed but DB update failed (lot left in 'selling'): ${updateError.message}`
    );
  }

  revalidatePath('/');
}

async function releaseClaim(baseLedgerId: string) {
  const supabase = await createClient();
  await supabase
    .from('trades')
    .update({ status: 'available' })
    .eq('base_ledger_id', baseLedgerId)
    .eq('status', 'selling');
}
