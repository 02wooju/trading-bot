import os
import time
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from datetime import datetime, timedelta

# Import our new database tool
import database 

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("APCA_API_KEY_ID")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
SYMBOL = "SPY" 

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
    """Executes the trade AND logs it to the database"""
    client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    
    if signal == "BUY":
        print(f"🚀 EXECUTING BUY ORDER FOR {SYMBOL}...")
        try:
            order_data = MarketOrderRequest(
                symbol=SYMBOL,
                qty=1,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY
            )
            client.submit_order(order_data)
            print("✅ BUY Order Submitted!")
            
            # --- MEMORY STEP ---
            # Save this event to our database
            database.log_trade(SYMBOL, "BUY", price)
            
        except Exception as e:
            print(f"Trade Failed: {e}")
        
    elif signal == "SELL":
        print(f"📉 EXECUTING SELL ORDER FOR {SYMBOL}...")
        # (In a real bot, we would submit a SELL order here)
        
        # Log it anyway so we can track the signal
        database.log_trade(SYMBOL, "SELL", price)
    
    else:
        print("⏸️ HOLDING.")

def run_bot():
    print(f"--- 🤖 STARTING ANALYSIS FOR {SYMBOL} ---")
    
    # 0. Ensure DB exists
    database.initialize_db()
    
    try:
        df = get_market_data()
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        latest = df.iloc[-1]
        price = latest['close']
        sma = latest['SMA_20']
        
        print(f"Price: ${price:.2f} | SMA: ${sma:.2f}")
        
        if price > sma:
            signal = "BUY"
        elif price < sma:
            signal = "SELL"
        else:
            signal = "HOLD"
            
        print(f"Signal: {signal}")
        
        # Pass the price to execute_trade so we can log it
        execute_trade(signal, price)
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("--- 🤖 ALGO TRADER INITIALIZED ---")
    database.initialize_db()
    
    while True:
        # 1. Run the analysis
        print(f"\n[Checking Market at {datetime.now().strftime('%H:%M:%S')}]")
        run_bot()
        
        # 2. Wait 60 seconds before checking again
        # This prevents us from spamming the API and getting banned
        print("Waiting 60 seconds...")
        time.sleep(60)