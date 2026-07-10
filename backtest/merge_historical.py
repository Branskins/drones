"""Merge Kraken's downloadable OHLCVT archive files into the candle caches.

Drop archive files into backtest/data/ named `{PAIR}_{INTERVAL}_historical.csv`
(e.g. XBTUSD_1440_historical.csv) and run:

    python -m backtest.merge_historical

Archive format (no header): unix_time,open,high,low,close,volume,trade_count
Cache format  (header):     ts (ISO 8601 UTC),open,high,low,close,volume

Where the archive overlaps existing cache rows, the cache (public API) values
win. Re-runnable: merging is idempotent, and the _historical source files are
left in place. After merging, re-run `python -m backtest.study`.
"""

import glob
import os
import re

import pandas as pd

from bot.data import COLUMNS, DATA_DIR, cache_path

ARCHIVE_COLUMNS = ['time', 'open', 'high', 'low', 'close', 'volume', 'trade_count']


def load_archive(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, header=None, names=ARCHIVE_COLUMNS)
    df['ts'] = pd.to_datetime(df['time'].astype(int), unit='s', utc=True)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    return df[COLUMNS]


def merge_into_cache(pair: str, interval_min: int, archive: pd.DataFrame) -> pd.DataFrame:
    path = cache_path(pair, interval_min)
    frames = [archive]
    if os.path.exists(path):
        cached = pd.read_csv(path, parse_dates=['ts'])
        cached['ts'] = pd.to_datetime(cached['ts'], utc=True)
        frames.append(cached)  # last wins on duplicate ts -> cache/API rows
    merged = (pd.concat(frames)
              .drop_duplicates(subset='ts', keep='last')
              .sort_values('ts')
              .reset_index(drop=True))
    merged.to_csv(path, index=False)
    return merged


def gap_report(df: pd.DataFrame, interval_min: int) -> str:
    expected = pd.date_range(df['ts'].min(), df['ts'].max(),
                             freq=f'{interval_min}min', tz='UTC')
    missing = expected.difference(df['ts'])
    if missing.empty:
        return 'no gaps'
    return (f'{len(missing)} missing candle(s), '
            f'first {missing[0]:%Y-%m-%d}, last {missing[-1]:%Y-%m-%d}')


def main():
    pattern = os.path.join(DATA_DIR, '*_historical.csv')
    files = sorted(glob.glob(pattern))
    if not files:
        print(f'no *_historical.csv files found in {DATA_DIR}')
        return

    for path in files:
        name = os.path.basename(path)
        m = re.match(r'^([A-Z0-9]+)_(\d+)_historical\.csv$', name)
        if not m:
            print(f'skip {name}: expected {{PAIR}}_{{INTERVAL}}_historical.csv')
            continue
        pair, interval_min = m.group(1), int(m.group(2))
        archive = load_archive(path)
        merged = merge_into_cache(pair, interval_min, archive)
        print(f'{name}: {len(archive)} archive rows -> cache now {len(merged)} candles '
              f'({merged.ts.min():%Y-%m-%d} .. {merged.ts.max():%Y-%m-%d}), '
              f'{gap_report(merged, interval_min)}')


if __name__ == '__main__':
    main()
