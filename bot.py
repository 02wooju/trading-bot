import os
import time
import threading
import pandas as pd
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS 
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from datetime import datetime, timedelta
import database

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("APCA_API_KEY_ID")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
SYMBOL = "SPY"

# --- FLASK WEB SERVER ---
app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "🤖 Smart-Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

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
    """Returns price data PLUS the new indicators (SMA_10, SMA_30)"""
    try:
        df = get_market_data()
        
        # 1. Calculate Indicators
        df['SMA_10'] = df['close'].rolling(window=10).mean()
        df['SMA_30'] = df['close'].rolling(window=30).mean()
        
        df = df.reset_index()
        
        chart_data = []
        for index, row in df.iterrows():
            if pd.isna(row['SMA_30']): continue # Skip until we have enough data
                
            chart_data.append({
                "time": row['timestamp'].strftime('%H:%M'),
                "price": row['close'],
                "sma_fast": row['SMA_10'],
                "sma_slow": row['SMA_30']
            })
            
        return jsonify(chart_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/account')
def account():
    try:
        client = TradingClient(API_KEY, SECRET_KEY, paper=True)
        account = client.get_account()
        return jsonify({
            "cash": float(account.cash),
            "equity": float(account.equity),
            "buying_power": float(account.buying_power)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/manual', methods=['POST'])
def manual_trade():
    try:
        data = request.json
        action = data.get('action').upper()
        df = get_market_data()
        current_price = df.iloc[-1]['close']
        execute_trade(action, current_price)
        return jsonify({"status": "success", "message": f"Manual {action} executed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- TRADING LOGIC ---
def get_market_data():
    client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    now = datetime.now()
    request = StockBarsRequest(
        symbol_or_symbols=SYMBOL,
        timeframe=TimeFrame.Minute,
        start=now - timedelta(minutes=200)
    )
    bars = client.get_stock_bars(request)
    return bars.df

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def execute_trade(signal, price):
    client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    if signal == "BUY":
        print(f"🚀 BUY ORDER: {SYMBOL} @ {price}")
        try:
            order_data = MarketOrderRequest(symbol=SYMBOL, qty=1, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
            client.submit_order(order_data)
            database.log_trade(SYMBOL, "BUY", price)
        except Exception as e:
            print(f"Trade Failed: {e}")
    elif signal == "SELL":
        print(f"📉 SELL ORDER: {SYMBOL} @ {price}")
        database.log_trade(SYMBOL, "SELL", price)

def run_bot():
    print(f"--- 🤖 ANALYZING MARKET {datetime.now().strftime('%H:%M:%S')} ---")
    database.initialize_db()
    try:
        df = get_market_data()
        
        # --- NEW MATH ---
        df['SMA_10'] = df['close'].rolling(window=10).mean()
        df['SMA_30'] = df['close'].rolling(window=30).mean()
        df['RSI'] = calculate_rsi(df['close'])
        
        latest = df.iloc[-1]
        price = latest['close']
        sma_fast = latest['SMA_10']
        sma_slow = latest['SMA_30']
        rsi = latest['RSI']
        
        # --- NEW STRATEGY ---
        signal = "HOLD"
        
        # BUY CRITERIA: Fast crosses above Slow AND RSI is not Overbought (>70)
        if sma_fast > sma_slow and rsi < 70:
            signal = "BUY"
            
        # SELL CRITERIA: Fast crosses below Slow (Trend Reversal)
        elif sma_fast < sma_slow:
            signal = "SELL"
            
        print(f"Price: ${price:.2f} | Fast: {sma_fast:.2f} | Slow: {sma_slow:.2f} | RSI: {rsi:.1f} | Signal: {signal}")
        
        # Only trade if signal changes (Basic logic for now)
        execute_trade(signal, price)
        
    except Exception as e:
        print(f"❌ Error: {e}")

def start_trading_loop():
    while True:
        run_bot()
        time.sleep(60)

if __name__ == "__main__":
    t = threading.Thread(target=start_trading_loop)
    t.daemon = True
    t.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)