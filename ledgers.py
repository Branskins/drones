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
        choices=['csv', 'ledger', 'db'],
        help='Output format: csv (save to CSV file), ledger (print ledger data) or db (save to Supabase) '
    )
    args = parser.parse_args()

    load_dotenv()
    PUBLIC_KEY = os.environ.get('PUBLIC_KEY')
    PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")

    if args.output == 'ledger':
        response = request(
            method="POST",
            path="/0/private/Ledgers",
            public_key=PUBLIC_KEY,
            private_key=PRIVATE_KEY,
            environment="https://api.kraken.com",
        )
        ledger = parse_ledger(response)

        print(json.dumps(ledger, indent=4))
    elif args.output == 'db':
        supabase: Client = create_client(url, key)
        sync_ledgers(supabase, PUBLIC_KEY, PRIVATE_KEY)
        print('Saved to DB')

    elif args.output == 'csv':
        response = request(
            method="POST",
            path="/0/private/Ledgers",
            public_key=PUBLIC_KEY,
            private_key=PRIVATE_KEY,
            environment="https://api.kraken.com",
        )
        ledger = parse_ledger(response)

        save_ledger(ledger['result']['ledger'])
        print('Saved to CSV')

SYNC_OVERLAP_SECONDS = 86400  # re-fetch a day of overlap; upsert dedupes


def _last_synced_time(supabase: Client) -> int | None:
    rows = (
        supabase.table('ledgers')
        .select('time')
        .order('time', desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0]['time'] if rows else None


def sync_ledgers(supabase: Client, public_key: str, private_key: str) -> None:
    ledgers = {}
    offset = 0
    batch_size = 50
    since = _last_synced_time(supabase)

    while True:
        body = {"ofs": offset}
        if since is not None:
            body["start"] = since - SYNC_OVERLAP_SECONDS
        response = request(
            method="POST",
            path="/0/private/Ledgers",
            body=body,
            public_key=public_key,
            private_key=private_key,
            environment="https://api.kraken.com",
        )
        ledger = parse_ledger(response)
        ledgers.update(ledger['result']['ledger'])

        if len(ledger['result']['ledger']) < batch_size:
            break

        offset += batch_size
        time.sleep(1)

    if not ledgers:
        return

    df = pd.DataFrame.from_dict(ledgers, orient='index')
    df.reset_index(names='ledger_id', inplace=True)
    df = df[['ledger_id', 'amount', 'asset', 'balance', 'fee', 'refid', 'time', 'type']]
    df = df.astype({'amount': float, 'balance': float, 'fee': float, 'time': int})

    response = (
        supabase.table('ledgers')
        .upsert(df.to_dict(orient='records'), on_conflict='ledger_id')
        .execute()
    )

def save_ledger(ledger: dict):
    df = pd.DataFrame.from_dict(ledger, orient='index')
    df.reset_index(names='ledger_id', inplace=True)
    df.to_csv('ledgers.csv', index=False)

def parse_ledger(response: http.client.HTTPResponse) -> dict:
    decoded_json = json.loads(response.read())

    # Check for errors in the response
    if 'error' in decoded_json and decoded_json['error']:
        error_msg = ', '.join(decoded_json['error'])
        raise ValueError(error_msg)

    # Check if result exists
    if 'result' not in decoded_json or 'ledger' not in decoded_json['result']:
        raise ValueError("Missing 'result' or 'ledger'")

    return decoded_json


if __name__ == '__main__':
    main()
