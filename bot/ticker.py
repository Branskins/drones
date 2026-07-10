"""Public ticker fetch (no auth, no nonce — safe from any context)."""

import json
import urllib.request

RESULT_KEYS = {'XBTUSD': 'XXBTZUSD', 'ETHUSD': 'XETHZUSD'}
PAIR_ASSET = {'XBTUSD': 'XXBT', 'ETHUSD': 'XETH'}


def fetch(pair: str) -> dict:
    url = f'https://api.kraken.com/0/public/Ticker?pair={pair}'
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())
    if data.get('error'):
        raise ValueError(', '.join(data['error']))
    t = data['result'][RESULT_KEYS.get(pair, pair)]
    return {
        'ask': float(t['a'][0]),
        'bid': float(t['b'][0]),
        'last': float(t['c'][0]),
    }
