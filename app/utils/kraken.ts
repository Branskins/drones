export interface PriceData {
  askPrice: number;
  bidPrice: number;
  lastPrice: number;
  volume24h: number;
}

export interface TickerData {
  btc: PriceData;
  eth: PriceData;
}

function parseTicker(ticker: Record<string, string[]>): PriceData {
  return {
    askPrice: parseFloat(ticker.a[0]),
    bidPrice: parseFloat(ticker.b[0]),
    lastPrice: parseFloat(ticker.c[0]),
    volume24h: parseFloat(ticker.v[1]),
  };
}

export async function fetchPriceData(): Promise<TickerData> {
  const pairs = ['XBTUSD', 'ETHUSD'].join(',');
  const response = await fetch(
    `https://api.kraken.com/0/public/Ticker?pair=${pairs}`,
    { next: { revalidate: 30 } }
  );
  const data = await response.json();

  if (data.error && data.error.length > 0) {
    throw new Error(data.error.join(', '));
  }

  return {
    btc: parseTicker(data.result['XXBTZUSD']),
    eth: parseTicker(data.result['XETHZUSD']),
  };
}
