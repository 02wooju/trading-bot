import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import './App.css';

function App() {
  const [trades, setTrades] = useState([]);
  const [chartData, setChartData] = useState([]); // New state for the chart
  const [loading, setLoading] = useState(true);

  // CHANGE THIS TO YOUR RENDER URL WHEN DEPLOYING
  // For now, keep it localhost to test on Windows
  //const API_URL = "http://127.0.0.1:5000"; 
   const API_URL = "https://trading-bot-bmku.onrender.com";

  useEffect(() => {
    fetchData();
    // Refresh data every 1 minute automatically
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      // 1. Get the Trades
      const tradeRes = await axios.get(`${API_URL}/api/trades`);
      setTrades(tradeRes.data);

      // 2. Get the Price History (New!)
      const historyRes = await axios.get(`${API_URL}/api/history`);
      console.log("CHART DATA:", historyRes.data);
      setChartData(historyRes.data);
      
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
        <p>Live Market Data & Execution Log</p>
      </header>

      <div className="dashboard-content">
        
        {/* SECTION 1: THE CHART */}
        <div className="chart-container">
          <h3>Market Trend (SPY)</h3>
          {loading ? <p>Loading Chart...</p> : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <XAxis dataKey="time" stroke="#8884d8" fontSize={12} tickCount={10}/>
                <YAxis domain={['dataMin', 'dataMax']} stroke="#8884d8" fontSize={12}/>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#333', border: 'none' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Line type="monotone" dataKey="price" stroke="#00d8ff" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* SECTION 2: THE TABLE */}
        <div className="table-container">
          <h3>Recent Trades</h3>
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
        </div>

      </div>
    </div>
  );
}

export default App;