import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { 
  ComposedChart, Line, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid 
} from 'recharts';
import './App.css';

function App() {
  const [trades, setTrades] = useState([]);
  const [chartData, setChartData] = useState([]);
  const [account, setAccount] = useState({ equity: 0, cash: 0 });
  const [viewMode, setViewMode] = useState('pro'); // 'simple' or 'pro'

  // SWITCH THIS when deploying!
  //const API_URL = "http://127.0.0.1:5000"; 
  const API_URL = "https://trading-bot-bmku.onrender.com";

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Fast 5s refresh
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [tradeRes, historyRes, accountRes] = await Promise.all([
        axios.get(`${API_URL}/api/trades`),
        axios.get(`${API_URL}/api/history`),
        axios.get(`${API_URL}/api/account`)
      ]);

      setTrades(tradeRes.data);
      setChartData(historyRes.data);
      setAccount(accountRes.data);
    } catch (error) {
      console.error("Error connecting to bot:", error);
    }
  };

  const handleManualTrade = async (action) => {
    try {
      await axios.post(`${API_URL}/api/manual`, { action });
      alert(`Manual ${action} Order Sent!`);
      fetchData();
    } catch (error) {
      alert("Trade Failed: " + error.message);
    }
  };

  return (
    <div className="App">
      {/* HEADER WITH STATS */}
      <header className="App-header">
        <h1>🚀 QUANT COMMANDER <span style={{fontSize:'0.8rem', color:'#666', marginLeft:'10px'}}>v2.0</span></h1>
        <div className="stats-bar">
          <div className="stat-box">
            <span className="stat-label">Equity</span>
            <span className="stat-value">${account.equity.toLocaleString()}</span>
          </div>
          <div className="stat-box">
            <span className="stat-label">Cash</span>
            <span className="stat-value">${account.cash.toLocaleString()}</span>
          </div>
        </div>
      </header>

      {/* EXPLANATION PANEL */}
      <div className="info-panel">
        <span className="info-title">ℹ️ How This Works</span>
        This is an autonomous trading bot running a <strong>Dual-SMA Crossover Strategy</strong>. 
        It buys SPY when the Fast Moving Average (Green) crosses above the Slow Average (Orange), indicating an uptrend. 
        It filters out bad trades using the Relative Strength Index (RSI).
      </div>

      <div className="dashboard-content">
        
        {/* CHART SECTION */}
        <div className="chart-container">
          <div className="chart-header">
            <h3>Live Market Analysis (SPY)</h3>
            <div className="chart-controls">
              <button 
                className={`toggle-btn ${viewMode === 'simple' ? 'active' : ''}`} 
                onClick={() => setViewMode('simple')}>
                Simple
              </button>
              <button 
                className={`toggle-btn ${viewMode === 'pro' ? 'active' : ''}`} 
                onClick={() => setViewMode('pro')}>
                Pro (Indicators)
              </button>
            </div>
          </div>
          
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="time" stroke="#666" fontSize={11} tickCount={10}/>
              <YAxis domain={['dataMin', 'dataMax']} stroke="#666" fontSize={11} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#222', border: '1px solid #444' }} 
                itemStyle={{ color: '#fff' }}
              />
              
              {/* PRICE AREA (Like a modern fintech app) */}
              <Area 
                type="monotone" 
                dataKey="price" 
                stroke="#00d8ff" 
                fillOpacity={0.1} 
                fill="#00d8ff" 
                strokeWidth={2} 
              />

              {/* INDICATORS (Only in PRO mode) */}
              {viewMode === 'pro' && (
                <>
                  <Line type="monotone" dataKey="sma_fast" stroke="#4caf50" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="sma_slow" stroke="#ff9800" strokeWidth={2} dot={false} strokeDasharray="5 5" />
                </>
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* CONTROLS */}
        <div className="control-panel">
          <button className="btn btn-buy" onClick={() => handleManualTrade("BUY")}>Override: BUY</button>
          <button className="btn btn-sell" onClick={() => handleManualTrade("SELL")}>Override: SELL</button>
        </div>

        {/* LOGS */}
        <div className="table-container">
          <h3>Algorithmic Execution Log</h3>
          <table className="trade-table">
            <thead>
              <tr><th>Timestamp</th><th>Symbol</th><th>Signal</th><th>Fill Price</th></tr>
            </thead>
            <tbody>
              {trades.length === 0 ? <tr><td colSpan="4">Waiting for market signals...</td></tr> : 
                trades.map((t) => (
                  <tr key={t.id}>
                    <td>{t.timestamp}</td>
                    <td>{t.symbol}</td>
                    <td className={t.action === "BUY" ? "buy-row" : "sell-row"}><strong>{t.action}</strong></td>
                    <td>${t.price.toFixed(2)}</td>
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