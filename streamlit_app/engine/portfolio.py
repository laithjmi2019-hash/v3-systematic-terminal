import numpy as np
import pandas as pd
from data.fmp import get_historical_prices, get_company_profile
from engine.math_utils import std_dev

def max_drawdown(series: list) -> float:
    if not series: return 0.0
    peak = series[0]
    mdd = 0.0
    for p in series:
        if p > peak:
            peak = p
        dd = (peak - p) / peak if peak > 0 else 0
        if dd > mdd:
            mdd = dd
    return mdd

def evaluate_portfolio(holdings: list) -> dict:
    signals = []
    returns_map = {}
    close_prices = {}
    sectors_map = {}
    
    for h in holdings:
        t = h["ticker"]
        prices = get_historical_prices(t, 252)
        close_list = [p["close"] for p in prices]
        close_prices[t] = close_list[::-1] # chronologically oldest to newest for drawdown logic
        
        returns = []
        for i in range(len(prices)-1):
            if prices[i+1]["close"] > 0:
                returns.append((prices[i]["close"] - prices[i+1]["close"]) / prices[i+1]["close"])
        returns_map[t] = returns
        
        prof = get_company_profile(t)
        sectors_map[t] = prof.get("sector", "Unknown")
        
    tickers = [h["ticker"] for h in holdings]
    correlation_matrix = {}
    total_corrs = 0
    sum_corrs = 0
    
    for t1 in tickers:
        correlation_matrix[t1] = {}
        for t2 in tickers:
            if t1 == t2:
                correlation_matrix[t1][t2] = 1.0
            else:
                a1 = returns_map[t1]
                a2 = returns_map[t2]
                length = min(len(a1), len(a2))
                if length == 0:
                    corr = 0.0
                else:
                    corr = float(np.corrcoef(a1[:length], a2[:length])[0, 1])
                    if np.isnan(corr): corr = 0.0
                
                correlation_matrix[t1][t2] = corr
                if t1 > t2:
                    sum_corrs += corr
                    total_corrs += 1
                    if corr > 0.8:
                        signals.append(f"High risk overlap: {t1} / {t2} (Corr: {corr:.2f})")
                        
    avg_corr = sum_corrs / total_corrs if total_corrs > 0 else 0
    
    sector_weights = {}
    for h in holdings:
        s = sectors_map[h["ticker"]]
        sector_weights[s] = sector_weights.get(s, 0) + h["weight"]
        
    top_sectors = sorted([{"sector": s, "percent": w} for s, w in sector_weights.items()], key=lambda x: x["percent"], reverse=True)
    max_sector_conc = top_sectors[0]["percent"] if top_sectors else 0
    if max_sector_conc > 0.4:
        signals.append(f"Sector Concentration Warning: {top_sectors[0]['sector']} at {max_sector_conc*100:.0f}%")
        
    sorted_holdings = sorted(holdings, key=lambda x: x["weight"], reverse=True)
    top3 = sum(h["weight"] for h in sorted_holdings[:3])
    if top3 > 0.6:
        signals.append(f"Top 3 Holdings Concentration: {top3*100:.0f}%")
        
    pt_volatility = 0.0
    pt_mdd = 0.0
    for h in holdings:
        t = h["ticker"]
        w = h["weight"]
        pt_volatility += std_dev(returns_map.get(t, [])) * w
        pt_mdd += max_drawdown(close_prices.get(t, [])) * w
        
    risk_factor = (0.5 * max(0, avg_corr)) + (0.3 * max_sector_conc) + (0.2 * min(1, pt_volatility * 20))
    risk_score = risk_factor * 100
    
    classification = "Low"
    if risk_score > 70:
        classification = "High"
    elif risk_score > 40:
        classification = "Medium"
        
    return {
        "avgCorrelation": avg_corr,
        "sectorConcentration": max_sector_conc,
        "volatility": pt_volatility,
        "maxDrawdown": pt_mdd,
        "riskClassification": classification,
        "portfolioRiskScore": risk_score,
        "topSectors": top_sectors,
        "correlationMatrix": correlation_matrix,
        "signals": signals
    }
