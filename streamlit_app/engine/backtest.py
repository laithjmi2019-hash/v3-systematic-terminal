import pandas as pd
import numpy as np
import datetime
from data.database import get_price_history, get_financial_history
from data.ingester import UNIVERSE_SUBSET
from engine.scoring import evaluate_stock
from engine.alpha import calculate_alpha_and_rank

def compute_cagr(start_val, end_val, days):
    if start_val <= 0 or days <= 0: return 0
    years = days / 252.0
    return (end_val / start_val)**(1/years) - 1

def compute_mdd(series):
    peak = series[0]
    mdd = 0
    for p in series:
        if p > peak: peak = p
        dd = (peak - p) / peak if peak > 0 else 0
        if dd > mdd: mdd = dd
    return mdd

def run_simulation(start_year: int = 2010):
    start_date = f"{start_year}-01-01"
    
    spy_df = get_price_history("SPY")
    if spy_df.empty:
        return {"error": "No SPY baseline prices found. Run Ingester."}
    
    spy_df = spy_df[spy_df['date'] >= start_date].sort_values('date').reset_index(drop=True)
    if spy_df.empty:
        return {"error": "No baseline prices in active window."}

    dates = spy_df['date'].tolist()
    
    # Identify quarterly rebalance dates (roughly every 63 trading days)
    rebalance_indices = list(range(0, len(dates), 63))
    
    port_history = []
    current_holdings = [] # List of tuples: (ticker, shares)
    cash = 100000.0
    nav = 100000.0
    
    spy_base = spy_df.iloc[0]['close']
    spy_shares = 100000.0 / spy_base if spy_base > 0 else 0
    
    nav_curve = []
    spy_curve = []
    perf_dates = []

    # Pre-cache DB to avoid DB thrashing inside loop
    price_cache = {}
    fin_cache = {}
    for ticker in UNIVERSE_SUBSET:
        if ticker == "SPY": continue
        px = get_price_history(ticker)
        price_cache[ticker] = px.set_index('date')['close'].to_dict() if not px.empty else {}
        fin_cache[ticker] = get_financial_history(ticker)

    current_idx = 0
    for i, date_str in enumerate(dates):
        # 1. Price update
        todays_nav = cash
        for h_tick, h_shares in current_holdings:
            px = price_cache.get(h_tick, {}).get(date_str, 0)
            todays_nav += px * h_shares
            
        nav = todays_nav if len(current_holdings) > 0 or cash < 100000.0 else 100000.0
        
        # 2. Rebalance logic
        if i in rebalance_indices:
            # Score universe
            scored_stocks = []
            for ticker in UNIVERSE_SUBSET:
                if ticker == "SPY": continue
                px_today = price_cache.get(ticker, {}).get(date_str, 0)
                if px_today == 0: continue
                
                # Lookback financials without leakage (assume 60 day lag required)
                tdt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                avail_fin = []
                for f in fin_cache[ticker]:
                    try:
                        f_dt = datetime.datetime.strptime(f['date'], "%Y-%m-%d")
                        if (tdt - f_dt).days > 60:
                            avail_fin.append(f)
                    except:
                        pass
                
                if avail_fin:
                    mock_quote = {"price": px_today, "peForward": 15, "pfcf": 15}
                    res = evaluate_stock(ticker, avail_fin, mock_quote, 1.0, True)
                    if "totalScore" in res:
                        alf = calculate_alpha_and_rank(res)
                        if alf["verdict"] != "AVOID":
                            scored_stocks.append((ticker, alf["alphaScore"], px_today))
                            
            # Sort Top 5
            scored_stocks.sort(key=lambda x: x[1], reverse=True)
            top_stocks = scored_stocks[:5]
            
            # Liquidate
            cash = nav
            current_holdings = []
            
            # Reinvest
            if top_stocks:
                alloc = cash / len(top_stocks)
                for t, score, px in top_stocks:
                    if px > 0:
                        shares = alloc / px
                        current_holdings.append((t, shares))
                        cash -= (shares * px)

        nav_curve.append(nav)
        perf_dates.append(date_str)
        s_val = spy_shares * spy_df.iloc[i]['close']
        spy_curve.append(s_val)
        
    # Stats
    cagr_port = compute_cagr(100000.0, nav_curve[-1], len(dates))
    cagr_spy = compute_cagr(100000.0, spy_curve[-1], len(dates))
    mdd_port = compute_mdd(nav_curve)
    mdd_spy = compute_mdd(spy_curve)

    port_df = pd.DataFrame({"Date": perf_dates, "Portfolio": nav_curve, "SPY": spy_curve})

    # Regime Analysis
    def extract_regime(start, end, df):
        mask = (df["Date"] >= start) & (df["Date"] <= end)
        sub = df[mask]
        if sub.empty: return None
        p_sub = sub["Portfolio"].tolist()
        s_sub = sub["SPY"].tolist()
        return {
            "PortMDD": compute_mdd(p_sub),
            "SpyMDD": compute_mdd(s_sub),
            "PortRet": (p_sub[-1]-p_sub[0])/p_sub[0] if p_sub[0]>0 else 0,
            "SpyRet": (s_sub[-1]-s_sub[0])/s_sub[0] if s_sub[0]>0 else 0
        }
        
    regimes = {
        "GFC 2008": extract_regime("2008-01-01", "2009-06-01", port_df),
        "COVID 2020": extract_regime("2020-02-01", "2020-05-01", port_df),
        "Rate Hike 2022": extract_regime("2022-01-01", "2022-12-31", port_df)
    }

    # Factor Prep
    port_rets = []
    spy_rets = []
    for i in range(1, len(nav_curve)):
        port_rets.append((nav_curve[i]-nav_curve[i-1])/nav_curve[i-1])
        spy_rets.append((spy_curve[i]-spy_curve[i-1])/spy_curve[i-1])

    return {
        "dates": perf_dates,
        "portfolio": nav_curve,
        "benchmark": spy_curve,
        "stats": {
            "CAGR": cagr_port,
            "SPY_CAGR": cagr_spy,
            "MDD": mdd_port,
            "SPY_MDD": mdd_spy
        },
        "regimes": regimes,
        "returns_streams": (port_rets, spy_rets)
    }
