import pandas as pd
import numpy as np
import datetime
from data.database import get_price_history, get_financial_history
from data.ingester import UNIVERSE_SUBSET
from engine.scoring import evaluate_stock
from engine.macro import get_macro_state
from engine.portfolio import allocate_capital

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

def run_simulation(start_year: int = 2010):
    start_date = f"{start_year}-01-01"
    spy_df = get_price_history("SPY")
    if spy_df.empty: return {"error": "No baseline prices."}
    
    spy_df = spy_df[spy_df['date'] >= start_date].sort_values('date').reset_index(drop=True)
    dates = spy_df['date'].tolist()
    
    rebalance_indices = list(range(0, len(dates), 63)) # Quarterly
    nav_curve = []
    spy_curve = []
    perf_dates = []
    
    cash = 100000.0
    nav = cash
    current_holdings = []
    target_invested_pct = 1.0
    
    spy_base = spy_df.iloc[0]['close']
    spy_shares = 100000.0 / spy_base if spy_base > 0 else 0
    
    price_cache = {}
    fin_cache = {}
    hist_returns_cache = {}
    
    for ticker in UNIVERSE_SUBSET:
        px = get_price_history(ticker)
        price_cache[ticker] = px.set_index('date')['close'].to_dict() if not px.empty else {}
        fin_cache[ticker] = get_financial_history(ticker)
        
        # Build hist returns lookup simply
        if not px.empty:
            df_ret = px.sort_values("date")
            hist_returns_cache[ticker] = df_ret['close'].tolist()

    peak_nav = 100000.0
    
    for i, date_str in enumerate(dates):
        # 1. Mark to Market
        todays_nav = cash
        for h_tick, h_shares in current_holdings:
            px = price_cache.get(h_tick, {}).get(date_str, 0)
            todays_nav += px * h_shares
            
        nav = todays_nav if len(current_holdings) > 0 or cash < 100000.0 else 100000.0
        
        if nav > peak_nav: peak_nav = nav
        current_mdd = (peak_nav - nav) / peak_nav if peak_nav > 0 else 0
        
        # Phase 4 Drawdown Control checks Daily
        dd_exposure_penalty = 1.0
        if current_mdd > 0.20:
             dd_exposure_penalty = 0.50
        elif current_mdd > 0.10:
             dd_exposure_penalty = 0.75
             
        # 2. Rebalance loop
        if i in rebalance_indices:
            # Macro check
            risk_profile = get_macro_state(date_str)
            state = risk_profile["state"]
            if state == "Risk-ON": target_invested_pct = 0.95
            elif state == "Risk-OFF": target_invested_pct = 0.20
            else: target_invested_pct = 0.60
            
            # Apply Drawdown overlay
            target_invested_pct = target_invested_pct * dd_exposure_penalty
            
            scored_stocks = []
            for ticker in UNIVERSE_SUBSET:
                if ticker in ["SPY", "TLT", "HYG", "RSP", "^VIX", "^TNX"]: continue
                px_today = price_cache.get(ticker, {}).get(date_str, 0)
                if px_today == 0: continue
                
                tdt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                avail_fin = [f for f in fin_cache[ticker] if (tdt - datetime.datetime.strptime(f['date'], "%Y-%m-%d")).days > 60]
                
                if avail_fin:
                    res = evaluate_stock(ticker, avail_fin, {"price": px_today, "peForward": 15, "pfcf": 15}, risk_profile, hist_returns_cache)
                    if res["verdict"] != "AVOID":
                        idx = spy_df[spy_df['date'] == date_str].index[0]
                        # Fetch 1 yr trailing returns for volatility
                        start_idx = max(0, idx - 252)
                        tr = hist_returns_cache[ticker][start_idx:idx+1]
                        rets = [(tr[j]-tr[j-1])/tr[j-1] for j in range(1, len(tr))] if len(tr) > 1 else []
                        
                        scored_stocks.append({
                            "ticker": ticker, 
                            "score": res["totalScore"],
                            "return_history": rets,
                            "sector": "Broad" # Missing mapping, default proxy
                        })
                        
            scored_stocks.sort(key=lambda x: x["score"], reverse=True)
            candidate_pool = scored_stocks[:20]
            
            allocations = allocate_capital(candidate_pool)
            
            # Liquidate
            cash = nav
            current_holdings = []
            
            invest_cap = nav * target_invested_pct
            for a in allocations:
                px = price_cache.get(a["ticker"], {}).get(date_str, 0)
                if px > 0:
                    shares = (invest_cap * a["weight"]) / px
                    current_holdings.append((a["ticker"], shares))
                    cash -= (shares * px)

        nav_curve.append(nav)
        perf_dates.append(date_str)
        s_val = spy_shares * spy_df.iloc[i]['close']
        spy_curve.append(s_val)
        
    cagr_port = compute_cagr(100000.0, nav_curve[-1], len(dates))
    cagr_spy = compute_cagr(100000.0, spy_curve[-1], len(dates))
    
    port_df = pd.DataFrame({"Date": perf_dates, "Portfolio": nav_curve, "SPY": spy_curve})
    
    regimes = {
        "GFC 2008": extract_regime("2008-01-01", "2009-06-01", port_df),
        "COVID 2020": extract_regime("2020-02-01", "2020-05-01", port_df),
        "Rate Hike 2022": extract_regime("2022-01-01", "2022-12-31", port_df)
    }
    
    port_rets = [(nav_curve[i]-nav_curve[i-1])/nav_curve[i-1] for i in range(1, len(nav_curve))]
    spy_rets = [(spy_curve[i]-spy_curve[i-1])/spy_curve[i-1] for i in range(1, len(spy_curve))]
    
    return {
        "dates": perf_dates,
        "portfolio": nav_curve,
        "benchmark": spy_curve,
        "stats": {"CAGR": cagr_port, "SPY_CAGR": cagr_spy, "MDD": compute_mdd(nav_curve), "SPY_MDD": compute_mdd(spy_curve)},
        "regimes": regimes,
        "returns_streams": (port_rets, spy_rets)
    }
