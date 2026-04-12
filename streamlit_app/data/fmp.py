import streamlit as st
import yfinance as yf
import requests
import os
import pandas as pd
from datetime import datetime, timedelta

FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
BASE_URL = "https://financialmodelingprep.com/api/v3"

@st.cache_data(ttl=86400)
def resolve_ticker(query: str) -> str:
    query = query.strip()
    if not query: return ""
    
    # Try FMP search
    if FMP_API_KEY:
        try:
            res = requests.get(f"{BASE_URL}/search?query={query}&limit=1&apikey={FMP_API_KEY}")
            data = res.json()
            if data and isinstance(data, list):
                return data[0]["symbol"]
        except:
            pass
            
    # Fallback Yahoo Finance Search API
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        data = res.json()
        if 'quotes' in data and len(data['quotes']) > 0:
            return data['quotes'][0]['symbol']
    except:
        pass
        
    return query.upper()

@st.cache_data(ttl=86400)
def search_companies(query: str) -> list:
    if not query:
        return []
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        data = res.json()
        if 'quotes' in data:
            results = []
            for item in data['quotes'][:7]: # limit to top 7 drops
                sym = item.get('symbol', '')
                name = item.get('shortname', sym)
                if sym:
                    results.append((f"{sym} - {name}", sym))
            return results
    except:
        return []
    return []

@st.cache_data(ttl=3600)
def get_quote(ticker: str) -> dict:
    if FMP_API_KEY:
        try:
            res = requests.get(f"{BASE_URL}/quote/{ticker}?apikey={FMP_API_KEY}")
            if res.status_code == 200 and len(res.json()) > 0:
                data = res.json()[0]
                return {
                    "ticker": ticker,
                    "price": data.get("price", 0),
                    "pe": data.get("pe", 0),
                    "peForward": data.get("pe", 0), # FMP standard quote doesn't reliably have forward PE, mocking
                    "pfcf": 0 # Usually pulled from advanced metrics
                }
        except:
            pass

    # Fallback to yfinance
    try:
        t = yf.Ticker(ticker)
        price = 0
        try:
            hist = t.history(period="1d", timeout=5)
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
        except:
            pass
            
        info = {}
        try:
            info = t.info
        except:
            pass
            
        if price == 0:
            price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            
        return {
            "ticker": ticker,
            "price": float(price),
            "pe": info.get("trailingPE", 0) if isinstance(info.get("trailingPE"), (int, float)) else 0,
            "peForward": info.get("forwardPE", 0) if isinstance(info.get("forwardPE"), (int, float)) else 0,
            "pfcf": info.get("priceToFreeCashFlows", 0) if isinstance(info.get("priceToFreeCashFlows"), (int, float)) else 0
        }
    except Exception as e:
        return {"ticker": ticker, "price": 0.0, "pe": 0, "peForward": 0, "pfcf": 0}

@st.cache_data(ttl=86400)
def get_historical_financials(ticker: str, limit: int = 10) -> list:
    # Need NI, FCF, Total Assets, Revenue, Gross Margin, Net Margin, ROE, ROA, Shares, Debt, Equity, Interest Exp
    if FMP_API_KEY:
        try:
            inc = requests.get(f"{BASE_URL}/income-statement/{ticker}?limit={limit}&apikey={FMP_API_KEY}").json()
            bs = requests.get(f"{BASE_URL}/balance-sheet-statement/{ticker}?limit={limit}&apikey={FMP_API_KEY}").json()
            cf = requests.get(f"{BASE_URL}/cash-flow-statement/{ticker}?limit={limit}&apikey={FMP_API_KEY}").json()
            
            # Map them together...
            # This is complex in Python if we don't have perfect alignment.
        except:
            pass
            
    # Fallback to yfinance
    try:
        t = yf.Ticker(ticker)
        inc = t.financials.fillna(0)
        bs = t.balance_sheet.fillna(0)
        cf = t.cashflow.fillna(0)
        
        financials = []
        # yfinance columns are dates
        for date in inc.columns[:limit]:
            try:
                # Safely extract values
                def safe_get(df, index_name):
                    try:
                        return df.loc[index_name, date] if index_name in df.index else 0
                    except:
                        return 0

                revenue = safe_get(inc, "Total Revenue")
                net_income = safe_get(inc, "Net Income")
                gross_profit = safe_get(inc, "Gross Profit")
                interest_exp = abs(safe_get(inc, "Interest Expense"))
                
                fcf = safe_get(cf, "Free Cash Flow")
                
                total_assets = safe_get(bs, "Total Assets")
                total_debt = safe_get(bs, "Total Debt")
                total_equity = safe_get(bs, "Stockholders Equity")
                shares = safe_get(bs, "Ordinary Shares Number")

                financials.append({
                    "date": str(date)[:10],
                    "revenue": revenue,
                    "grossProfit": gross_profit,
                    "grossMargin": gross_profit / revenue if revenue else 0,
                    "netIncome": net_income,
                    "netMargin": net_income / revenue if revenue else 0,
                    "roe": net_income / total_equity if total_equity else 0,
                    "roa": net_income / total_assets if total_assets else 0,
                    "freeCashFlow": fcf,
                    "totalAssets": total_assets,
                    "sharesOutstanding": shares,
                    "totalDebt": total_debt,
                    "totalEquity": total_equity,
                    "interestExpense": interest_exp
                })
            except:
                continue
        return financials
    except Exception as e:
        return []

@st.cache_data(ttl=86400)
def get_company_profile(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown")
        }
    except:
        return {"sector": "Unknown", "industry": "Unknown"}

@st.cache_data(ttl=3600)
def get_historical_prices(ticker: str, days: int = 252) -> list:
    try:
        t = yf.Ticker(ticker)
        # 252 trading days is about 1 year, we grab recent 252
        data = t.history(period="1y")
        if data.empty:
            return []
        
        prices = []
        for index, row in data.iterrows():
            prices.append({
                "date": str(index)[:10],
                "close": row["Close"]
            })
        return prices[::-1] # Newest first to match JS pattern
    except:
        return []
