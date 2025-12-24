import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import './App.css';

function App() {
  const [trades, setTrades] = useState([]);
  const [chartData, setChartData] = useState([]);
  const [account, setAccount] = useState({ equity: 0, cash: 0 }); // New Account State
  const [loading, setLoading] = useState(true);

  // SWITCH THIS when deploying!
  //const API_URL = "http://127.0.0.1:5000"; 
  const API_URL = "https://trading-bot-bmku.onrender.com";

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // Refresh every 10s (faster)
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const tradeRes = await axios.get(`${API_URL}/api/trades`);
      const historyRes = await axios.get(`${API_URL}/api/history`);
      const accountRes = await axios.get(`${API_URL}/api/account`); // New Fetch

      setTrades(tradeRes.data);
      setChartData(historyRes.data);
      setAccount(accountRes.data);
      setLoading(false);
    } catch (error) {
      console.error("Error connecting to bot:", error);
    }
  };

  // Function to handle Button Clicks
  const handleManualTrade = async (action) => {
    try {
      await axios.post(`${API_URL}/api/manual`, { action: action });
      alert(`Manual ${action} Order Sent!`);
      fetchData(); // Refresh immediately
    } catch (error) {
      alert("Trade Failed: " + error.message);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚀 Algo-Trading Commander</h1>
      </header>

      <div className="stats-bar">
        <div className="stat-card">
          <span className="stat-label">Total Equity</span>
          <span className="stat-value">${account.equity.toLocaleString()}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Available Cash</span>
          <span className="stat-value">${account.cash.toLocaleString()}</span>
        </div>
      </div>

      <div className="dashboard-content">
        
        {/* CONTROLS */}
        <div className="control-panel">
          <button className="btn btn-buy" onClick={() => handleManualTrade("BUY")}>BUY SPY (Market)</button>
          <button className="btn btn-sell" onClick={() => handleManualTrade("SELL")}>SELL SPY (Market)</button>
        </div>

        {/* CHART */}
        <div className="chart-container">
          <h3>Market Trend (SPY)</h3>
          {loading ? <p>Loading Data...</p> : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <XAxis dataKey="time" stroke="#8884d8" fontSize={12} tickCount={10}/>
                <YAxis domain={['dataMin', 'dataMax']} stroke="#8884d8" fontSize={12}/>
                <Tooltip contentStyle={{ backgroundColor: '#333', border: 'none' }} itemStyle={{ color: '#fff' }}/>
                <Line type="monotone" dataKey="price" stroke="#00d8ff" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="sma_fast" stroke="#4caf50" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="sma_slow" stroke="#ff9800" strokeWidth={2} dot={false} strokeDasharray="5 5" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* TABLE */}
        <div className="table-container">
          <h3>Execution Log</h3>
          <table className="trade-table">
            <thead>
              <tr><th>Time</th><th>Symbol</th><th>Action</th><th>Price</th></tr>
            </thead>
            <tbody>
              {trades.length === 0 ? <tr><td colSpan="4">No trades yet.</td></tr> : 
                trades.map((t) => (
                  <tr key={t.id} className={t.action === "BUY" ? "buy-row" : "sell-row"}>
                    <td>{t.timestamp}</td><td>{t.symbol}</td><td><strong>{t.action}</strong></td><td>${t.price.toFixed(2)}</td>
                  </tr>
                ))
              }
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default App;