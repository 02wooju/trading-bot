import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Import your Risk Manager
from risk_manager import RiskManager

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("APCA_API_KEY_ID")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")

# FUNDED PORTFOLIO SETTINGS
TICKERS = ["TSLA", "AAPL", "GLD", "USO", "SPY"]
PAPER_MODE = True  # Set to False when you get a real Funded Account

# Initialize Clients
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=PAPER_MODE)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

# Initialize Risk Manager (We update the balance inside the loop)
# We assume $100k start for paper, but the code adapts to actual account value
risk_manager = RiskManager(initial_balance=100000, daily_risk_limit=0.01, max_drawdown_limit=0.06)

def get_account_equity():
    account = trading_client.get_account()
    return float(account.equity)

def fetch_latest_bars(tickers):
    """Fetch the last 200 hours of data for all tickers to calculate indicators"""
    print(f"⏳ Fetching live market data...")
    end_time = datetime.now()
    start_time = end_time - timedelta(days=20) # Get enough buffer for 200 SMA
    
    req = StockBarsRequest(
        symbol_or_symbols=tickers,
        timeframe=TimeFrame.Hour,
        start=start_time,
        end=end_time
    )
    bars = data_client.get_stock_bars(req)
    
    # Process into Dictionary of DataFrames
    data_map = {}
    multi_df = bars.df
    
    for ticker in tickers:
        try:
            df = multi_df.xs(ticker, level=0).copy()
            df = df.reset_index()
            
            # Calculate Indicators
            df['SMA_20'] = df['close'].rolling(window=20).mean()
            df['STD_20'] = df['close'].rolling(window=20).std()
            df['Upper'] = df['SMA_20'] + (2 * df['STD_20'])
            df['Lower'] = df['SMA_20'] - (2 * df['STD_20'])
            df['SMA_200'] = df['close'].rolling(window=200).mean()
            
            data_map[ticker] = df
        except Exception as e:
            print(f"⚠️ Could not process {ticker}: {e}")
            
    return data_map

def close_position(ticker, qty, side):
    """Closes a position by placing an opposing order"""
    print(f"CLOSING {ticker} ({qty} shares)...")
    try:
        req = MarketOrderRequest(
            symbol=ticker,
            qty=abs(qty),
            side=OrderSide.SELL if side == 'LONG' else OrderSide.BUY,
            time_in_force=TimeInForce.DAY
        )
        trading_client.submit_order(order_data=req)
    except Exception as e:
        print(f"❌ Failed to close {ticker}: {e}")

def enter_position(ticker, side, equity):
    """Calculates size and places a new trade"""
    # SIZE CALCULATION (From Backtest: 45% of Allocation)
    # 5 Tickers = 20% Allocation each. 45% of 20% = 9% Total Risk per trade.
    allocation = equity / len(TICKERS)
    trade_amt = allocation * 0.45 
    
    # Get current price
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Minute, limit=1)
    bar = data_client.get_stock_bars(req).df.iloc[-1]
    price = bar['close']
    
    qty = int(trade_amt // price)
    if qty < 1:
        print(f"⚠️ {ticker}: Insufficient funds for 1 share.")
        return

    print(f"🚀 ENTERING {side} {ticker}: {qty} shares @ ${price}")
    try:
        req = MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=OrderSide.BUY if side == 'LONG' else OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        trading_client.submit_order(order_data=req)
    except Exception as e:
        print(f"❌ Order Failed: {e}")

def run_bot_cycle():
    print(f"\n--- 🤖 BOT CYCLE START: {datetime.now()} ---")
    
    # 1. CHECK ACCOUNT & RISK
    equity = get_account_equity()
    today = datetime.now()
    allowed, msg = risk_manager.check_trade_allowed(today, equity)
    
    print(f"💰 Equity: ${equity:,.2f} | Status: {msg}")
    
    if not allowed:
        print("🛑 RISK MANAGER TRIGGERED. HALTING TRADING.")
        # Optional: Add logic here to liquidate all positions if risk hit
        return

    # 2. GET POSITIONS
    alpaca_positions = trading_client.get_all_positions()
    pos_map = {p.symbol: p for p in alpaca_positions}

    # 3. GET DATA
    data_map = fetch_latest_bars(TICKERS)
    
    # 4. LOOP THROUGH TICKERS
    for ticker in TICKERS:
        if ticker not in data_map: continue
        
        df = data_map[ticker]
        if df.empty: continue
        
        # Get Latest Candle
        row = df.iloc[-1] 
        price = row['close']
        
        # Check if we have a position
        has_position = ticker in pos_map
        current_qty = float(pos_map[ticker].qty) if has_position else 0
        
        # Determine Current Side (Long/Short) based on qty
        # Alpaca returns negative qty for shorts
        pos_type = None
        if current_qty > 0: pos_type = 'LONG'
        elif current_qty < 0: pos_type = 'SHORT'
        
        # --- LOGIC ---
        
        # A. MANAGE EXISTING POSITIONS
        if pos_type == 'LONG':
            if price > row['SMA_20']:
                print(f"🔵 {ticker}: Mean Reversion Exit Reached (Price > SMA). Closing.")
                close_position(ticker, current_qty, 'LONG')
                
        elif pos_type == 'SHORT':
            if price < row['SMA_20']:
                print(f"🔵 {ticker}: Mean Reversion Exit Reached (Price < SMA). Closing.")
                close_position(ticker, current_qty, 'SHORT')

        # B. CHECK NEW ENTRIES (Only if flat)
        if not has_position:
            # LONG SIGNAL
            if price < row['Lower'] and price > row['SMA_200']:
                print(f"🟢 {ticker}: Oversold in Uptrend. BUY SIGNAL.")
                enter_position(ticker, 'LONG', equity)
                
            # SHORT SIGNAL
            elif price > row['Upper'] and price < row['SMA_200']:
                print(f"🟣 {ticker}: Overbought in Downtrend. SELL SIGNAL.")
                enter_position(ticker, 'SHORT', equity)
            else:
                print(f"⚪ {ticker}: No Signal.")

if __name__ == "__main__":
    print("🤖 PORTFOLIO TRADING BOT INITIALIZED")
    print(f"watching: {TICKERS}")
    
    while True:
        try:
            run_bot_cycle()
            # Sleep for 1 hour (3600 seconds)
            # For testing, you can reduce this, but for live, stick to 1H candles
            print("💤 Sleeping for 60 minutes...")
            time.sleep(3600) 
        except Exception as e:
            print(f"⚠️ CRITICAL ERROR: {e}")
            time.sleep(60) # Wait 1 min before retry