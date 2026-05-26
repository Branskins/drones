import crypto from 'crypto';

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

export interface AddOrderParams {
  pair: string;
  type: string;
  ordertype: string;
  volume: string;
  price?: string;
}

export interface AddOrderResult {
  txid: string[];
  descr: { order: string };
}

function getNonce(): string {
  return Date.now().toString();
}

function getSignature(
  privateKey: string,
  path: string,
  nonce: string,
  postData: string
): string {
  const message = path + crypto
    .createHash('sha256')
    .update(nonce + postData)
    .digest('binary');

  const hmac = crypto.createHmac(
    'sha512',
    Buffer.from(privateKey, 'base64')
  );
  hmac.update(message, 'binary');
  return hmac.digest('base64');
}

async function privateRequest<T>(
  path: string,
  body: Record<string, string>
): Promise<T> {
  const publicKey = process.env.PUBLIC_KEY;
  const privateKey = process.env.PRIVATE_KEY;

  if (!publicKey || !privateKey) {
    throw new Error('Kraken API keys are not configured (PUBLIC_KEY / PRIVATE_KEY)');
  }

  const nonce = getNonce();
  const params = new URLSearchParams({ ...body, nonce });
  const postData = params.toString();

  const signature = getSignature(privateKey, `/0${path}`, nonce, postData);

  const response = await fetch(`https://api.kraken.com/0${path}`, {
    method: 'POST',
    headers: {
      'API-Key': publicKey,
      'API-Sign': signature,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: postData,
  });

  const data = await response.json();

  if (data.error && data.error.length > 0) {
    throw new Error(`Kraken API error: ${data.error.join(', ')}`);
  }

  return data.result as T;
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

export async function addOrder(params: AddOrderParams): Promise<AddOrderResult> {
  const body: Record<string, string> = {
    pair: params.pair,
    type: params.type,
    ordertype: params.ordertype,
    volume: params.volume,
  };

  if (params.price) {
    body.price = params.price;
  }

  return privateRequest<AddOrderResult>('/private/AddOrder', body);
}
