from engine.math_utils import clamp, normalize, inverse_normalize, std_dev

# Sector median P/E table (proxy — update from FMP batch when available)
SECTOR_MEDIAN_PE = {
    "Technology":        28.0,
    "Consumer Cyclical": 22.0,
    "Communication":     20.0,
    "Healthcare":        18.0,
    "Financial":         14.0,
    "Industrials":       20.0,
    "Consumer Defensive":20.0,
    "Energy":            12.0,
    "Utilities":         16.0,
    "Real Estate":       30.0,
    "Basic Materials":   15.0,
    "DEFAULT":           20.0,
}

def evaluate_stock(ticker: str, financials: list, quote: dict, macro_state: dict = None, hist_returns: dict = None):
    """
    V6.6 Institutional-Grade Alpha Engine
    Quality(25) | Value(20) | Growth(25) | Momentum(20) | Risk(10)
    Full institutional hardening: hard caps, sector-relative valuation,
    PEG correction, dual-negative momentum gate, global compression.
    """
    red_flags = []

    if macro_state is None:
        macro_state = {"state": "Neutral"}

    state = macro_state.get("state", "Neutral")

    # --- FACTOR TILTS ---
    w_qual, w_val, w_grow, w_mom, w_risk = 25, 20, 25, 20, 10
    if state == "Risk-ON":
        w_grow, w_mom, w_qual, w_val, w_risk = 35, 30, 15, 10, 10
    elif state == "Risk-OFF":
        w_qual, w_val, w_risk, w_grow, w_mom = 35, 30, 20, 10, 5

    sorted_fin = sorted(financials, key=lambda x: x.get("date", ""), reverse=True)
    if not sorted_fin:
        return {"error": "No financials"}

    current = sorted_fin[0]

    # --- BASE DATA ---
    curr_roe  = current.get("roe", 0)
    curr_nm   = current.get("netMargin", 0)
    fwd_pe    = quote.get("peForward", 0) or 0
    curr_pfcf = quote.get("pfcf", 0) or 0
    sector    = quote.get("sector", "DEFAULT")
    div_yield = quote.get("dividendYield", 0) or 0  # decimal, e.g. 0.03

    de = current.get("totalDebt", 0) / current.get("totalEquity", 1) \
         if current.get("totalEquity", 0) > 0 else 3.0
    cr = 1.5  # proxy; replace with current ratio if available in quote

    # --- HARD FAILS ---
    hard_fail = False
    if de > 5.0:
        red_flags.append({"severity": "CRITICAL", "message": "Extreme leverage (D/E > 5)", "metric": "D/E"})
        hard_fail = True

    neg_fcf_years = sum(1 for f in sorted_fin[:3] if f.get("freeCashFlow", 0) < 0)
    if neg_fcf_years >= 3:
        red_flags.append({"severity": "CRITICAL", "message": "Persistent negative FCF.", "metric": "FCF"})
        hard_fail = True

    # =========================================================
    # PILLAR 1 — QUALITY (25)
    # =========================================================
    score_roe  = normalize(curr_roe, 0, 0.20)
    score_nm   = normalize(curr_nm, 0, 0.25)
    score_roic = normalize(current.get("roa", 0) * 1.2, 0, 0.20)  # proxy ROIC

    qual_raw   = (score_roe * 0.4) + (score_roic * 0.4) + (score_nm * 0.2)
    qual_final = qual_raw * w_qual

    # =========================================================
    # PILLAR 2 — VALUE (20) — HARD REBUILD
    # =========================================================
    rev_growths = []
    for i in range(min(len(sorted_fin) - 1, 4)):
        r1, r2 = sorted_fin[i].get("revenue", 0), sorted_fin[i + 1].get("revenue", 0)
        if r2 > 0:
            rev_growths.append((r1 - r2) / r2)
    avg_growth = (sum(rev_growths) / len(rev_growths)) if rev_growths else 0.05

    eps_growths_val = []
    for i in range(min(len(sorted_fin) - 1, 4)):
        e1, e2 = sorted_fin[i].get("netIncome", 0), sorted_fin[i + 1].get("netIncome", 0)
        if e2 > 0:
            eps_growths_val.append((e1 - e2) / e2)
    avg_eps_g_val = (sum(eps_growths_val) / len(eps_growths_val)) if eps_growths_val else 0.05

    best_growth_pct = max(avg_growth, avg_eps_g_val, 0.0) * 100  # raw %, no artificial floor

    # RULE 4: PEG correction — if growth < 5%, ignore PEG; use dividend-adjusted yield valuation instead
    use_peg = best_growth_pct >= 5.0
    if use_peg:
        eff_growth = best_growth_pct  # no growth floor inflation
        peg = fwd_pe / eff_growth if eff_growth > 0 and fwd_pe > 0 else 5.0
        score_peg = inverse_normalize(peg, 0.5, 3.5)
    else:
        # Low/no-growth company: value them on dividend yield + FCF yield
        # Map combined yield: 4%+ yield = high score, 0% yield = low score
        div_score = normalize(div_yield, 0.0, 0.05)      # 5% = full dividend score
        fcf_score = inverse_normalize(curr_pfcf, 5, 35)  # cheaper FCF = better
        score_peg = (div_score * 0.6) + (fcf_score * 0.4)
        peg = 0.0  # PEG suppressed for low-growth companies

    score_pfcf = inverse_normalize(curr_pfcf, 5, 45)
    score_pe   = inverse_normalize(fwd_pe, 8, 50)

    val_raw   = (score_peg * 0.40) + (score_pfcf * 0.30) + (score_pe * 0.30)
    val_final = val_raw * w_val

    # RULE 2: PEG penalty — only applied when PEG is actually used
    if use_peg and peg > 2.0:
        val_final -= w_val * (5.0 / 20.0)

    # RULE 3 (P/FCF penalty)
    if curr_pfcf > 25:
        val_final -= w_val * (4.0 / 20.0)

    val_final = max(0.0, val_final)

    # RULE 2 (P/E Hard Caps) — applied strictly after penalties
    if fwd_pe > 80:
        val_final = min(val_final, w_val * (6.0 / 20.0))   # Max 6
    elif fwd_pe > 50:
        val_final = min(val_final, w_val * (10.0 / 20.0))  # Max 10
    elif fwd_pe > 30:
        val_final = min(val_final, w_val * (14.0 / 20.0))  # Max 14

    # RULE 3 (Sector-Relative Valuation)
    sector_median = SECTOR_MEDIAN_PE.get(sector, SECTOR_MEDIAN_PE["DEFAULT"])
    if fwd_pe > 0 and sector_median > 0 and fwd_pe > 1.5 * sector_median:
        val_final -= w_val * (4.0 / 20.0)  # Sector premium penalty (~4 pts)
        val_final = max(0.0, val_final)

    # RULE 5 (Value ≤ Quality when P/E > 30)
    if fwd_pe > 30:
        val_final = min(val_final, qual_final)

    # =========================================================
    # PILLAR 3 — GROWTH (25)
    # =========================================================
    eps_growths = []
    for i in range(min(len(sorted_fin) - 1, 4)):
        e1, e2 = sorted_fin[i].get("netIncome", 0), sorted_fin[i + 1].get("netIncome", 0)
        if e2 > 0:
            eps_growths.append((e1 - e2) / e2)
    avg_eps_g = (sum(eps_growths) / len(eps_growths)) if eps_growths else 0.05

    score_rev_g = normalize(avg_growth, 0, 0.20)
    score_eps_g = normalize(avg_eps_g, 0, 0.20)

    grow_raw   = (score_rev_g * 0.5) + (score_eps_g * 0.5)
    grow_final = grow_raw * w_grow

    # =========================================================
    # PILLAR 4 — MOMENTUM (20) — FINAL RULES
    # =========================================================
    mom_6m, mom_12m, mom_rel = 0.0, 0.0, 0.0

    p_t   = []
    p_spy = []

    if hist_returns and ticker in hist_returns and "SPY" in hist_returns:
        p_t   = hist_returns[ticker]
        p_spy = hist_returns["SPY"]
    else:
        from data.fmp import get_historical_prices
        t_hist = get_historical_prices(ticker, days=252)
        s_hist = get_historical_prices("SPY", days=252)

        # Guarantee chronological order: Oldest → Newest
        t_hist_sorted = sorted(t_hist, key=lambda x: x["date"]) if t_hist else []
        s_hist_sorted = sorted(s_hist, key=lambda x: x["date"]) if s_hist else []

        p_t   = [x["close"] for x in t_hist_sorted]
        p_spy = [x["close"] for x in s_hist_sorted]

    if len(p_t) >= 126:  # 6 months
        mom_6m = (p_t[-1] - p_t[-126]) / p_t[-126]

    if len(p_t) >= 200:  # 12 months
        idx_12m = min(len(p_t), 252)
        mom_12m = (p_t[-1] - p_t[-idx_12m]) / p_t[-idx_12m]

        idx_spy = min(len(p_spy), 252)
        if idx_spy > 100:
            spy_12m  = (p_spy[-1] - p_spy[-idx_spy]) / p_spy[-idx_spy]
            mom_rel  = mom_12m - spy_12m

    # Normalization — signed: positive → high score, negative → low score
    score_m12  = max(0.0, min(1.0, (mom_12m + 0.20) / 0.75))  # -20% = 0, +55% = 1
    score_m6   = max(0.0, min(1.0, (mom_6m  + 0.10) / 0.40))  # -10% = 0, +30% = 1
    score_mrel = max(0.0, min(1.0, (mom_rel  + 0.10) / 0.40)) # -10% = 0, +30% = 1

    # Weights: 12M=50%, 6M=30%, Relative=20%
    mom_raw   = (score_m12 * 0.50) + (score_m6 * 0.30) + (score_mrel * 0.20)
    mom_final = mom_raw * w_mom

    # HARD CONDITIONS (applied against absolute out-of-20 equivalents)
    if mom_12m < 0:
        mom_final = min(mom_final, w_mom * (8.0 / 20.0))   # ≤ 8 equivalent

    if mom_6m < 0 and mom_12m < 0:
        mom_final = min(mom_final, w_mom * (5.0 / 20.0))   # ≤ 5 equivalent

    # =========================================================
    # PILLAR 5 — RISK (10)
    # =========================================================
    score_de       = inverse_normalize(de, 0, 5.0)
    score_cr       = normalize(cr, 0.5, 2.0)
    eps_vol        = std_dev(eps_growths)
    score_eps_cons = inverse_normalize(eps_vol, 0.05, 1.0)  # Earnings stability
    rev_vol        = std_dev(rev_growths)
    score_rev_vol  = inverse_normalize(rev_vol, 0.05, 0.5)

    # 40% Balance Sheet | 40% Earnings Consistency | 10% CR | 10% Rev Stability
    risk_raw   = (score_de * 0.40) + (score_cr * 0.10) + (score_eps_cons * 0.40) + (score_rev_vol * 0.10)
    risk_final = risk_raw * w_risk

    # =========================================================
    # FINAL AGGREGATION — RULE 6: 0.9x Global Compression
    # =========================================================
    sys_raw   = qual_final + val_final + grow_final + mom_final + risk_final
    sys_total = (sys_raw * 0.90) - (len(red_flags) * 3.0)
    sys_total = max(0.0, sys_total)

    if hard_fail:
        sys_total = min(sys_total, 30.0)

    verdict = "PASS" if sys_total >= 50 else ("WATCH" if sys_total >= 35 else "AVOID")
    if hard_fail:
        verdict = "AVOID"

    return {
        "ticker":           ticker,
        "baseScore":        round(sys_total, 1),
        "totalScore":       round(sys_total, 1),
        "macroMultiplier":  1.0,
        "verdict":          verdict,
        "scoreMomentum":    0.0,
        "dataQualityLabel": "Reliable",
        "dataQualityPct":   0.95,
        "pillars": {
            "moat":             {"title": "Quality",  "total": round(qual_final, 1), "max": w_qual, "breakdown": [], "penaltyRatio": 0},
            "profitability":    {"title": "Value",    "total": round(val_final, 1),  "max": w_val,  "breakdown": [], "penaltyRatio": 0},
            "financialStrength":{"title": "Growth",   "total": round(grow_final, 1), "max": w_grow, "breakdown": [], "penaltyRatio": 0},
            "cashFlowQuality":  {"title": "Momentum", "total": round(mom_final, 1),  "max": w_mom,  "breakdown": [], "penaltyRatio": 0},
            "valuation":        {"title": "Risk",     "total": round(risk_final, 1), "max": w_risk, "breakdown": [], "penaltyRatio": 0},
        },
        "redFlags": red_flags,
    }
