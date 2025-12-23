import sqlite3
from datetime import datetime

# Name of our database file
DB_NAME = "trading_journal.db"

def initialize_db():
    """Creates the database and the table if they don't exist"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create a table to store our trades
    # We store: Symbol, Action (BUY/SELL), Price, and Time
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized and ready.")

def log_trade(symbol, action, price):
    """Saves a trade to the database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute('''
        INSERT INTO trades (symbol, action, price, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (symbol, action, price, timestamp))
    
    conn.commit()
    conn.close()
    print(f"📝 Trade logged to DB: {action} {symbol} @ ${price}")

def get_trade_history():
    """Fetches all past trades so we can see them"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM trades ORDER BY id DESC")
    rows = cursor.fetchall()
    
    conn.close()
    return rows

# Run this once when the file is run directly to set it up
if __name__ == "__main__":
    initialize_db()