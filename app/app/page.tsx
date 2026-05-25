import Ledgers from '../components/ledger';
import { fetchPriceData } from '../utils/kraken';

export default async function Home() {
  const { btc, eth } = await fetchPriceData();

  return (
    <div>
      <Ledgers btcBidPrice={btc.bidPrice} ethBidPrice={eth.bidPrice} />
    </div>
  );
}
