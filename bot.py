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
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetAssetsRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetStatus
from datetime import datetime, timedelta
import database

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("APCA_API_KEY_ID")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")

# GLOBAL VARIABLES
CURRENT_SYMBOL = "SPY"
RISK_PER_TRADE = 0.10 
ASSET_CACHE = []
TRADING_ACTIVE = False  # <--- NEW: Default to OFF so it doesn't spend money instantly

app = Flask(__name__)
CORS(app)

# ... (Keep cache_assets same as before) ...
def cache_assets():
    global ASSET_CACHE
    try:
        print("⏳ Loading Asset Database...")
        client = TradingClient(API_KEY, SECRET_KEY, paper=True)
        req = GetAssetsRequest(status=AssetStatus.ACTIVE)
        assets = client.get_all_assets(req)
        temp_list = []
        for a in assets:
            if a.tradable:
                temp_list.append({"symbol": a.symbol, "name": a.name})
        ASSET_CACHE = temp_list
        print(f"✅ Loaded {len(ASSET_CACHE)} Assets!")
    except Exception as e:
        print(f"❌ Failed to load assets: {e}")

@app.route('/')
def home(): return f"🤖 Bot: {CURRENT_SYMBOL} | Active: {TRADING_ACTIVE}"

# --- NEW: MASTER SWITCH ENDPOINT ---
@app.route('/api/toggle', methods=['POST'])
def toggle_trading():
    global TRADING_ACTIVE
    TRADING_ACTIVE = not TRADING_ACTIVE
    status = "ON" if TRADING_ACTIVE else "OFF"
    print(f"🔴 SYSTEM TOGGLED: {status}")
    return jsonify({"status": "success", "active": TRADING_ACTIVE})

@app.route('/api/status')
def get_status():
    return jsonify({"active": TRADING_ACTIVE, "symbol": CURRENT_SYMBOL})

# ... (Keep /api/assets, /api/settings, /api/trades, /api/history same as before) ...
@app.route('/api/assets')
def get_assets(): return jsonify(ASSET_CACHE)

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    global CURRENT_SYMBOL
    if request.method == 'POST':
        data = request.json
        new_symbol = data.get('symbol')
        if new_symbol:
            CURRENT_SYMBOL = new_symbol.upper()
            return jsonify({"status": "success", "symbol": CURRENT_SYMBOL})
    return jsonify({"symbol": CURRENT_SYMBOL})

@app.route('/api/trades')
def trades():
    raw_data = database.get_trade_history()
    json_data = []
    for row in raw_data:
        json_data.append({
            "id": row[0], "symbol": row[1], "action": row[2], 
            "price": row[3], "timestamp": row[4]
        })
    return jsonify(json_data)

@app.route('/api/history')
def history():
    tf_str = request.args.get('timeframe', '1m')
    try:
        df = get_market_data(tf_str)
        if df.empty: return jsonify([])
        df['SMA_10'] = df['close'].rolling(window=10).mean()
        df['SMA_30'] = df['close'].rolling(window=30).mean()
        df = df.reset_index()
        chart_data = []
        for index, row in df.iterrows():
            ts = row['timestamp']
            if hasattr(ts, 'to_pydatetime'): ts = ts.to_pydatetime()
            chart_data.append({
                "time": ts.strftime('%H:%M'),
                "open": row['open'], "high": row['high'], "low": row['low'], "close": row['close'],
                "price": row['close'],
                "sma_fast": row['SMA_10'] if not pd.isna(row['SMA_10']) else None,
                "sma_slow": row['SMA_30'] if not pd.isna(row['SMA_30']) else None
            })
        return jsonify(chart_data)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/account')
def account():
    try:
        client = TradingClient(API_KEY, SECRET_KEY, paper=True)
        acc = client.get_account()
        return jsonify({
            "cash": float(acc.cash),
            "equity": float(acc.equity),
            "symbol": CURRENT_SYMBOL,
            "active": TRADING_ACTIVE # Send status to frontend
        })
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/manual', methods=['POST'])
def manual_trade():
    try:
        data = request.json
        action = data.get('action').upper()
        df = get_market_data('1m')
        current_price = df.iloc[-1]['close']
        # Manual trades ALWAYS bypass the master switch
        execute_trade(action, current_price, manual=True)
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"error": str(e)}), 500

# --- LOGIC ---
def get_market_data(tf_str='1m'):
    now = datetime.now()
    if tf_str == '15m': tf, delta = TimeFrame(15, TimeFrameUnit.Minute), timedelta(days=2)
    elif tf_str == '1h': tf, delta = TimeFrame.Hour, timedelta(days=5)
    elif tf_str == '1d': tf, delta = TimeFrame.Day, timedelta(days=30)
    else: tf, delta = TimeFrame.Minute, timedelta(minutes=200)
    start = now - delta
    
    if "/" in CURRENT_SYMBOL:
        client = CryptoHistoricalDataClient(API_KEY, SECRET_KEY)
        req = CryptoBarsRequest(symbol_or_symbols=CURRENT_SYMBOL, timeframe=tf, start=start)
        return client.get_crypto_bars(req).df
    else:
        client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
        req = StockBarsRequest(symbol_or_symbols=CURRENT_SYMBOL, timeframe=tf, start=start)
        return client.get_stock_bars(req).df

def calculate_qty(price):
    try:
        client = TradingClient(API_KEY, SECRET_KEY, paper=True)
        account = client.get_account()
        cash = float(account.cash)
        budget = cash * RISK_PER_TRADE 
        if budget < 5: return 0
        if "/" in CURRENT_SYMBOL: return round(budget / price, 4)
        else: return math.floor(budget / price) if budget >= price else round(budget / price, 3)
    except: return 1

def execute_trade(signal, price, manual=False):
    # CRITICAL CHECK: Only trade if active OR if it's a manual override
    if not TRADING_ACTIVE and not manual:
        print(f"⏸️ SIGNAL IGNORED: Bot is PAUSED. ({signal})")
        return

    client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    qty = calculate_qty(price)
    if qty == 0: return

    if signal == "BUY":
        print(f"🚀 BUY {qty} {CURRENT_SYMBOL}")
        try:
            req = MarketOrderRequest(symbol=CURRENT_SYMBOL, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
            client.submit_order(req)
            database.log_trade(CURRENT_SYMBOL, "BUY", price)
        except Exception as e: print(f"Trade Error: {e}")
            
    elif signal == "SELL":
        try:
            pos = client.get_open_position(CURRENT_SYMBOL)
            qty_to_sell = float(pos.qty)
            print(f"📉 SELL {qty_to_sell} {CURRENT_SYMBOL}")
            req = MarketOrderRequest(symbol=CURRENT_SYMBOL, qty=qty_to_sell, side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
            client.submit_order(req)
            database.log_trade(CURRENT_SYMBOL, "SELL", price)
        except: print("No position to sell.")

def run_bot():
    print(f"--- 🔍 SCANNING {CURRENT_SYMBOL} [Active: {TRADING_ACTIVE}] ---")
    database.initialize_db()
    try:
        df = get_market_data('1m')
        if len(df) < 30: return
        df['SMA_10'] = df['close'].rolling(window=10).mean()
        df['SMA_30'] = df['close'].rolling(window=30).mean()
        latest = df.iloc[-1]
        signal = "HOLD"
        if latest['SMA_10'] > latest['SMA_30']: signal = "BUY"
        elif latest['SMA_10'] < latest['SMA_30']: signal = "SELL"
        execute_trade(signal, latest['close'])
    except Exception as e: print(f"Loop Error: {e}")

def start_trading_loop():
    cache_assets()
    while True:
        run_bot()
        time.sleep(60)

if __name__ == "__main__":
    t = threading.Thread(target=start_trading_loop)
    t.daemon = True
    t.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)