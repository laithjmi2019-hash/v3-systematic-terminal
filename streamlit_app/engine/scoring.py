import logging

logger = logging.getLogger(__name__)

def evaluate_stock(ticker: str, quote: dict, growth: dict, metrics: dict, prices: list, macro_state: dict = None):
    red_flags = []
    
    def build_breakdown(metric, points, max_points, passed, val_str, exp):
        return {
            "metric": metric, 
            "score": float(points), 
            "basePoints": float(points), 
            "maxPoints": max_points, 
            "passed": passed, 
            "value": val_str, 
            "explanation": exp
        }

    # 1. GROWTH (Max 50)
    rev_grow = growth.get("revenueGrowth", 0) or 0
    eps_grow = growth.get("epsgrowth", growth.get("netIncomeGrowth", 0)) or 0
    years_avg = growth.get("yearsAveraged", 1)

    rev_pts = 25 if rev_grow > 0.10 else (15 if rev_grow >= 0.05 else 5)
    eps_pts = 25 if eps_grow > 0.10 else (15 if eps_grow >= 0.05 else 5)
    growth_total = rev_pts + eps_pts

    p_growth = {
        "title": f"Growth Score ({years_avg}-Yr Avg)", "total": float(growth_total), "max": 50, "penaltyRatio": 0,
        "breakdown": [
            build_breakdown("Revenue Growth", rev_pts, 25, rev_pts > 5, f"{rev_grow*100:.1f}%", ">10%=25, 5-10%=15, <5%=5"),
            build_breakdown("Earnings Growth", eps_pts, 25, eps_pts > 5, f"{eps_grow*100:.1f}%", ">10%=25, 5-10%=15, <5%=5")
        ]
    }

    # 2. VALUE (Sector Relative Valuation) (Max 20)
    pe = quote.get("pe", quote.get("peForward", 0)) or 0
    sector = quote.get("sector", "DEFAULT")

    SECTOR_PE = {
        "Technology": 28.0, "Healthcare": 22.0, "Financial Services": 14.0,
        "Consumer Cyclical": 20.0, "Industrials": 21.0, "Energy": 12.0,
        "Consumer Defensive": 20.0, "Utilities": 17.0, "Real Estate": 25.0,
        "Basic Materials": 15.0, "Communication Services": 19.0, "DEFAULT": 20.0
    }
    sec_median_pe = SECTOR_PE.get(sector, 20.0)
    
    pe_pts = 5
    rel_pe = (pe / sec_median_pe) if (sec_median_pe > 0 and pe > 0) else 999.0
    
    if pe > 0 and rel_pe <= 0.8: pe_pts = 20
    elif pe > 0 and rel_pe <= 1.2: pe_pts = 10

    p_value = {
        "title": "Value Score (Sector Rel)", "total": float(pe_pts), "max": 20, "penaltyRatio": 0,
        "breakdown": [
            build_breakdown("P/E Ratio", pe_pts, 20, pe_pts > 5, f"{pe:.1f} vs {sec_median_pe:.1f} (Peer)", "Rel PE <=0.8=20, <=1.2=10, >1.2=5")
        ]
    }

    # 3. STABILITY (Max 40)
    de = metrics.get("debtToEquityTTM", 0) or 0
    roe = metrics.get("roeTTM", 0) or 0

    de_pts = 20 if (0 <= de < 1) else 5
    roe_pts = 20 if roe > 0.15 else 10
    stab_total = de_pts + roe_pts

    p_stab = {
        "title": "Stability Score", "total": float(stab_total), "max": 40, "penaltyRatio": 0,
        "breakdown": [
            build_breakdown("Debt / Equity", de_pts, 20, de_pts == 20, f"{de:.2f}", "<1=20, else 5"),
            build_breakdown("ROE", roe_pts, 20, roe_pts == 20, f"{roe*100:.1f}%", ">15%=20, else 10")
        ]
    }

    # 4. PROFITABILITY (Max 30)
    roa = metrics.get("roaTTM", 0) or 0
    fcf = metrics.get("freeCashFlowPerShareTTM", quote.get("pfcf", 0)) or 0

    roa_pts = 15 if roa > 0.10 else 5
    fcf_pts = 15 if fcf > 0 else 5
    prof_total = roa_pts + fcf_pts

    p_prof = {
        "title": "Profitability Score", "total": float(prof_total), "max": 30, "penaltyRatio": 0,
        "breakdown": [
            build_breakdown("ROA", roa_pts, 15, roa_pts == 15, f"{roa*100:.1f}%", ">10%=15, else 5"),
            build_breakdown("Free Cash Flow", fcf_pts, 15, fcf_pts == 15, "Positive" if fcf > 0 else "Negative", ">0 = 15, else 5")
        ]
    }

    # 5. DIVIDEND (Max 10)
    yield_val = metrics.get("dividendYieldPercentageTTM")
    if yield_val is None: yield_val = quote.get("dividendYield", 0)
    yield_pct = yield_val or 0
    formatted_yield = yield_pct * 100 if yield_pct < 1 else yield_pct

    div_pts = 0
    if formatted_yield > 3: div_pts = 10
    elif formatted_yield >= 1: div_pts = 5

    p_div = {
        "title": "Dividend Score", "total": float(div_pts), "max": 10, "penaltyRatio": 0,
        "breakdown": [
            build_breakdown("Dividend Yield", div_pts, 10, div_pts > 0, f"{formatted_yield:.1f}%", ">3%=10, 1-3%=5, <1%=0")
        ]
    }

    base_total = growth_total + pe_pts + stab_total + prof_total + div_pts

    # 6. ENGINES & GUARDRAILS (V10 Institutional)
    
    # Smart Money Revisions Bonus/Penalty
    rev_score = quote.get("revisions_score", 0.5)
    bonus_penalty = 0
    if rev_score >= 0.75: bonus_penalty = 10
    elif rev_score <= 0.25: bonus_penalty = -15
    
    # 200 SMA Kill Switch logic
    fail_trend_gate = False
    curr_price = float(quote.get("price", 0))
    sma200 = 0.0
    if prices and len(prices) > 50:
        prices_subset = [float(day.get("close", 0)) for day in prices[-200:]]
        sma200 = sum(prices_subset) / len(prices_subset)
        if curr_price > 0 and curr_price < sma200:
            fail_trend_gate = True
            red_flags.append({
                "severity": "CRITICAL", 
                "metric": "SMA 200 Trend Gate", 
                "message": f"Structural downtrend. Price (${curr_price:.2f}) < SMA200 (${sma200:.2f}). Max score capped at HOLD."
            })
    
    if bonus_penalty != 0:
        red_flags.append({
            "severity": "INFO" if bonus_penalty > 0 else "WARNING", 
            "metric": "Smart Money / Analyst Revisions", 
            "message": f"{'+' if bonus_penalty > 0 else ''}{bonus_penalty} point adjustment."
        })

    final_score = base_total + bonus_penalty
    macro_multiplier = macro_state.get("multiplier", 1.0) if macro_state else 1.0
    final_score = final_score * macro_multiplier
    
    # Limit maximum score to 150
    final_score = min(final_score, 150)

    # Hard-Fail Kill Switch Application
    if fail_trend_gate:
        # Heavily cap maximum out of 150 so it never reads BUY/STRONG BUY
        final_score = min(final_score, 64)

    if final_score >= 80:
        verdict = "STRONG BUY"
    elif final_score >= 65:
        verdict = "BUY"
    elif final_score >= 50:
        verdict = "HOLD"
    else:
        verdict = "AVOID"

    confidence = "High" if bool(quote) and bool(growth) and bool(metrics) else "Low"

    return {
        "ticker": ticker,
        "baseScore": base_total,
        "totalScore": round(final_score, 1),
        "macroMultiplier": macro_multiplier,
        "verdict": verdict,
        "action": verdict,
        "confidence": confidence,
        "alphaScore": 0,
        "alphaRankingStr": "Underperformer",
        "pillars": {
            "growth": p_growth,
            "value": p_value,
            "stability": p_stab,
            "profitability": p_prof,
            "dividend": p_div
        },
        "redFlags": red_flags
    }

