import yfinance as yf
import pandas as pd
from .database import save_prices, save_financials, get_connection
from .fmp import get_historical_financials
import time
import streamlit as st

# We lock to 20 representative S&P stocks + macro ETFs for the MVP ingestion 
# to avoid 12 hour fetch loops on Streamlit cloud
UNIVERSE_SUBSET = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "BRK-B", "JPM", "JNJ", "V", "PG", "UNH", "HD", "MA", "INTC", "CVX", "ABBV", "PFE", "CSCO", "PEP", "SPY", "QQQ", "IWM", "TLT", "HYG", "RSP", "^VIX", "^TNX", "^IRX"]

@st.cache_data(ttl=86400)
def ingest_historical_data():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM prices WHERE ticker = 'AAPL'")
    count = c.fetchone()[0]
    conn.close()
    
    if count > 1000:
        return False # Database already populated
        
    for ticker in UNIVERSE_SUBSET:
        try:
            # 1. Fetch Prices
            t = yf.Ticker(ticker)
            df = t.history(period="15y")
            if not df.empty:
                df = df.reset_index()
                # yfinance returns DatetimeIndex with timezone, so format it safely
                df['date'] = df['Date'].apply(lambda x: str(x)[:10])
                df['close'] = df['Close']
                df['ticker'] = ticker
                save_prices(df[['ticker', 'date', 'close']])
                
            # 2. Fetch Financials (We use our existing fallback logic in fmp.py for consistency)
            if ticker != "SPY":
                fin = get_historical_financials(ticker, limit=20) 
                if fin:
                    save_financials(ticker, fin)
                    
            time.sleep(0.5) 
        except Exception as e:
            pass
            
    return True
