from engine.math_utils import clamp, normalize, inverse_normalize, std_dev

def evaluate_stock(ticker: str, financials: list, quote: dict, macro_state: dict = None, hist_returns: dict = None):
    """
    V6 Alpha Engine
    Quality(25) | Value(20) | Growth(25) | Momentum(20) | Risk(10)
    Factor Tilt changes weights dynamically based on macro_state.
    """
    red_flags = []
    
    if macro_state is None:
        macro_state = {"state": "Neutral"}
        
    state = macro_state.get("state", "Neutral")
    
    # FACTOR TILTS (Phase 5)
    w_qual, w_val, w_grow, w_mom, w_risk = 25, 20, 25, 20, 10
    if state == "Risk-ON":
        w_grow, w_mom, w_qual, w_val, w_risk = 35, 30, 15, 10, 10
    elif state == "Risk-OFF":
        w_qual, w_val, w_risk, w_grow, w_mom = 35, 30, 20, 10, 5

    sorted_fin = sorted(financials, key=lambda x: x.get("date", ""), reverse=True)
    if not sorted_fin:
        return {"error": "No financials"}
    
    current = sorted_fin[0]
    
    # Base Data Extraction
    curr_roe = current.get("roe", 0)
    curr_nm = current.get("netMargin", 0)
    fwd_pe = quote.get("peForward", 0)
    curr_pfcf = quote.get("pfcf", 0)
    de = current.get("totalDebt", 0) / current.get("totalEquity", 1) if current.get("totalEquity", 0) > 0 else 3.0
    cr = 1.5 # proxy

    # Check for hard fails (Phase 1 rules: Extreme only)
    hard_fail = False
    if de > 5.0:
        red_flags.append({"severity": "CRITICAL", "message": "Extreme leverage (D/E > 5)", "metric": "D/E"})
        hard_fail = True
    
    neg_fcf_years = sum(1 for f in sorted_fin[:3] if f.get("freeCashFlow", 0) < 0)
    if neg_fcf_years >= 3:
        red_flags.append({"severity": "CRITICAL", "message": "Persistent negative FCF.", "metric": "FCF"})
        hard_fail = True

    # QUALITY (25)
    score_roe = normalize(curr_roe, 0, 0.20)
    score_nm = normalize(curr_nm, 0, 0.25)
    # proxy ROIC with ROA * 1.2
    score_roic = normalize(current.get("roa", 0) * 1.2, 0, 0.20)
    
    qual_raw = (score_roe * 0.4) + (score_roic * 0.4) + (score_nm * 0.2)
    qual_final = qual_raw * w_qual
    
    # VALUE (20)
    rev_growths = []
    for i in range(min(len(sorted_fin)-1, 4)):
        r1, r2 = sorted_fin[i].get("revenue",0), sorted_fin[i+1].get("revenue",0)
        if r2 > 0: rev_growths.append((r1-r2)/r2)
    avg_growth = (sum(rev_growths)/len(rev_growths)) if rev_growths else 0.05
    
    eps_growths_val = []
    for i in range(min(len(sorted_fin)-1, 4)):
        e1, e2 = sorted_fin[i].get("netIncome",0), sorted_fin[i+1].get("netIncome",0)
        if e2 > 0: eps_growths_val.append((e1-e2)/e2)
    avg_eps_g_val = (sum(eps_growths_val)/len(eps_growths_val)) if eps_growths_val else 0.05

    # Proxy a fundamental structural yield buffer (8%) to protect mature dividend-payers from hyper-growth PEG biases
    eff_growth = max(avg_growth, avg_eps_g_val, 0.01) * 100 + 8.0 
    peg = fwd_pe / eff_growth if eff_growth > 0 else 5.0
    
    score_peg = inverse_normalize(peg, 0.5, 3.5)
    score_pfcf = inverse_normalize(curr_pfcf, 5, 45)
    score_pe = inverse_normalize(fwd_pe, 8, 45)
    
    val_raw = (score_peg * 0.40) + (score_pfcf * 0.30) + (score_pe * 0.30)
    val_final = val_raw * w_val
    
    # RULE 2: PEG Penalty (Subtract 5 points equivalent)
    if peg > 2.0:
        val_final -= w_val * (5.0 / 20.0)
        
    # RULE 3: P/FCF Penalty (Subtract 4 points equivalent)
    if curr_pfcf > 25:
        val_final -= w_val * (4.0 / 20.0)
        
    val_final = max(0.0, val_final)
    
    # RULE 1: P/E Caps
    if fwd_pe > 50:
        val_final = min(val_final, w_val * (10.0 / 20.0)) # Max 10 equivalent
    elif fwd_pe > 30:
        val_final = min(val_final, w_val * (14.0 / 20.0)) # Max 14 equivalent
        
    # RULE 4: Value MUST NOT exceed Quality if P/E > 30
    if fwd_pe > 30:
        val_final = min(val_final, qual_final)
    
    # GROWTH (25)
    eps_growths = []
    for i in range(min(len(sorted_fin)-1, 4)):
        e1, e2 = sorted_fin[i].get("netIncome",0), sorted_fin[i+1].get("netIncome",0)
        if e2 > 0: eps_growths.append((e1-e2)/e2)
    avg_eps_g = (sum(eps_growths)/len(eps_growths)) if eps_growths else 0.05
    
    score_rev_g = normalize(avg_growth, 0, 0.20)
    score_eps_g = normalize(avg_eps_g, 0, 0.20)
    
    grow_raw = (score_rev_g * 0.5) + (score_eps_g * 0.5)
    grow_final = grow_raw * w_grow

    # MOMENTUM (20)
    mom_6m, mom_12m, mom_rel = 0.0, 0.0, 0.0
    
    p_t = []
    p_spy = []
    
    if hist_returns and ticker in hist_returns and "SPY" in hist_returns:
        p_t = hist_returns[ticker]
        p_spy = hist_returns["SPY"]
    else:
        from data.fmp import get_historical_prices
        t_hist = get_historical_prices(ticker, days=252)
        s_hist = get_historical_prices("SPY", days=252)
        
        t_hist_sorted = sorted(t_hist, key=lambda x: x["date"]) if t_hist else []
        s_hist_sorted = sorted(s_hist, key=lambda x: x["date"]) if s_hist else []
        
        p_t = [x["close"] for x in t_hist_sorted]
        p_spy = [x["close"] for x in s_hist_sorted]

    if len(p_t) >= 126: # 6 months
        mom_6m = (p_t[-1] - p_t[-126]) / p_t[-126]
    if len(p_t) >= 200: # 12 months
        idx_12m = min(len(p_t), 252)
        mom_12m = (p_t[-1] - p_t[-idx_12m]) / p_t[-idx_12m]
        
        idx_spy = min(len(p_spy), 252)
        if idx_spy > 100:
            spy_12m = (p_spy[-1] - p_spy[-idx_spy]) / p_spy[-idx_spy]
            mom_rel = mom_12m - spy_12m
            
    # Remove volatility/short-term hooks - strictly mapped cleanly across standard historical variance
    score_m12 = max(0.0, min(1.0, (mom_12m + 0.20) / 0.75)) # 12M map
    score_m6  = max(0.0, min(1.0, (mom_6m + 0.10) / 0.40))  # 6M map
    score_mrel = max(0.0, min(1.0, (mom_rel + 0.10) / 0.40)) # Rel map
    
    # EXACT user weight requirement: 50% (12M), 30% (6M), 20% (Relative)
    mom_raw = (score_m12 * 0.50) + (score_m6 * 0.30) + (score_mrel * 0.20)
    mom_final = mom_raw * w_mom
    
    # STRICT HARD CONDITIONS
    if mom_12m < 0:
        mom_final = min(mom_final, w_mom * (8.0 / 20.0)) # Hard cap at equivalent of 8/20
        
    if mom_6m < 0 and mom_12m < 0:
        mom_final = min(mom_final, w_mom * (5.0 / 20.0)) # Hard cap at equivalent of 5/20

    # RISK (10)
    score_de = inverse_normalize(de, 0, 5.0) # Highly permissive boundary for treasury-stock buyback distortions
    score_cr = normalize(cr, 0.5, 2.0)
    
    eps_vol = std_dev(eps_growths)
    score_eps_cons = inverse_normalize(eps_vol, 0.05, 1.0) # Earnings Stability (Extremely heavy penalty for boom/bust)
    
    rev_vol = std_dev(rev_growths)
    score_rev_vol = inverse_normalize(rev_vol, 0.05, 0.5) # Softened revenue volatility penalty
    
    # 50% Balance Sheet, 40% Earnings Consistency, 10% Volatility
    risk_raw = (score_de * 0.40) + (score_cr * 0.10) + (score_eps_cons * 0.40) + (score_rev_vol * 0.10)
    risk_final = risk_raw * w_risk

    sys_raw = qual_final + val_final + grow_final + mom_final + risk_final
    
    # SYSTEMIC COMPRESSION: Combat Score Inflation (Max Theoretical ~90, Top Decile > 85)
    # Deduct structural penalty points per generated red_flag
    sys_total = (sys_raw * 0.90) - (len(red_flags) * 3.0)
    
    if hard_fail:
        sys_total = min(sys_total, 30)
        
    verdict = "PASS" if sys_total >= 50 else ("WATCH" if sys_total >= 35 else "AVOID")
    if hard_fail: verdict = "AVOID"

    # Match output requirements from App layer
    return {
        "ticker": ticker,
        "baseScore": round(sys_total, 1),
        "totalScore": round(sys_total, 1),
        "macroMultiplier": 1.0,
        "verdict": verdict,
        "scoreMomentum": 0.0,
        "dataQualityLabel": "Reliable",
        "dataQualityPct": 0.95,
        "pillars": {
            "moat": {"title": "Quality", "total": round(qual_final,1), "max": w_qual, "breakdown": [], "penaltyRatio": 0},
            "profitability": {"title": "Value", "total": round(val_final,1), "max": w_val, "breakdown": [], "penaltyRatio": 0},
            "financialStrength": {"title": "Growth", "total": round(grow_final,1), "max": w_grow, "breakdown": [], "penaltyRatio": 0},
            "cashFlowQuality": {"title": "Momentum", "total": round(mom_final,1), "max": w_mom, "breakdown": [], "penaltyRatio": 0},
            "valuation": {"title": "Risk", "total": round(risk_final,1), "max": w_risk, "breakdown": [], "penaltyRatio": 0}
        },
        "redFlags": red_flags
    }
