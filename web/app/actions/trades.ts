'use server';

import { createClient } from '@/lib/supabase/server';
import { addOrder } from '@/lib/kraken';
import { revalidatePath } from 'next/cache';

export async function markTradeAsSold(baseLedgerId: string) {
  const supabase = await createClient();

  // Fetch the trade row so we have the asset & volume to send to Kraken
  const { data: trade, error: fetchError } = await supabase
    .from('trades')
    .select('asset, volume')
    .eq('base_ledger_id', baseLedgerId)
    .single();

  if (fetchError || !trade) {
    throw new Error(`Trade not found: ${fetchError?.message}`);
  }

  // Map Kraken asset codes to the pair format AddOrder expects
  const pairMap: Record<string, string> = {
    XXBT: 'XBTUSD',
    XETH: 'ETHUSD',
  };
  const pair = pairMap[trade.asset];
  if (!pair) {
    throw new Error(`Unsupported asset: ${trade.asset}`);
  }

  // Place a market sell order on Kraken
  const order = await addOrder({
    pair,
    type: 'sell',
    ordertype: 'market',
    volume: String(trade.volume),
  });

  console.log('Kraken order placed:', order.descr.order, '| txid:', order.txid);

  // Mark the trade as sold in Supabase
  const { error: updateError } = await supabase
    .from('trades')
    .update({ status: 'sold', order_txid: order.txid[0] })
    .eq('base_ledger_id', baseLedgerId);

  if (updateError) {
    throw new Error(`Kraken order placed but DB update failed: ${updateError.message}`);
  }

  revalidatePath('/');
}
