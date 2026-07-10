"""Market data loader: Kraken public OHLC -> local CSV cache + market_data table.

The public OHLC endpoint returns at most the last 720 candles per interval:
  - interval 1440 (1d)  -> ~2 years
  - interval 240  (4h)  -> ~4 months
Deeper history requires Kraken's downloadable OHLCVT CSV archive (manual step,
see docs/human-actions.md); drop those files into backtest/data/ with the same
column layout and the loaders below pick them up transparently.

Usage:
    python -m bot.data              # refresh caches + upsert market_data
"""

import json
import os
import urllib.request
from datetime import datetime, timezone

import pandas as pd

PAIRS = {'XBTUSD': 'XXBTZUSD', 'ETHUSD': 'XETHZUSD'}
INTERVALS_MIN = [1440, 240]
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'backtest', 'data')
COLUMNS = ['ts', 'open', 'high', 'low', 'close', 'volume']


def fetch_ohlc(pair: str, interval_min: int) -> pd.DataFrame:
    """Fetch up to 720 recent candles from Kraken's public OHLC endpoint."""
    url = f'https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval_min}'
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())
    if data.get('error'):
        raise ValueError(', '.join(data['error']))
    result_key = PAIRS.get(pair, pair)
    rows = data['result'][result_key]
    df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close',
                                     'vwap', 'volume', 'count'])
    df['ts'] = pd.to_datetime(df['time'].astype(int), unit='s', utc=True)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    # Last candle is still forming; drop it so stored candles are final.
    return df[COLUMNS].iloc[:-1].reset_index(drop=True)


def cache_path(pair: str, interval_min: int) -> str:
    return os.path.join(DATA_DIR, f'{pair}_{interval_min}.csv')


def refresh_cache(pair: str, interval_min: int) -> pd.DataFrame:
    """Merge freshly fetched candles into the local CSV cache (grows over time,
    and absorbs manually imported historical CSVs)."""
    fresh = fetch_ohlc(pair, interval_min)
    path = cache_path(pair, interval_min)
    if os.path.exists(path):
        cached = pd.read_csv(path, parse_dates=['ts'])
        cached['ts'] = pd.to_datetime(cached['ts'], utc=True)
        merged = (pd.concat([cached, fresh])
                  .drop_duplicates(subset='ts', keep='last')
                  .sort_values('ts')
                  .reset_index(drop=True))
    else:
        merged = fresh
    os.makedirs(DATA_DIR, exist_ok=True)
    merged.to_csv(path, index=False)
    return merged


def load_candles(pair: str, interval_min: int) -> pd.DataFrame:
    """Load candles from the local cache (refresh first if missing)."""
    path = cache_path(pair, interval_min)
    if not os.path.exists(path):
        return refresh_cache(pair, interval_min)
    df = pd.read_csv(path, parse_dates=['ts'])
    df['ts'] = pd.to_datetime(df['ts'], utc=True)
    return df


def upsert_market_data(supabase, pair: str, interval_min: int,
                       df: pd.DataFrame, since: datetime | None = None) -> int:
    """Push candles into the market_data table (chunked upsert)."""
    if since is not None:
        df = df[df['ts'] >= since]
    records = [
        {'pair': pair, 'interval_min': interval_min,
         'ts': row.ts.isoformat(), 'open': row.open, 'high': row.high,
         'low': row.low, 'close': row.close, 'volume': row.volume}
        for row in df.itertuples()
    ]
    for i in range(0, len(records), 500):
        supabase.table('market_data').upsert(
            records[i:i + 500], on_conflict='pair,interval_min,ts'
        ).execute()
    return len(records)


def main():
    import dotenv
    from supabase import create_client
    dotenv.load_dotenv()
    supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])
    for pair in PAIRS:
        for interval in INTERVALS_MIN:
            df = refresh_cache(pair, interval)
            n = upsert_market_data(supabase, pair, interval, df)
            print(f'{pair} {interval}m: cache={len(df)} candles '
                  f'({df.ts.min():%Y-%m-%d} .. {df.ts.max():%Y-%m-%d}), upserted={n}')


if __name__ == '__main__':
    main()
