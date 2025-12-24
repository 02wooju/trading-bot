import os
import time
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS  # <--- THIS IS THE KEY
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
CORS(app)  # <--- THIS UNBLOCKS THE BROWSER

@app.route('/')
def home():
    return "🤖 Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/api/trades')
def trades():
    """Returns trade history as JSON for the React Frontend"""
    raw_data = database.get_trade_history()
    json_data = []
    for row in raw_data:
        json_data.append({
            "id": row[0],
            "symbol": row[1],
            "action": row[2],
            "price": row[3],
            "timestamp": row[4]
        })
    return jsonify(json_data)

@app.route('/api/history')
def history():
    """Returns the last 200 minutes of price data for the chart"""
    try:
        df = get_market_data()
        
        # FIX: Flatten the data structure so it's easier to read
        df = df.reset_index()
        
        chart_data = []
        for index, row in df.iterrows():
            # safely get the time and price
            time_val = row['timestamp']
            price_val = row['close']
            
            chart_data.append({
                "time": time_val.strftime('%H:%M'),  # Format as "14:30"
                "price": price_val
            })
            
        return jsonify(chart_data)
        
    except Exception as e:
        print(f"❌ CHART ERROR: {e}") # This will show us the error in the terminal
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/account')
def account():
    """Returns live account balance and equity"""
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
    """Allows the Frontend to force a trade"""
    try:
        data = request.json
        action = data.get('action').upper() # "BUY" or "SELL"
        
        # We reuse our existing logic!
        # Fetch current price just for logging
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
    start_time = now - timedelta(minutes=200)
    request = StockBarsRequest(
        symbol_or_symbols=SYMBOL,
        timeframe=TimeFrame.Minute,
        start=start_time
    )
    bars = client.get_stock_bars(request)
    return bars.df

def execute_trade(signal, price):
    client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    if signal == "BUY":
        print(f"🚀 EXECUTING BUY ORDER FOR {SYMBOL}...")
        try:
            order_data = MarketOrderRequest(
                symbol=SYMBOL, qty=1, side=OrderSide.BUY, time_in_force=TimeInForce.DAY
            )
            client.submit_order(order_data)
            database.log_trade(SYMBOL, "BUY", price)
        except Exception as e:
            print(f"Trade Failed: {e}")
    elif signal == "SELL":
        print(f"📉 SIGNAL SELL {SYMBOL}")
        database.log_trade(SYMBOL, "SELL", price)

def run_bot():
    print(f"--- 🤖 CHECKING MARKET {datetime.now().strftime('%H:%M:%S')} ---")
    database.initialize_db()
    try:
        df = get_market_data()
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        latest = df.iloc[-1]
        price = latest['close']
        sma = latest['SMA_20']
        
        if price > sma:
            signal = "BUY"
        elif price < sma:
            signal = "SELL"
        else:
            signal = "HOLD"
            
        print(f"Price: ${price:.2f} | SMA: ${sma:.2f} | Signal: {signal}")
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