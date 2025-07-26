from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import ccxt
import pandas as pd
from datetime import datetime
from ta.momentum import RSIIndicator

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

exchange = ccxt.kraken()
markets = exchange.load_markets()
target_symbols = [s for s in markets if any(s.endswith(q) for q in ['/USD', '/USDC']) and not s.startswith('.')]

def fetch_ohlcv_data(symbol, timeframe='1h', limit=50):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception:
        return None

def get_movers(invest_amount: float = 100.0):
    movers = []
    for symbol in target_symbols:
        df = fetch_ohlcv_data(symbol)
        if df is None or len(df) < 30:
            continue
        df['ema_fast'] = df['close'].ewm(span=8).mean()
        df['ema_slow'] = df['close'].ewm(span=21).mean()
        df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
        latest = df.iloc[-1]
        fast = latest['ema_fast']
        slow = latest['ema_slow']
        rsi_val = latest['rsi']
        if fast > slow and 40 < rsi_val < 70:
            avg_vol = df['volume'][:-3].mean()
            recent_vol = df['volume'][-3:].mean()
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 0
            if vol_ratio >= 2:
                price = latest['close']
                coin_qty = invest_amount / price
                movers.append({
                    "symbol": symbol,
                    "price": round(price, 6),
                    "can_buy": round(coin_qty, 6),
                    "rsi": round(rsi_val, 2),
                    "vol_spike": round(vol_ratio, 2),
                    "ema_fast": round(fast, 6),
                    "ema_slow": round(slow, 6)
                })
    movers.sort(key=lambda x: x['vol_spike'], reverse=True)
    return movers

@app.get("/scan")
def scan(invest_amount: float = Query(100.0, ge=10)):
    data = get_movers(invest_amount)
    return {
        "timestamp": datetime.utcnow(),
        "amount": invest_amount,
        "count": len(data),
        "candidates": data
    }
