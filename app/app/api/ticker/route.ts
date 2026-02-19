import { NextResponse } from 'next/server';
import { fetchPriceData } from '@/utils/kraken';

export async function GET() {
  try {
    const data = await fetchPriceData();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch Bitcoin price' },
      { status: 500 }
    );
  }
}
