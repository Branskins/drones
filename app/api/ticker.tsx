import { NextResponse } from 'next/server';

export async function GET() {
  try {
    const response = await fetch(
      'https://api.kraken.com/0/public/Ticker?pair=XBTUSD',
      { next: { revalidate: 30 } }
    );
    
    const data = await response.json();
    
    if (data.error && data.error.length > 0) {
      return NextResponse.json(
        { error: data.error },
        { status: 500 }
      );
    }
    
    const ticker = data.result.XXBTZUSD;
    
    return NextResponse.json({
      askPrice: parseFloat(ticker.a[0]),
      bidPrice: parseFloat(ticker.b[0]),
      lastPrice: parseFloat(ticker.c[0]),
      volume24h: parseFloat(ticker.v[1]),
    });
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch Bitcoin price' },
      { status: 500 }
    );
  }
}