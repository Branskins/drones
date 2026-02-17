import Ledgers from '../components/ledger';
import Ticker from '../components/ticker';

export default function Home() {
  return (
    <div>
      <h1>Hello world!</h1>
      <Ticker>
        <Ledgers />
      </Ticker>
    </div>
  );
}
