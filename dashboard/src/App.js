import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { 
  ComposedChart, Line, Area, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid 
} from 'recharts';
import './App.css';

// --- CUSTOM CANDLESTICK SHAPE ---
const Candlestick = (props) => {
  const { x, y, width, height, low, high, open, close } = props;
  const isGreen = close > open;
  const color = isGreen ? "#22ab94" : "#f23645";
  const ratio = Math.abs(height / (open - close)); 
  
  // Calculate wick positions
  const yHigh = y - ((high - Math.max(open, close)) * ratio);
  const yLow = y + height + ((Math.min(open, close) - low) * ratio);

  return (
    <g stroke={color} fill={color} strokeWidth="2">
      <path d={`M ${x + width / 2},${yHigh} L ${x + width / 2},${yLow}`} />
      <rect x={x} y={y} width={width} height={height} stroke="none" />
    </g>
  );
};

function App() {
  // --- CORE DATA STATES ---
  const [trades, setTrades] = useState([]);
  const [chartData, setChartData] = useState([]);
  const [positions, setPositions] = useState([]); // New state for Active Positions
  const [account, setAccount] = useState({ equity: 0, cash: 0, symbol: '---' });
  
  // UI STATES
  const [isBotActive, setIsBotActive] = useState(false);
  const [watchlist, setWatchlist] = useState(['BTC/USD', 'ETH/USD', 'SPY', 'TSLA', 'NVDA']);

  //const API_URL = "http://127.0.0.1:5001"; 
  const API_URL = "https://trading-bot-bmku.onrender.com";

  // 1. INITIAL LOAD & INTERVAL
  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 2000); // 2s Refresh
    return () => clearInterval(timer);
  }, []);

  const fetchData = async () => {
    try {
      const [tradeRes, historyRes, accountRes, posRes] = await Promise.all([
        axios.get(`${API_URL}/api/trades`),
        axios.get(`${API_URL}/api/history`),
        axios.get(`${API_URL}/api/account`),
        axios.get(`${API_URL}/api/positions`) // Fetch open trades
      ]);
      setTrades(tradeRes.data);
      setAccount(accountRes.data);
      setPositions(posRes.data);
      setIsBotActive(accountRes.data.active);
    } catch (err) { console.error(err); }
  };

  const loadAsset = async (symbol) => {
    try { 
        await axios.post(`${API_URL}/api/settings`, { symbol }); 
        fetchData(); 
    } catch (err) { alert("Error switching asset"); }
  };

  const handleToggle = async () => {
    try {
      const res = await axios.post(`${API_URL}/api/toggle`);
      setIsBotActive(res.data.active);
    } catch (err) { alert("Error"); }
  };

  const handleManualTrade = async (action) => {
    try { await axios.post(`${API_URL}/api/manual`, { action }); fetchData(); } 
    catch (err) { alert(err.message); }
  };

  return (
    <div className="tv-container">
      {/* HEADER */}
      <header className="tv-header">
        <div className="tv-brand">QUANT COMMANDER <span className="pro-badge">PRO</span></div>
        <div className="tv-ticker-info">
          <span className="ticker-name">{account.symbol}</span>
          <span className="ticker-badge">LIVE</span>
        </div>
        <div className="tv-stats">
            <span className="stat-label">EQUITY:</span>
            <span className="stat-value">${account.equity.toLocaleString()}</span>
        </div>
      </header>

      <div className="tv-body">
        {/* CHART */}
        <main className="tv-chart-area">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="1 1" stroke="#2a2e39" vertical={false} />
              <XAxis dataKey="time" stroke="#787b86" fontSize={11} tickLine={false} axisLine={false} tick={{dy: 10}} />
              <YAxis domain={['auto', 'auto']} orientation="right" stroke="#787b86" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ backgroundColor: '#131722', border: '1px solid #2a2e39', color: '#fff' }} />
              
              <Area type="monotone" dataKey="close" stroke="#2962ff" strokeWidth={2} fillOpacity={0.1} fill="#2962ff" />
              <Line type="monotone" dataKey="sma_fast" stroke="#22ab94" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="sma_slow" stroke="#f23645" dot={false} strokeWidth={1.5} />
            </ComposedChart>
          </ResponsiveContainer>
        </main>

        {/* SIDEBAR */}
        <aside className="tv-sidebar">
            <div className="sidebar-section watchlist">
                <div className="section-header"><span>WATCHLIST</span></div>
                <div className="watchlist-items">
                    {watchlist.map(sym => (
                        <div key={sym} className={`watchlist-item ${account.symbol === sym ? 'active' : ''}`} onClick={() => loadAsset(sym)}>
                            <span className="wl-sym">{sym}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* NEW: OPEN POSITIONS */}
            <div className="sidebar-section positions">
                <div className="section-header"><span>OPEN POSITIONS</span></div>
                <div className="positions-list">
                    {positions.length === 0 ? (
                        <div className="empty-msg">No active trades</div>
                    ) : (
                        positions.map((pos) => (
                            <div key={pos.symbol} className="pos-item">
                                <div className="pos-header">
                                    <span className="pos-sym">{pos.symbol}</span>
                                    <span className="pos-time">{pos.entry_time}</span>
                                </div>
                                <div className="pos-details">
                                    <div className="pos-row">
                                        <span>Entry:</span> <span>${pos.entry_price.toFixed(2)}</span>
                                    </div>
                                    <div className="pos-row">
                                        <span>Current:</span> <span>${pos.current_price.toFixed(2)}</span>
                                    </div>
                                    <div className={`pos-row pl ${pos.pl >= 0 ? 'win' : 'loss'}`}>
                                        <span>P/L:</span> 
                                        <span>${pos.pl.toFixed(2)} ({pos.pl_pct.toFixed(2)}%)</span>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            <div className="sidebar-section orders">
                <div className="section-header"><span>CONTROLS</span></div>
                <button className={`toggle-system-btn ${isBotActive ? 'on' : 'off'}`} onClick={handleToggle}>
                  {isBotActive ? '🛑 STOP ALGO' : '▶ START ALGO'}
                </button>
                <div className="order-buttons">
                    <button className="tv-btn buy" onClick={() => handleManualTrade("BUY")}>BUY</button>
                    <button className="tv-btn sell" onClick={() => handleManualTrade("SELL")}>SELL</button>
                </div>
            </div>
            
            <div className="sidebar-section history">
                <div className="section-header"><span>TRADE HISTORY</span></div>
                <div className="history-list">
                    {trades.slice(0, 10).map((t) => (
                        <div key={t.id} className="history-item">
                            <span className={`badge ${t.action}`}>{t.action}</span>
                            <span className="hist-sym">{t.symbol}</span>
                            <span className="hist-price">${t.price.toFixed(2)}</span>
                        </div>
                    ))}
                </div>
            </div>
        </aside>
      </div>

      {/* --- MODAL --- */}
      {isModalOpen && (
          <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
              <div className="modal-content" onClick={e => e.stopPropagation()}>
                  <div className="modal-header">
                      <h3>Add Symbol</h3>
                      <button className="close-btn" onClick={() => setIsModalOpen(false)}>✕</button>
                  </div>
                  <input autoFocus type="text" placeholder="Search (e.g. AAPL)..." value={searchTerm} onChange={handleSearch} className="modal-search"/>
                  <div className="modal-results">
                      {searchResults.map(asset => (
                          <div key={asset.symbol} className="result-item" onClick={() => addToWatchlist(asset.symbol)}>
                              <span className="res-sym">{asset.symbol}</span>
                              <span className="res-name">{asset.name}</span>
                              <span className="res-add">＋</span>
                          </div>
                      ))}
                  </div>
              </div>
          </div>
      )}
    </div>
  );
}

export default App;