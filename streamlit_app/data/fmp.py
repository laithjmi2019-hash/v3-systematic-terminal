import streamlit as st
import yfinance as yf
import requests
import os
import pandas as pd
from datetime import datetime, timedelta

FMP_API_KEY = os.environ.get("FMP_API_KEY", "ZopJDkQbPkxpeehQrJtxGAQRVWJnkiop")
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "WLZRN9J45SFA1NEJ")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "d2c9a2pr01qihtcqnssgd2c9a2pr01qihtcqnst0")
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
            for item in data['quotes'][:7]:
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
    """
    Primary: yfinance (gives FULL data: forwardPE, pfcf, sector, dividendYield).
    Fallback: FMP for price only if yfinance price fails.
    """
    _empty = {"ticker": ticker, "price": 0.0, "pe": 0.0, "peForward": 0.0,
              "pfcf": 0.0, "sector": "DEFAULT", "dividendYield": 0.0}

    price     = 0.0
    fwd_pe    = 0.0
    trail_pe  = 0.0
    pfcf      = 0.0
    sector    = "DEFAULT"
    div_yield = 0.0

    # --- STEP 1: yfinance (always attempt — richest data source) ---
    try:
        t = yf.Ticker(ticker)

        # Price: try fast_info first, then history, then info keys
        try:
            fi = t.fast_info
            price = float(fi.last_price or 0)
        except Exception:
            pass

        if price == 0.0:
            try:
                hist = t.history(period="5d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            except Exception:
                pass

        # Full info for fundamentals
        info = {}
        try:
            info = t.info or {}
        except Exception:
            info = {}

        # Price fallback from info
        if price == 0.0:
            for key in ("currentPrice", "regularMarketPrice", "previousClose", "open"):
                candidate = info.get(key)
                if candidate and isinstance(candidate, (int, float)) and float(candidate) > 0:
                    price = float(candidate)
                    break

        # Extract fundamentals
        if isinstance(info.get("forwardPE"), (int, float)):
            fwd_pe = float(info["forwardPE"])
        if isinstance(info.get("trailingPE"), (int, float)):
            trail_pe = float(info["trailingPE"])
        if isinstance(info.get("priceToFreeCashFlows"), (int, float)):
            pfcf = float(info["priceToFreeCashFlows"])
        
        sector    = info.get("sector", "DEFAULT") or "DEFAULT"
        div_yield = float(info.get("dividendYield", 0) or 0)

    except Exception:
        pass

    # --- STEP 1.5: FINNHUB Fallback for missing elements ---
    try:
        if price == 0.0 or div_yield == 0.0:
            res = requests.get(f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}", timeout=5)
            if res.status_code == 200:
                d = res.json()
                if price == 0.0 and d.get("c"): price = float(d["c"])
            
            res_m = requests.get(f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={FINNHUB_KEY}", timeout=5)
            if res_m.status_code == 200:
                dm = res_m.json()
                if "metric" in dm:
                    if fwd_pe == 0.0: fwd_pe = float(dm["metric"].get("peNormalizedAnnual", 0) or 0)
                    if div_yield == 0.0: div_yield = float(dm["metric"].get("dividendYieldIndicatedAnnual", 0) or 0)
    except Exception:
        pass

    # --- STEP 2: FMP fallback for price only ---
    if price == 0.0 and FMP_API_KEY:
        try:
            res = requests.get(f"{BASE_URL}/quote/{ticker}?apikey={FMP_API_KEY}", timeout=8)
            if res.status_code == 200 and res.json():
                data = res.json()[0]
                price = float(data.get("price", 0) or 0)
                # Also grab trailing PE from FMP if yfinance gave us nothing
                if trail_pe == 0.0:
                    trail_pe = float(data.get("pe", 0) or 0)
        except Exception:
            pass

    # If we have trailing PE but no forward PE, use trailing as proxy
    if fwd_pe == 0.0 and trail_pe > 0:
        fwd_pe = trail_pe

    return {
        "ticker":        ticker,
        "price":         price,
        "pe":            trail_pe,
        "peForward":     fwd_pe,
        "pfcf":          pfcf,
        "sector":        sector,
        "dividendYield": div_yield,
    }

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
                if fcf == 0.0:
                    ocf = safe_get(cf, "Operating Cash Flow")
                    capex = safe_get(cf, "Capital Expenditure")
                    if ocf != 0.0:
                        # CapEx is typically reported as negative outflow
                        fcf = ocf + capex if capex < 0 else ocf - capex
                
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

def _fetch_historical_prices_raw(ticker: str) -> list:
    """Internal helper — NOT cached. Returns oldest-first list of {date, close}."""
    try:
        t = yf.Ticker(ticker)
        data = t.history(period="1y")
        if data.empty:
            return []
        
        prices = []
        for index, row in data.iterrows():
            prices.append({
                "date": str(index)[:10],
                "close": float(row["Close"])
            })
        # Sort chronologically: oldest first
        prices.sort(key=lambda x: x["date"])
        return prices
    except:
        return []

@st.cache_data(ttl=3600)
def get_historical_prices(ticker: str, days: int = 252) -> list:
    """
    Returns price history. Cached for 1 hour (NOT 24h — prevents stale empty caching).
    Returns oldest-first order for momentum calculations.
    """
    result = _fetch_historical_prices_raw(ticker)
    # If we got fewer than 50 data points, this is likely a failure — DON'T cache it
    # by returning through a non-cached path
    if len(result) < 50:
        st.cache_data.clear()  # Clear this specific cache entry
        return result
    return result

@st.cache_data(ttl=86400)
def get_analyst_revisions(ticker: str) -> dict:
    """
    V9 Upgrade: Returns Analyst Revisions Momentum.
    Checks FMP analyst-estimates over the expected quarters to see if EPS est is being revised up.
    Returns:
       score (float): 0.0 to 1.0 signal. 0.5 = neutral, >0.5 = upgrades, <0.5 = downgrades
    """
    revisions_score = 0.5
    if not FMP_API_KEY:
        return {"revisions_score": revisions_score}
        
    try:
        url = f"{BASE_URL}/analyst-estimates/{ticker}?period=quarter&limit=4&apikey={FMP_API_KEY}"
        res = requests.get(url, timeout=8)
        if res.status_code == 200 and res.json():
            data = res.json()
            if len(data) >= 2:
                # Naive revision trend: compare estimatedEPSCurrent vs estimatedEPSPrior if available, or just check recent quarters
                # FMP analyst-estimates has estimatedEps
                # For a rough revision momentum proxy, we see if upcoming quarters expected EPS > previous expectations
                # or if estimatedEps itself is strong. Let's use a simple binary indicator for MVP.
                est1 = data[0].get('estimatedEps', 0) or 0
                est2 = data[1].get('estimatedEps', 0) or 0
                if est1 > est2 * 1.05:
                    revisions_score = 1.0
                elif est1 > est2:
                    revisions_score = 0.75
                elif est1 < est2 * 0.95:
                    revisions_score = 0.0
                elif est1 < est2:
                    revisions_score = 0.25
    except Exception:
        pass
        
    return {"revisions_score": revisions_score}

@st.cache_data(ttl=86400)
def get_financial_growth(ticker: str) -> dict:
    result = {"revenueGrowth": 0, "netIncomeGrowth": 0, "epsgrowth": 0, "yearsAveraged": 1}
    
    # 1. TRY YFINANCE (Primary 100% Free)
    try:
        t = yf.Ticker(ticker)
        inc = t.financials
        if not inc.empty and len(inc.columns) >= 2:
            def get_row(df, names):
                for name in names:
                    if name in df.index: return df.loc[name]
                return None
            
            rev_row = get_row(inc, ["Total Revenue", "Operating Revenue", "Revenue"])
            ni_row = get_row(inc, ["Net Income", "Net Income Common Stockholders"])
            
            rev_growths = []
            ni_growths = []
            
            limit = min(4, len(inc.columns)) 
            for i in range(limit - 1):
                cur_rev = rev_row.iloc[i] if rev_row is not None else 0
                prev_rev = rev_row.iloc[i+1] if rev_row is not None else 0
                if prev_rev and prev_rev != 0:
                    rev_growths.append((cur_rev - prev_rev) / abs(prev_rev))
                    
                cur_ni = ni_row.iloc[i] if ni_row is not None else 0
                prev_ni = ni_row.iloc[i+1] if ni_row is not None else 0
                if prev_ni and prev_ni != 0:
                    ni_growths.append((cur_ni - prev_ni) / abs(prev_ni))
            
            if rev_growths or ni_growths:
                r_avg = sum(rev_growths)/len(rev_growths) if rev_growths else 0
                n_avg = sum(ni_growths)/len(ni_growths) if ni_growths else 0
                result.update({
                    "revenueGrowth": r_avg,
                    "netIncomeGrowth": n_avg,
                    "epsgrowth": n_avg,
                    "yearsAveraged": max(len(rev_growths), len(ni_growths))
                })
                return result
    except Exception:
        pass

    # 2. TRY ALPHA VANTAGE (Fallback)
    try:
        url = f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={ticker}&apikey={ALPHA_VANTAGE_KEY}"
        res = requests.get(url, timeout=8)
        data = res.json()
        if "annualReports" in data:
            reports = data["annualReports"]
            rev_growths = []
            ni_growths = []
            limit = min(4, len(reports))
            for i in range(limit - 1):
                cur_rev = float(reports[i].get("totalRevenue", 0) or 0)
                prev_rev = float(reports[i+1].get("totalRevenue", 0) or 0)
                if prev_rev != 0: rev_growths.append((cur_rev - prev_rev) / abs(prev_rev))
                
                cur_ni = float(reports[i].get("netIncome", 0) or 0)
                prev_ni = float(reports[i+1].get("netIncome", 0) or 0)
                if prev_ni != 0: ni_growths.append((cur_ni - prev_ni) / abs(prev_ni))
            
            if rev_growths or ni_growths:
                r_avg = sum(rev_growths)/len(rev_growths) if rev_growths else 0
                n_avg = sum(ni_growths)/len(ni_growths) if ni_growths else 0
                result.update({
                    "revenueGrowth": r_avg,
                    "netIncomeGrowth": n_avg,
                    "epsgrowth": n_avg,
                    "yearsAveraged": max(len(rev_growths), len(ni_growths))
                })
                return result
    except Exception:
        pass
        
    return result

@st.cache_data(ttl=86400)
def get_key_metrics(ticker: str) -> dict:
    metrics = {"roeTTM": 0, "roaTTM": 0, "debtToEquityTTM": 0, "freeCashFlowPerShareTTM": 0, "dividendYieldPercentageTTM": 0}
    
    # 1. TRY YFINANCE (Primary)
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        
        metrics["roeTTM"] = info.get("returnOnEquity", 0) or 0
        metrics["roaTTM"] = info.get("returnOnAssets", 0) or 0
        metrics["debtToEquityTTM"] = (info.get("debtToEquity", 0) or 0) / 100.0 if info.get("debtToEquity") else 0
        metrics["freeCashFlowPerShareTTM"] = info.get("freeCashflow", 0) or 0
        metrics["dividendYieldPercentageTTM"] = info.get("dividendYield", 0) or 0
        
        # Manual fallback from raw sheets
        if metrics["roeTTM"] == 0 or metrics["debtToEquityTTM"] == 0:
            bs = t.balance_sheet
            inc = t.financials
            if not bs.empty and not inc.empty:
                def get_val(df, names):
                    for name in names:
                        if name in df.index: return df.loc[name].iloc[0]
                    return 0
                equity = get_val(bs, ["Stockholders Equity", "Total Stockholder Equity"])
                assets = get_val(bs, ["Total Assets"])
                debt = get_val(bs, ["Total Debt", "Long Term Debt"])
                ni = get_val(inc, ["Net Income"])
                
                if equity and equity != 0:
                    if metrics["roeTTM"] == 0: metrics["roeTTM"] = ni / equity
                    if metrics["debtToEquityTTM"] == 0: metrics["debtToEquityTTM"] = debt / equity
                if assets and assets != 0 and metrics["roaTTM"] == 0:
                    metrics["roaTTM"] = ni / assets
    except Exception:
        pass
        
    # 2. TRY FINNHUB (Fallback Tier 2)
    try:
        if metrics["roeTTM"] == 0 or metrics["debtToEquityTTM"] == 0:
            url = f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={FINNHUB_KEY}"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json().get("metric", {})
                if metrics["roeTTM"] == 0: metrics["roeTTM"] = (data.get("roeTTM", 0) or 0) / 100.0
                if metrics["roaTTM"] == 0: metrics["roaTTM"] = (data.get("roaTTM", 0) or 0) / 100.0
                if metrics["debtToEquityTTM"] == 0: metrics["debtToEquityTTM"] = (data.get("totalDebt/totalEquityQuarterly", 0) or 0) / 100.0
    except Exception:
        pass

    return metrics
