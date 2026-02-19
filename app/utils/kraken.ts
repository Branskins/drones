export interface PriceData {
  askPrice: number;
  bidPrice: number;
  lastPrice: number;
  volume24h: number;
}

export async function fetchPriceData(): Promise<PriceData> {
  const response = await fetch(
    'https://api.kraken.com/0/public/Ticker?pair=XBTUSD',
    { next: { revalidate: 30 } }
  );
  const data = await response.json();

  if (data.error && data.error.length > 0) {
    throw new Error(data.error.join(', '));
  }

  const ticker = data.result.XXBTZUSD;
  return {
    askPrice: parseFloat(ticker.a[0]),
    bidPrice: parseFloat(ticker.b[0]),
    lastPrice: parseFloat(ticker.c[0]),
    volume24h: parseFloat(ticker.v[1]),
  };
}
