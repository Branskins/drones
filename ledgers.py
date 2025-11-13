import argparse
import base64
import hashlib
import hmac
import http.client
import json
import os
import time
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from supabase import Client, create_client


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
        ledgers = {}
        offset = 0
        batch_size = 50
        supabase: Client = create_client(url, key)

        while True:
            response = request(
                method="POST",
                path="/0/private/Ledgers",
                body = {
                    "ofs": offset
                },
                public_key=PUBLIC_KEY,
                private_key=PRIVATE_KEY,
                environment="https://api.kraken.com",
            )

            ledger = parse_ledger(response)
            ledgers.update(ledger['result']['ledger'])

            if len(ledger['result']['ledger']) < batch_size:
                break

            offset += batch_size

            time.sleep(1)

        df = pd.DataFrame.from_dict(ledgers, orient='index')
        df.reset_index(names='ledger_id', inplace=True)
        # df = df[df['type'].isin(['deposit', 'receive', 'spend'])]
        df = df[['ledger_id', 'amount', 'asset', 'balance', 'fee' , 'refid', 'time', 'type']]
        df = df.astype({'amount': float, 'balance': float, 'fee': float, 'time': int})
        
        try:
            response = (
                supabase.table('ledgers')
                .insert(df.to_dict(orient='records'))
                .execute()
            )
            print(response)
        except Exception as exception:
            print(exception)

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

def request(method: str = "GET", path: str = "", query: dict | None = None, body: dict | None = None, public_key: str = "", private_key: str = "", environment: str = "") -> http.client.HTTPResponse:
    url = environment + path
    query_str = ""
    if query is not None and len(query) > 0:
        query_str = urllib.parse.urlencode(query)
        url += "?" + query_str
    nonce = ""
    if len(public_key) > 0:
        if body is None:
            body = {}
        nonce = body.get("nonce")
        if nonce is None:
            nonce = get_nonce()
            body["nonce"] = nonce
    headers = {}
    body_str = ""
    if body is not None and len(body) > 0:
        body_str = json.dumps(body)
        headers["Content-Type"] = "application/json"
    if len(public_key) > 0:
        headers["API-Key"] = public_key
        headers["API-Sign"] = get_signature(private_key, query_str+body_str, nonce, path)
    req = urllib.request.Request(
        method=method,
        url=url,
        data=body_str.encode(),
        headers=headers,
    )
    return urllib.request.urlopen(req)

def get_nonce() -> str:
    return str(int(time.time() * 1000))

def get_signature(private_key: str, data: str, nonce: str, path: str) -> str:
    return sign(
        private_key=private_key,
        message=path.encode() + hashlib.sha256(
                (nonce + data)
            .encode()
        ).digest()
    )

def sign(private_key: str, message: bytes) -> str:
    return base64.b64encode(
        hmac.new(
            key=base64.b64decode(private_key),
            msg=message,
            digestmod=hashlib.sha512,
        ).digest()
    ).decode()


if __name__ == '__main__':
    main()
