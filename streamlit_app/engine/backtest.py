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
    if not series: return 0
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
        "PortRet": (p_sub[-1]-p_sub[0])/p_sub[0] if len(p_sub)>0 and p_sub[0]>0 else 0,
        "SpyRet": (s_sub[-1]-s_sub[0])/s_sub[0] if len(s_sub)>0 and s_sub[0]>0 else 0
    }

def run_simulation(start_year: int = 2010):
    start_date = f"{start_year}-01-01"
    spy_df = get_price_history("SPY")
    qqq_df = get_price_history("QQQ")
    iwm_df = get_price_history("IWM")
    irx_df = get_price_history("^IRX")
    
    if spy_df.empty: return {"error": "No baseline prices."}
    
    spy_df = spy_df[spy_df['date'] >= start_date].sort_values('date').reset_index(drop=True)
    dates = spy_df['date'].tolist()
    
    rebalance_indices = list(range(0, len(dates), 63)) # Quarterly
    
    nav_curve = []
    spy_curve = []
    qqq_curve = []
    iwm_curve = []
    perf_dates = []
    
    cash = 100000.0
    nav = cash
    current_holdings = []
    
    spy_shares = 100000.0 / spy_df.iloc[0]['close'] if spy_df.iloc[0]['close'] > 0 else 0
    
    # Pre-index benchmarks
    qqq_idx = qqq_df.set_index('date')['close'].to_dict() if not qqq_df.empty else {}
    iwm_idx = iwm_df.set_index('date')['close'].to_dict() if not iwm_df.empty else {}
    irx_idx = irx_df.set_index('date')['close'].to_dict() if not irx_df.empty else {}
    qqq_start_px = qqq_idx.get(dates[0], 0)
    iwm_start_px = iwm_idx.get(dates[0], 0)
    qqq_shares = 100000.0 / qqq_start_px if qqq_start_px > 0 else 0
    iwm_shares = 100000.0 / iwm_start_px if iwm_start_px > 0 else 0
    
    price_cache = {}
    fin_cache = {}
    hist_returns_cache = {}
    
    ignore_tickers = ["SPY", "QQQ", "IWM", "TLT", "HYG", "RSP", "^VIX", "^TNX", "^IRX"]
    
    for ticker in UNIVERSE_SUBSET:
        px = get_price_history(ticker)
        price_cache[ticker] = px.set_index('date')['close'].to_dict() if not px.empty else {}
        if ticker not in ignore_tickers:
            fin_cache[ticker] = get_financial_history(ticker)
            if not px.empty:
                df_ret = px.sort_values("date")
                hist_returns_cache[ticker] = df_ret['close'].tolist()

    peak_nav = 100000.0
    
    # Phase 11 & 13 State
    execution_queue = [] 
    previous_candidate_pool = set()
    initial_run = True
    
    for i, date_str in enumerate(dates):
        # --- CASH YIELD ACCRUAL (Phase 14) ---
        # ^IRX is annualized %. E.g. 5.12 means 5.12% per year.
        daily_rate_pct = irx_idx.get(date_str, 2.0) / 100.0 / 252.0
        cash += (cash * daily_rate_pct)
        
        # --- T+1 EXECUTION LOOP (Phase 11 & 12) ---
        if execution_queue:
            new_holdings = []
            for target in execution_queue:
                tck = target["ticker"]
                cap = target["capital"]
                px = price_cache.get(tck, {}).get(date_str, 0)
                if px > 0:
                    shares = cap / px
                    friction = cap * 0.0015 # 0.15% tx cost
                    cash -= (cap + friction)
                    new_holdings.append((tck, shares))
            current_holdings = new_holdings
            execution_queue = []
            
        # --- MARK TO MARKET ---
        todays_market_val = 0
        for h_tick, h_shares in current_holdings:
            px = price_cache.get(h_tick, {}).get(date_str, 0)
            todays_market_val += px * h_shares
            
        nav = cash + todays_market_val
        
        if nav > peak_nav: peak_nav = nav
        current_mdd = (peak_nav - nav) / peak_nav if peak_nav > 0 else 0
        
        dd_exposure_penalty = 1.0
        if current_mdd > 0.20:
             dd_exposure_penalty = 0.50
        elif current_mdd > 0.10:
             dd_exposure_penalty = 0.75
             
        # --- REBALANCE LOOP ---
        if i in rebalance_indices:
            risk_profile = get_macro_state(date_str)
            target_invested_pct = risk_profile.get("exposureTarget", 0.7) * dd_exposure_penalty
            
            scored_stocks = []
            for ticker in UNIVERSE_SUBSET:
                if ticker in ignore_tickers: continue
                px_today = price_cache.get(ticker, {}).get(date_str, 0)
                if px_today == 0: continue
                
                tdt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                avail_fin = [f for f in fin_cache[ticker] if (tdt - datetime.datetime.strptime(f['date'], "%Y-%m-%d")).days > 60]
                
                if avail_fin:
                    # Compute real point-in-time valuation (NOT hardcoded)
                    latest = avail_fin[0]
                    shares = latest.get("sharesOutstanding", 0) or 0
                    ni     = latest.get("netIncome", 0) or 0
                    fcf    = latest.get("freeCashFlow", 0) or 0

                    pt_pe   = 0.0
                    pt_pfcf = 0.0
                    if shares > 0 and ni > 0:
                        eps   = ni / shares
                        pt_pe = px_today / eps if eps > 0 else 0
                    if shares > 0 and fcf > 0:
                        fcf_ps  = fcf / shares
                        pt_pfcf = px_today / fcf_ps if fcf_ps > 0 else 0

                    bt_quote = {"price": px_today, "peForward": pt_pe, "pfcf": pt_pfcf, "sector": "DEFAULT", "dividendYield": 0}

                    bt_growth = {"revenueGrowth": 0, "epsgrowth": 0, "netIncomeGrowth": 0, "yearsAveraged": 1}
                    if len(avail_fin) >= 2:
                        cur_rev = latest.get("revenue", 0) or 0
                        prev_rev = avail_fin[1].get("revenue", 0) or 0
                        if prev_rev: bt_growth["revenueGrowth"] = (cur_rev - prev_rev) / abs(prev_rev)
                        
                        cur_ni = latest.get("netIncome", 0) or 0
                        prev_ni = avail_fin[1].get("netIncome", 0) or 0
                        if prev_ni: 
                            bt_growth["epsgrowth"] = (cur_ni - prev_ni) / abs(prev_ni)
                            bt_growth["netIncomeGrowth"] = bt_growth["epsgrowth"]

                    equity = latest.get("totalEquity", 1) or 1
                    if equity == 0: equity = 1
                    assets = latest.get("totalAssets", 1) or 1
                    if assets == 0: assets = 1
                    debt = latest.get("totalDebt", 0) or 0
                    
                    bt_metrics = {
                        "debtToEquityTTM": debt/equity, 
                        "roeTTM": ni/equity, 
                        "roaTTM": ni/assets, 
                        "freeCashFlowPerShareTTM": fcf, 
                        "dividendYieldPercentageTTM": 0
                    }
                    
                    # Convert raw returns to [{"close": price}] format required by V10 engine
                    idx = spy_df[spy_df['date'] == date_str].index[0]
                    start_idx = max(0, idx - 252)
                    bt_prices = [{"close": p} for p in hist_returns_cache[ticker][start_idx:idx+1]]

                    res = evaluate_stock(ticker, bt_quote, bt_growth, bt_metrics, bt_prices, risk_profile)

                    action = res.get("action", res.get("verdict", ""))
                    if action not in ["AVOID"]:
                        # Calculate volatility
                        idx = spy_df[spy_df['date'] == date_str].index[0]
                        start_idx = max(0, idx - 252)
                        tr = hist_returns_cache[ticker][start_idx:idx+1]
                        rets = [(tr[j]-tr[j-1])/tr[j-1] for j in range(1, len(tr))] if len(tr) > 1 else []

                        scored_stocks.append({
                            "ticker": ticker,
                            "score": res["totalScore"],
                            "return_history": rets,
                            "sector": "Broad"
                        })
            
            scored_stocks.sort(key=lambda x: x["score"], reverse=True)
            top_percentile = [s["ticker"] for s in scored_stocks[:max(20, len(scored_stocks)//3)]]
            
            # Phase 13 Stability Filter
            candidate_pool = []
            for s in scored_stocks:
                if initial_run or s["ticker"] in previous_candidate_pool:
                    candidate_pool.append(s)
            
            # Save for next quarter
            previous_candidate_pool = set(top_percentile)
            initial_run = False
            
            allocations = allocate_capital(candidate_pool[:20])
            
            # Liquidate existing at T
            for h_tick, h_shares in current_holdings:
                px = price_cache.get(h_tick, {}).get(date_str, 0)
                gross_proceeds = h_shares * px
                friction = gross_proceeds * 0.0015
                cash += (gross_proceeds - friction)
                
            current_holdings = [] # All holdings sold
            
            # Queue new purchases for T+1
            invest_cap = (cash + (0)) * target_invested_pct 
            # Note: We compute against total available. 
            
            for a in allocations:
                execution_queue.append({
                    "ticker": a["ticker"],
                    "capital": invest_cap * a["weight"]
                })

        nav_curve.append(nav)
        perf_dates.append(date_str)
        spy_curve.append(spy_shares * spy_df.iloc[i]['close'])
        
        q_val = qqq_shares * qqq_idx.get(date_str, qqq_start_px)
        i_val = iwm_shares * iwm_idx.get(date_str, iwm_start_px)
        qqq_curve.append(q_val if qqq_start_px > 0 else 100000.0)
        iwm_curve.append(i_val if iwm_start_px > 0 else 100000.0)
        
    port_df = pd.DataFrame({"Date": perf_dates, "Portfolio": nav_curve, "SPY": spy_curve, "QQQ": qqq_curve, "IWM": iwm_curve})
    
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
        "benchmark_spy": spy_curve,
        "benchmark_qqq": qqq_curve,
        "benchmark_iwm": iwm_curve,
        "stats": {
            "CAGR": compute_cagr(100000.0, nav_curve[-1], len(dates)),
            "SPY_CAGR": compute_cagr(100000.0, spy_curve[-1], len(dates)),
            "QQQ_CAGR": compute_cagr(100000.0, qqq_curve[-1], len(dates)),
            "MDD": compute_mdd(nav_curve),
            "SPY_MDD": compute_mdd(spy_curve)
        },
        "regimes": regimes,
        "returns_streams": (port_rets, spy_rets)
    }
