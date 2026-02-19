import Ledgers from '../components/ledger';
import Ticker from '../components/ticker';
import { fetchPriceData } from '../utils/kraken';

export default async function Home() {
  const { bidPrice } = await fetchPriceData();

  return (
    <div>
      <h1>Hello world!</h1>
      <Ticker>
        <Ledgers bidPrice={bidPrice} />
      </Ticker>
    </div>
  );
}
