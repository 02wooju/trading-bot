import os
import time
import threading
from flask import Flask
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

# --- FLASK WEB SERVER (For Free Tier) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

# --- TRADING LOGIC (Same as before) ---
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

# --- BACKGROUND LOOP ---
def start_trading_loop():
    while True:
        run_bot()
        # Wait 60 seconds
        time.sleep(60)

# --- STARTUP ---
if __name__ == "__main__":
    # 1. Start the trading bot in a separate thread
    t = threading.Thread(target=start_trading_loop)
    t.daemon = True
    t.start()
    
    # 2. Start the Flask web server (blocks the main thread)
    # This ensures Render sees a "Web Service" running
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)