import os
import time
import threading
import math
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS 
from dotenv import load_dotenv

# --- IMPORTS ---
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetAssetsRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetStatus, QueryOrderStatus
from datetime import datetime, timedelta
import database

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("APCA_API_KEY_ID")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")

# --- HEDGE FUND SETTINGS ---
WATCHLIST = ['BTC/USD', 'ETH/USD', 'SPY', 'QQQ', 'NVDA', 'TSLA'] 
MAX_POS_SIZE = 0.10  # Risk management: Max 10% per trade
TRADING_ACTIVE = False 
CURRENT_SYMBOL = "BTC/USD" 

app = Flask(__name__)
CORS(app)

# --- CACHING ---
ASSET_CACHE = []
def cache_assets():
    global ASSET_CACHE
    try:
        print("⏳ Loading Asset Database...")
        client = TradingClient(API_KEY, SECRET_KEY, paper=True)
        req = GetAssetsRequest(status=AssetStatus.ACTIVE)
        assets = client.get_all_assets(req)
        temp = [{"symbol": a.symbol, "name": a.name} for a in assets if a.tradable]
        ASSET_CACHE = temp
        print(f"✅ Loaded {len(ASSET_CACHE)} Assets!")
    except: pass

# --- ROUTES ---
@app.route('/')
def home(): return f"🤖 Bot Active: {TRADING_ACTIVE}"

@app.route('/api/toggle', methods=['POST'])
def toggle():
    global TRADING_ACTIVE
    TRADING_ACTIVE = not TRADING_ACTIVE
    return jsonify({"active": TRADING_ACTIVE})

@app.route('/api/status')
def status(): return jsonify({"active": TRADING_ACTIVE, "symbol": CURRENT_SYMBOL})

@app.route('/api/assets')
def assets(): return jsonify(ASSET_CACHE)

@app.route('/api/settings', methods=['POST'])
def set_symbol():
    global CURRENT_SYMBOL
    CURRENT_SYMBOL = request.json.get('symbol', 'BTC/USD').upper()
    return jsonify({"symbol": CURRENT_SYMBOL})

@app.route('/api/trades')
def trades():
    raw = database.get_trade_history()
    data = [{"id":r[0], "symbol":r[1], "action":r[2], "price":r[3], "timestamp":r[4]} for r in raw]
    return jsonify(data)

# --- NEW: POSITIONS ENDPOINT ---
@app.route('/api/positions')
def get_positions():
    try:
        client = TradingClient(API_KEY, SECRET_KEY, paper=True)
        positions = client.get_all_positions()
        data = []
        for p in positions:
            entry_time = "N/A"
            try:
                # Find the buy order time
                req = GetOrdersRequest(symbol=p.symbol, side=OrderSide.BUY, status=QueryOrderStatus.FILLED, limit=1)
                orders = client.get_orders(req)
                if orders: entry_time = orders[0].filled_at.strftime('%b %d %H:%M')
            except: pass

            data.append({
                "symbol": p.symbol,
                "qty": float(p.qty),
                "entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "pl": float(p.unrealized_pl),
                "pl_pct": float(p.unrealized_plpc) * 100,
                "entry_time": entry_time
            })
        return jsonify(data)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/history')
def history():
    try:
        df = get_market_data(CURRENT_SYMBOL)
        if df.empty: return jsonify([])
        df['SMA_10'] = df['close'].rolling(10).mean()
        df['SMA_30'] = df['close'].rolling(30).mean()
        df = df.reset_index()
        data = []
        for i, row in df.iterrows():
            ts = row['timestamp']
            if hasattr(ts, 'to_pydatetime'): ts = ts.to_pydatetime()
            s10 = row['SMA_10'] if not pd.isna(row['SMA_10']) else None
            s30 = row['SMA_30'] if not pd.isna(row['SMA_30']) else None
            data.append({
                "time": ts.strftime('%H:%M'),
                "open": row['open'], "high": row['high'], "low": row['low'], "close": row['close'],
                "price": row['close'], "sma_fast": s10, "sma_slow": s30
            })
        return jsonify(data)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/account')
def account():
    try:
        client = TradingClient(API_KEY, SECRET_KEY, paper=True)
        acc = client.get_account()
        return jsonify({
            "cash": float(acc.cash), "equity": float(acc.equity), 
            "symbol": CURRENT_SYMBOL, "active": TRADING_ACTIVE
        })
    except: return jsonify({"error": "Account Error"}), 500

@app.route('/api/manual', methods=['POST'])
def manual():
    data = request.json
    action = data.get('action').upper()
    df = get_market_data(CURRENT_SYMBOL)
    price = df.iloc[-1]['close']
    execute_trade(CURRENT_SYMBOL, action, price, manual=True)
    return jsonify({"status": "success"})

# --- LOGIC ---
def get_market_data(symbol):
    now = datetime.now()
    start = now - timedelta(hours=24)
    if "/" in symbol:
        client = CryptoHistoricalDataClient(API_KEY, SECRET_KEY)
        req = CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Minute, start=start)
        return client.get_crypto_bars(req).df
    else:
        client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
        req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Minute, start=start)
        return client.get_stock_bars(req).df

def calculate_safe_qty(symbol, price):
    try:
        client = TradingClient(API_KEY, SECRET_KEY, paper=True)
        acct = client.get_account()
        equity = float(acct.equity)
        budget = equity * MAX_POS_SIZE 
        if budget < price and "/" not in symbol: return 0
        if "/" in symbol: return round(budget / price, 4)
        return math.floor(budget / price)
    except: return 0

def execute_trade(symbol, signal, price, manual=False):
    if not TRADING_ACTIVE and not manual: return
    client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    
    try:
        pos = client.get_open_position(symbol)
        qty_held = float(pos.qty)
        has_pos = True
    except:
        has_pos = False
        qty_held = 0

    if signal == "BUY":
        if has_pos and not manual:
            print(f"✋ SKIP {symbol}: Already hold {qty_held}")
            return
        qty = calculate_safe_qty(symbol, price)
        if qty == 0: return
        print(f"🚀 BUY {qty} {symbol} @ ${price:.2f}")
        try:
            req = MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
            client.submit_order(req)
            database.log_trade(symbol, "BUY", price)
        except Exception as e: print(f"Order Error: {e}")

    elif signal == "SELL":
        if not has_pos: return
        print(f"📉 SELL ALL {symbol} @ ${price:.2f}")
        try:
            req = MarketOrderRequest(symbol=symbol, qty=qty_held, side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
            client.submit_order(req)
            database.log_trade(symbol, "SELL", price)
        except Exception as e: print(f"Order Error: {e}")

def run_portfolio_cycle():
    print(f"--- 🔄 SCANNING PORTFOLIO {datetime.now().strftime('%H:%M')} ---")
    database.initialize_db()
    for symbol in WATCHLIST:
        try:
            df = get_market_data(symbol)
            if len(df) < 30: continue
            fast = df['close'].rolling(10).mean().iloc[-1]
            slow = df['close'].rolling(30).mean().iloc[-1]
            signal = "BUY" if fast > slow else "SELL" if fast < slow else "HOLD"
            if signal != "HOLD":
                print(f"🔍 {symbol}: {signal} Signal")
                execute_trade(symbol, signal, df['close'].iloc[-1])
        except Exception as e:
            if "SPY" not in symbol: print(f"❌ Error {symbol}: {e}")

def start_loop():
    cache_assets()
    while True:
        run_portfolio_cycle()
        time.sleep(60)

if __name__ == "__main__":
    t = threading.Thread(target=start_loop)
    t.daemon = True
    t.start()
    # Using Port 5001 to avoid conflicts
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)