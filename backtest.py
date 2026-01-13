import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from risk_manager import RiskManager

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("APCA_API_KEY_ID")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")

# 1. THE PORTFOLIO (Diversified Mix)
# TSLA (High Vol Tech), AAPL (Stable Tech), GLD (Gold/Defense), USO (Oil/Energy), SPY (Market)
TICKERS = ["TSLA", "AAPL", "GLD", "USO", "SPY"]
INITIAL_CAPITAL = 80000 
START_DATE = datetime(2023, 1, 1)

def fetch_data(tickers):
    print(f"⏳ Fetching data for Portfolio: {tickers}...")
    client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    req = StockBarsRequest(symbol_or_symbols=tickers, timeframe=TimeFrame.Hour, start=START_DATE)
    bars = client.get_stock_bars(req)
    
    # FIX: Get the MultiIndex DataFrame directly
    multi_df = bars.df 
    
    data_map = {}
    for ticker in tickers:
        try:
            # Extract data for this specific ticker using Cross Section (xs)
            # level=0 is the 'symbol' index
            df = multi_df.xs(ticker, level=0).copy()
            
            # Reset index so 'timestamp' becomes a normal column for our loop
            df = df.reset_index()
            
            # Calculate Indicators
            df['SMA_20'] = df['close'].rolling(window=20).mean()
            df['STD_20'] = df['close'].rolling(window=20).std()
            df['Upper'] = df['SMA_20'] + (2 * df['STD_20'])
            df['Lower'] = df['SMA_20'] - (2 * df['STD_20'])
            df['SMA_200'] = df['close'].rolling(window=200).mean()
            
            data_map[ticker] = df
        except KeyError:
            print(f"⚠️ Warning: No data found for {ticker}")
            
    return data_map

def run_portfolio_backtest(data_map):
    print("⚙️ Running PORTFOLIO SIMULATION (Aligned)...")
    
    # 1. ALIGN DATA TO COMMON INDEX (Crucial Fix)
    print("   -> Aligning timestamps across all assets...")
    
    # Set index to timestamp for all frames so we can lookup by Date
    for t in data_map:
        if 'timestamp' in data_map[t].columns:
            data_map[t] = data_map[t].set_index('timestamp')
    
    # Find the intersection (Times where ALL stocks have data)
    # This prevents the "IndexError" crash
    common_index = data_map[TICKERS[0]].index
    for t in TICKERS[1:]:
        common_index = common_index.intersection(data_map[t].index)
    
    # Sort just in case
    common_index = common_index.sort_values()
    print(f"   -> Found {len(common_index)} common trading hours.")

    # 2. STATE VARIABLES
    risk_manager = RiskManager(INITIAL_CAPITAL, daily_risk_limit=0.01, max_drawdown_limit=0.06)
    balance = INITIAL_CAPITAL
    positions = {ticker: {'shares': 0, 'type': None, 'entry': 0} for ticker in TICKERS}
    equity_curve = []
    
    # 3. LOOP THROUGH TIME (Using Dates, not Numbers)
    # Skip first 200 hours for SMA_200 warm-up
    trading_hours = common_index[200:] 
    
    for current_time in trading_hours:
        # A. CALCULATE TOTAL EQUITY
        current_equity = balance
        for ticker in TICKERS:
            # Safe Lookup by Time
            price = data_map[ticker].loc[current_time]['close']
            pos = positions[ticker]
            if pos['type'] == 'LONG': current_equity += (pos['shares'] * price)
            elif pos['type'] == 'SHORT': current_equity -= (abs(pos['shares']) * price)
            
        equity_curve.append(current_equity)

        # B. CHECK RISK MANAGER
        # We pass the actual Timestamp object
        allowed, message = risk_manager.check_trade_allowed(current_time, current_equity)
        
        if not allowed:
            # Force Close Everything if Daily Limit Hit
            for ticker in TICKERS:
                pos = positions[ticker]
                if pos['shares'] != 0:
                    price = data_map[ticker].loc[current_time]['close']
                    if pos['type'] == 'LONG': balance += (pos['shares'] * price)
                    elif pos['type'] == 'SHORT': balance -= (abs(pos['shares']) * price)
                    pos['shares'] = 0; pos['type'] = None
            continue # Skip to next hour

        # C. TRADING LOOP FOR EACH TICKER
        for ticker in TICKERS:
            # Access Row by Time
            row = data_map[ticker].loc[current_time] 
            price = row['close']
            pos = positions[ticker]

            # 1. MANAGE EXISITING POSITIONS
            STOP_PCT = 0.015
            TARGET_PCT = 0.06
            
            if pos['type'] == 'LONG':
                stop = pos['entry'] * (1 - STOP_PCT)
                target = pos['entry'] * (1 + TARGET_PCT)
                
                if row['low'] <= stop: 
                    balance += (pos['shares'] * stop)
                    pos['shares'] = 0; pos['type'] = None
                elif row['high'] >= target: 
                    balance += (pos['shares'] * target)
                    pos['shares'] = 0; pos['type'] = None
                elif price > row['SMA_20']:
                    balance += (pos['shares'] * price)
                    pos['shares'] = 0; pos['type'] = None

            elif pos['type'] == 'SHORT':
                stop = pos['entry'] * (1 + STOP_PCT)
                target = pos['entry'] * (1 - TARGET_PCT)
                
                if row['high'] >= stop:
                    balance -= (abs(pos['shares']) * stop)
                    pos['shares'] = 0; pos['type'] = None
                elif row['low'] <= target:
                    balance -= (abs(pos['shares']) * target)
                    pos['shares'] = 0; pos['type'] = None
                elif price < row['SMA_20']:
                    balance -= (abs(pos['shares']) * price)
                    pos['shares'] = 0; pos['type'] = None

            # 2. ENTRY LOGIC (If Flat)
            if pos['type'] is None:
                # ALLOCATION: Equal Weight (20% of Equity per stock)
                # Trade Size: Use 15% of that chunk (Safety Buffer)
                # Effective Risk: 3% of Account per stock
                allocation = current_equity / len(TICKERS) 
                trade_amt = allocation * 0.45 
                
                if price < row['Lower'] and price > row['SMA_200']:
                    shares = trade_amt // price
                    balance -= (shares * price)
                    pos['shares'] = shares; pos['type'] = 'LONG'; pos['entry'] = price
                
                elif price > row['Upper'] and price < row['SMA_200']:
                    shares = trade_amt // price
                    balance += (shares * price)
                    pos['shares'] = -shares; pos['type'] = 'SHORT'; pos['entry'] = price

    # D. REPORTING
    final_eq = equity_curve[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    series = pd.Series(equity_curve)
    max_equity = series.cummax()
    dd = (series - max_equity) / max_equity * 100
    max_dd = dd.min()

    print("\n" + "="*40)
    print(f"🌍 PORTFOLIO RESULTS ({len(TICKERS)} Assets)")
    print("="*40)
    print(f"End Balance:    ${final_eq:,.2f}")
    print(f"Total Return:   {ret:.2f}%")
    print(f"Max Drawdown:   {max_dd:.2f}% (Limit: -6%)")
    
    if max_dd > -6:
        print("🏆 STATUS: PASSED & FUNDED.")
    else:
        print("❌ STATUS: FAILED.")
    print("="*40)

    plt.figure(figsize=(12,6))
    plt.plot(equity_curve, label='Portfolio Equity')
    plt.title(f"Diversified Portfolio: {TICKERS}")
    plt.show()

if __name__ == "__main__":
    data = fetch_data(TICKERS)
    run_portfolio_backtest(data)