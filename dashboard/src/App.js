import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  // We are running locally on Windows, so we talk to localhost:5000
  const API_URL = "http://127.0.0.1:5000"; 

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    try {
      console.log("Fetching trades from:", `${API_URL}/api/trades`);
      const response = await axios.get(`${API_URL}/api/trades`);
      console.log("Data received:", response.data);
      setTrades(response.data);
      setLoading(false);
    } catch (error) {
      console.error("Error connecting to bot:", error);
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚀 Algo-Trading Dashboard</h1>
        <p>Live Trade History</p>
      </header>

      <div className="trade-container">
        {loading ? (
          <p>Loading trades...</p>
        ) : (
          <table className="trade-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Action</th>
                <th>Price</th>
              </tr>
            </thead>
            <tbody>
              {trades.length === 0 ? (
                <tr><td colSpan="4">No trades recorded yet.</td></tr>
              ) : (
                trades.map((trade) => (
                  <tr key={trade.id} className={trade.action === "BUY" ? "buy-row" : "sell-row"}>
                    <td>{trade.timestamp}</td>
                    <td>{trade.symbol}</td>
                    <td><strong>{trade.action}</strong></td>
                    <td>${trade.price.toFixed(2)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default App;