import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# 1. Load the secrets from the .env file
load_dotenv()

# 2. Get keys from the environment (Safe way)
API_KEY = os.getenv("PKINA4ZLCIEMVIJZOVQRTGZBJN")
SECRET_KEY = os.getenv("EgCdpRwMwpp21cTkY8qJmJgWH55miqZsDGGALgJrDNAj")

def place_trade():
    # Verify keys exist before running
    if not API_KEY or not SECRET_KEY:
        print("Error: Keys not found. Check your .env file.")
        return

    trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    account = trading_client.get_account()
    print(f"Buying Power: ${account.buying_power}")

    # 3. Prepare an order to BUY 1 share of Apple (AAPL)
    # Market Order = Buy immediately at whatever the current price is
    print("Preparing to buy 1 share of AAPL...")
    order_details = MarketOrderRequest(
        symbol="AAPL",
        qty=1,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY
    )

    # 4. Submit the order
    try:
        order = trading_client.submit_order(order_details)
        print(f"SUCCESS! Order submitted. Status: {order.status}")
        print(f"Order ID: {order.id}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    place_trade()
