import argparse
import http.client
import json
import os
import time

import pandas as pd
from dotenv import load_dotenv
from supabase import Client, create_client

from utils.kraken import request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'output',
        choices=['csv', 'trade', 'db'],
        help='Output format: csv (save to CSV file), trade (print trade data) or db (save to Supabase) '
    )
    args = parser.parse_args()

    load_dotenv()
    PUBLIC_KEY = os.environ.get('PUBLIC_KEY')
    PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")

    if args.output == 'trade':
        response = request(
            method="POST",
            path="/0/private/TradesHistory",
            public_key=PUBLIC_KEY,
            private_key=PRIVATE_KEY,
            environment="https://api.kraken.com",
        )
        trade = parse_trade(response)

        print(json.dumps(trade, indent=4))
    elif args.output == 'db':
        supabase: Client = create_client(url, key)
        sync_trades(supabase, PUBLIC_KEY, PRIVATE_KEY)
        print('Saved to DB')

    elif args.output == 'csv':
        response = request(
            method="POST",
            path="/0/private/TradesHistory",
            public_key=PUBLIC_KEY,
            private_key=PRIVATE_KEY,
            environment="https://api.kraken.com",
        )
        trade = parse_trade(response)

        save_trade(trade['result']['trades'])
        print('Saved to CSV')

def sync_trades(supabase: Client, public_key: str, private_key: str) -> None:
    trades = {}
    offset = 0
    batch_size = 50

    while True:
        response = request(
            method="POST",
            path="/0/private/TradesHistory",
            body={"ofs": offset},
            public_key=public_key,
            private_key=private_key,
            environment="https://api.kraken.com",
        )
        trade = parse_trade(response)
        trades.update(trade['result']['trades'])

        if len(trade['result']['trades']) < batch_size:
            break

        offset += batch_size
        time.sleep(1)

    df = pd.DataFrame.from_dict(trades, orient='index')
    df = df.rename(columns={'ordertxid': 'order_txid', 'trade_id': '_trade_id'})
    df.reset_index(names='trade_id', inplace=True)
    df = df[['trade_id', 'order_txid', 'pair', 'type', 'price', 'cost', 'fee', 'vol', 'time']]
    df = df.astype({'price': float, 'cost': float, 'fee': float, 'vol': float, 'time': float})

    response = (
        supabase.table('trades_history')
        .upsert(df.to_dict(orient='records'), on_conflict='trade_id')
        .execute()
    )

def save_trade(trades: dict):
    df = pd.DataFrame.from_dict(trades, orient='index')
    df.reset_index(names='_trade_id', inplace=True)
    df.to_csv('trades_history.csv', index=False)

def parse_trade(response: http.client.HTTPResponse) -> dict:
    decoded_json = json.loads(response.read())

    if 'error' in decoded_json and decoded_json['error']:
        error_msg = ', '.join(decoded_json['error'])
        raise ValueError(error_msg)

    if 'result' not in decoded_json or 'trades' not in decoded_json['result']:
        raise ValueError("Missing 'result' or 'trades'")

    return decoded_json


if __name__ == '__main__':
    main()
