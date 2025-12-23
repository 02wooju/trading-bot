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

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("APCA_API_KEY_ID")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
SYMBOL = "SPY" # Trading the S&P 500 ETF (More volume than AAPL after hours)

def get_market_data():
    client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    
    # Get only the last 200 minutes of data to ensure we are looking at "NOW"
    now = datetime.now()
    start_time = now - timedelta(minutes=200)
    
    request = StockBarsRequest(
        symbol_or_symbols=SYMBOL,
        timeframe=TimeFrame.Minute,
        start=start_time
    )
    
    bars = client.get_stock_bars(request)
    return bars.df

def execute_trade(signal):
    client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    account = client.get_account()
    
    print(f"💰 Buying Power: ${account.buying_power}")
    
    if signal == "BUY":
        print(f"🚀 EXECUTING BUY ORDER FOR {SYMBOL}...")
        order_data = MarketOrderRequest(
            symbol=SYMBOL,
            qty=1,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY
        )
        client.submit_order(order_data)
        print("✅ BUY Order Submitted!")
        
    elif signal == "SELL":
        # Note: You can only sell if you already own it! 
        # For this test, we will just print the message.
        print(f"📉 SIGNAL IS SELL. If we owned {SYMBOL}, we would sell now.")
    
    else:
        print("⏸️ HOLDING. No trade executed.")

def run_bot():
    print(f"--- 🤖 STARTING ANALYSIS FOR {SYMBOL} ---")
    
    try:
        # 1. Get Data
        df = get_market_data()
        
        # 2. Calculate SMA
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        latest = df.iloc[-1]
        
        price = latest['close']
        sma = latest['SMA_20']
        
        print(f"Time: {latest.name}")
        print(f"Price: ${price:.2f} | SMA: ${sma:.2f}")
        
        # 3. Decide
        if price > sma:
            signal = "BUY"
        elif price < sma:
            signal = "SELL"
        else:
            signal = "HOLD"
            
        print(f"Signal: {signal}")
        
        # 4. Execute
        execute_trade(signal)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("NOTE: If error is 'empty data', the market might be closed/quiet.")

if __name__ == "__main__":
    run_bot()