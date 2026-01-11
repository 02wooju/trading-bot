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
  const [account, setAccount] = useState({ equity: 0, cash: 0, symbol: '---' });
  
  // --- UI STATES ---
  const [viewMode, setViewMode] = useState('pro'); // 'simple' or 'pro'
  const [interval, setInterval] = useState('1m'); // '1m', '15m', '1h', '1d'
  const [chartStyle, setChartStyle] = useState('line'); // 'line' or 'candle'
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isBotActive, setIsBotActive] = useState(false); // Master Switch State

  // --- WATCHLIST STATE ---
  const [watchlist, setWatchlist] = useState(() => {
    const saved = localStorage.getItem('quantWatchlist');
    return saved ? JSON.parse(saved) : ['SPY', 'BTC/USD', 'TSLA', 'NVDA', 'AAPL'];
  });

  // --- SEARCH STATES ---
  const [allAssets, setAllAssets] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  // --- API CONFIGURATION ---
  // UNCOMMENT the one you are currently using:
  const API_URL = "http://127.0.0.1:5000"; 
  // const API_URL = "https://trading-bot-bmku.onrender.com";

  // 1. INITIAL LOAD & INTERVAL
  useEffect(() => {
    fetchData();
    fetchAssets();
    const timer = setInterval(fetchData, 2000); // Fast refresh for live feel
    return () => clearInterval(timer);
  }, [interval]); // Refetch if interval changes

  // 2. SAVE WATCHLIST
  useEffect(() => {
    localStorage.setItem('quantWatchlist', JSON.stringify(watchlist));
  }, [watchlist]);

  const fetchAssets = async () => {
    try {
        const res = await axios.get(`${API_URL}/api/assets`);
        setAllAssets(res.data);
    } catch (err) { console.error("Asset DB Error", err); }
  };

  const fetchData = async () => {
    try {
      const [tradeRes, historyRes, accountRes] = await Promise.all([
        axios.get(`${API_URL}/api/trades`),
        axios.get(`${API_URL}/api/history?timeframe=${interval}`),
        axios.get(`${API_URL}/api/account`)
      ]);

      setTrades(tradeRes.data);
      setAccount(accountRes.data);
      setIsBotActive(accountRes.data.active); // Sync Switch State

      // Process Data for Candles
      const formattedHistory = historyRes.data.map(d => ({
        ...d,
        bodyTop: Math.max(d.open, d.close),
        bodyBottom: Math.min(d.open, d.close),
        bodySize: [Math.min(d.open, d.close), Math.max(d.open, d.close)]
      }));
      setChartData(formattedHistory);
      
    } catch (err) { console.error(err); }
  };

  // --- ACTIONS ---
  const handleToggle = async () => {
    try {
      const res = await axios.post(`${API_URL}/api/toggle`);
      setIsBotActive(res.data.active);
    } catch (err) { alert("Error toggling bot"); }
  };

  const loadAsset = async (symbol) => {
    try { 
        await axios.post(`${API_URL}/api/settings`, { symbol }); 
        fetchData(); 
    } catch (err) { alert("Error switching asset"); }
  };

  const handleSearch = (e) => {
    const text = e.target.value;
    setSearchTerm(text);
    if (text.length > 1) {
        const matches = allAssets.filter(asset => 
            asset.symbol.includes(text.toUpperCase()) || 
            asset.name.toLowerCase().includes(text.toLowerCase())
        ).slice(0, 50);
        setSearchResults(matches);
    } else { setSearchResults([]); }
  };

  const addToWatchlist = (symbol) => {
    if (!watchlist.includes(symbol)) setWatchlist([...watchlist, symbol]);
    setIsModalOpen(false); 
    setSearchTerm('');
    loadAsset(symbol);
  };

  const removeFromWatchlist = (e, symbol) => {
    e.stopPropagation(); 
    setWatchlist(watchlist.filter(i => i !== symbol));
  };

  const handleManualTrade = async (action) => {
    try { 
        await axios.post(`${API_URL}/api/manual`, { action }); 
        fetchData(); 
    } catch (err) { alert(err.message); }
  };

  return (
    <div className="tv-container">
      
      {/* --- HEADER --- */}
      <header className="tv-header">
        <div className="tv-brand">QUANT COMMANDER</div>
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
        
        {/* --- MAIN CHART --- */}
        <main className="tv-chart-area">
          {/* TOOLBAR */}
          <div className="chart-toolbar">
             {/* Timeframes */}
             <div className="group">
               {['1m', '15m', '1h', '1d'].map(t => (
                 <button key={t} className={interval===t?'active':''} onClick={()=>setInterval(t)}>{t.toUpperCase()}</button>
               ))}
             </div>
             <div className="divider"></div>
             {/* Chart Type */}
             <div className="group">
               <button className={chartStyle==='line'?'active':''} onClick={()=>setChartStyle('line')}>Line</button>
               <button className={chartStyle==='candle'?'active':''} onClick={()=>setChartStyle('candle')}>Candle</button>
             </div>
             <div className="divider"></div>
             {/* Indicators */}
             <div className="group">
               <button className={viewMode==='pro'?'active':''} onClick={()=>setViewMode(viewMode==='pro'?'simple':'pro')}>
                 SMA ({viewMode==='pro'?'ON':'OFF'})
               </button>
             </div>
          </div>
          
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="1 1" stroke="#2a2e39" vertical={false} />
              <XAxis dataKey="time" stroke="#787b86" fontSize={11} tickLine={false} axisLine={false} tick={{dy: 10}} />
              <YAxis domain={['auto', 'auto']} orientation="right" stroke="#787b86" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ backgroundColor: '#131722', border: '1px solid #2a2e39', color: '#fff' }} />
              
              {/* LINE MODE */}
              {chartStyle === 'line' && (
                <Area type="monotone" dataKey="close" stroke="#2962ff" strokeWidth={2} fillOpacity={0.1} fill="#2962ff" />
              )}

              {/* CANDLE MODE */}
              {chartStyle === 'candle' && (
                <Bar 
                  dataKey="bodySize" 
                  fill="#8884d8" 
                  shape={(props) => <Candlestick {...props} low={props.payload.low} high={props.payload.high} open={props.payload.open} close={props.payload.close} />}
                />
              )}

              {/* INDICATORS */}
              {viewMode === 'pro' && (
                  <>
                    <Line type="monotone" dataKey="sma_fast" stroke="#22ab94" dot={false} strokeWidth={1.5} />
                    <Line type="monotone" dataKey="sma_slow" stroke="#f23645" dot={false} strokeWidth={1.5} />
                  </>
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </main>

        {/* --- RIGHT SIDEBAR --- */}
        <aside className="tv-sidebar">
            
            {/* WATCHLIST */}
            <div className="sidebar-section watchlist">
                <div className="section-header">
                    <span>WATCHLIST</span>
                    <button className="add-btn" onClick={() => setIsModalOpen(true)}>＋</button>
                </div>
                <div className="watchlist-items">
                    {watchlist.map(sym => (
                        <div key={sym} className={`watchlist-item ${account.symbol === sym ? 'active' : ''}`} onClick={() => loadAsset(sym)}>
                            <span className="wl-sym">{sym}</span>
                            <button className="wl-delete" onClick={(e) => removeFromWatchlist(e, sym)}>✕</button>
                        </div>
                    ))}
                </div>
            </div>

            {/* ORDER PANEL */}
            <div className="sidebar-section orders">
                <div className="section-header"><span>ORDER PANEL</span></div>
                
                {/* MASTER SWITCH */}
                <button 
                  className={`toggle-system-btn ${isBotActive ? 'on' : 'off'}`} 
                  onClick={handleToggle}
                >
                  {isBotActive ? '🛑 STOP ALGO' : '▶ START ALGO'}
                </button>

                <div className="order-buttons">
                    <button className="tv-btn buy" onClick={() => handleManualTrade("BUY")}>BUY NOW</button>
                    <button className="tv-btn sell" onClick={() => handleManualTrade("SELL")}>SELL NOW</button>
                </div>
            </div>
            
            {/* HISTORY */}
            <div className="sidebar-section history">
                <div className="section-header"><span>RECENT TRADES</span></div>
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