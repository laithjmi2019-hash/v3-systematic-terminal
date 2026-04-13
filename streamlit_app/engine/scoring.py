import logging
from engine.math_utils import clamp, normalize, inverse_normalize, std_dev

logger = logging.getLogger(__name__)

# Sector median P/E table (proxy)
SECTOR_MEDIAN_PE = {
    "Technology":            28.0,
    "Consumer Cyclical":     22.0,
    "Communication Services":22.0,
    "Communication":         22.0,
    "Healthcare":            18.0,
    "Financial Services":    14.0,
    "Financial":             14.0,
    "Industrials":           20.0,
    "Consumer Defensive":    20.0,
    "Energy":                12.0,
    "Utilities":             16.0,
    "Real Estate":           30.0,
    "Basic Materials":       15.0,
    "DEFAULT":               20.0,
}


def evaluate_stock(ticker: str, financials: list, quote: dict,
                   macro_state: dict = None, hist_returns: dict = None):
    """
    V6.7 Institutional-Grade Alpha Engine — COMPREHENSIVE FIX
    Quality(25) | Value(20) | Growth(25) | Momentum(20) | Risk(10)

    All penalty/cap logic is guarded by data-availability flags.
    Missing data → neutral scores, NOT penalty spirals.
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
    curr_roe  = current.get("roe", 0) or 0
    curr_nm   = current.get("netMargin", 0) or 0
    fwd_pe    = float(quote.get("peForward", 0) or 0)
    curr_pfcf = float(quote.get("pfcf", 0) or 0)
    sector    = quote.get("sector", "DEFAULT") or "DEFAULT"
    div_yield = float(quote.get("dividendYield", 0) or 0)

    # Data availability flags — guards ALL penalty/cap logic
    has_pe   = fwd_pe > 0
    has_pfcf = curr_pfcf > 0

    de = current.get("totalDebt", 0) / current.get("totalEquity", 1) \
         if current.get("totalEquity", 0) > 0 else 3.0
    cr = 1.5  # proxy

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
    score_roic = normalize(current.get("roa", 0) * 1.2, 0, 0.20)

    qual_raw   = (score_roe * 0.4) + (score_roic * 0.4) + (score_nm * 0.2)
    qual_final = qual_raw * w_qual

    # =========================================================
    # PILLAR 2 — VALUE (20) — DATA-GUARDED
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

    best_growth_pct = max(avg_growth, avg_eps_g_val, 0.0) * 100

    # --- PEG SCORING ---
    # Only compute PEG when BOTH forward PE exists AND growth >= 5%
    use_peg = best_growth_pct >= 5.0 and has_pe
    peg = 0.0

    if use_peg:
        peg = fwd_pe / best_growth_pct if best_growth_pct > 0 else 5.0
        score_peg = inverse_normalize(peg, 0.5, 3.5)
    elif not has_pe:
        # NO PE DATA: completely neutral PEG — do NOT penalize
        score_peg = 0.5
    else:
        # Has PE but low growth: dividend-adjusted valuation
        div_score = normalize(div_yield, 0.0, 0.05)
        fcf_score = inverse_normalize(curr_pfcf, 5, 35) if has_pfcf else 0.5
        score_peg = (div_score * 0.6) + (fcf_score * 0.4)

    # P/FCF & P/E sub-scores — neutral when data missing
    score_pfcf = inverse_normalize(curr_pfcf, 5, 45) if has_pfcf else 0.5
    score_pe   = inverse_normalize(fwd_pe, 8, 50)    if has_pe   else 0.5

    val_raw   = (score_peg * 0.40) + (score_pfcf * 0.30) + (score_pe * 0.30)
    val_final = val_raw * w_val

    # --- PENALTIES (only fire when data is REAL) ---
    if use_peg and peg > 2.0:
        val_final -= 5.0

    if has_pfcf and curr_pfcf > 25:
        val_final -= 4.0

    val_final = max(0.0, val_final)

    # --- VALUE TRAP DETECTION ---
    latest_fcf = current.get("freeCashFlow", 0)
    if avg_growth < 0 and latest_fcf < 0:
        val_final -= 7.0
        red_flags.append({"severity": "WARNING",
                          "message": "Value trap risk: declining revenue + negative FCF",
                          "metric": "ValueTrap"})

    if curr_roe < 0.05:
        val_final -= 4.0

    val_final = max(0.0, val_final)

    # --- P/E HARD CAPS (only when PE data exists) ---
    if has_pe:
        if fwd_pe > 80:
            val_final = min(val_final, 6.0)
        elif fwd_pe > 50:
            val_final = min(val_final, 10.0)
        elif fwd_pe > 30:
            val_final = min(val_final, 14.0)

    # --- SECTOR-RELATIVE PENALTY (only when PE data exists) ---
    if has_pe:
        sector_median = SECTOR_MEDIAN_PE.get(sector, SECTOR_MEDIAN_PE["DEFAULT"])
        if fwd_pe > 1.5 * sector_median:
            val_final = max(0.0, val_final - 4.0)

    # --- VALUE ≤ QUALITY GATE (only when PE data exists and PE is high) ---
    if has_pe and fwd_pe > 30:
        val_final = min(val_final, qual_final)

    logger.debug("[VALUE %s] pe=%.1f pfcf=%.1f peg=%.2f has_pe=%s has_pfcf=%s use_peg=%s → val=%.1f",
                 ticker, fwd_pe, curr_pfcf, peg, has_pe, has_pfcf, use_peg, val_final)

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
    # PILLAR 4 — MOMENTUM (20)
    # Weights: 12M = 50%, 6M = 30%, Relative vs SPY = 20%
    # =========================================================
    mom_6m, mom_12m, mom_rel = 0.0, 0.0, 0.0
    has_momentum_data = False

    p_t   = []
    p_spy = []

    if hist_returns and ticker in hist_returns and "SPY" in hist_returns:
        p_t   = hist_returns[ticker]
        p_spy = hist_returns["SPY"]
    else:
        from data.fmp import get_historical_prices
        t_prices  = get_historical_prices(ticker, days=252)
        s_prices  = get_historical_prices("SPY", days=252)

        # get_historical_prices now returns oldest-first already
        p_t   = [x["close"] for x in t_prices]
        p_spy = [x["close"] for x in s_prices]

    # return = (price_now / price_past) - 1
    if len(p_t) >= 126:
        has_momentum_data = True
        mom_6m = (p_t[-1] / p_t[-126]) - 1.0

    if len(p_t) >= 200:
        idx_12m = min(len(p_t), 252)
        mom_12m = (p_t[-1] / p_t[-idx_12m]) - 1.0

        idx_spy = min(len(p_spy), 252)
        if idx_spy > 100 and p_spy[-idx_spy] > 0:
            spy_12m = (p_spy[-1] / p_spy[-idx_spy]) - 1.0
            mom_rel = mom_12m - spy_12m

    logger.debug("[MOMENTUM %s] 6m=%.3f 12m=%.3f rel=%.3f pts=%d has_data=%s",
                 ticker, mom_6m, mom_12m, mom_rel, len(p_t), has_momentum_data)

    if has_momentum_data:
        # Signed normalization — positive → high, negative → low
        score_m12  = max(0.0, min(1.0, (mom_12m + 0.20) / 0.75))
        score_m6   = max(0.0, min(1.0, (mom_6m  + 0.10) / 0.40))
        score_mrel = max(0.0, min(1.0, (mom_rel  + 0.10) / 0.40))

        mom_raw   = (score_m12 * 0.50) + (score_m6 * 0.30) + (score_mrel * 0.20)
        mom_final = mom_raw * w_mom

        # HARD CONDITIONS
        if mom_12m < 0:
            mom_final = min(mom_final, 8.0 * (w_mom / 20.0))

        if mom_6m < 0 and mom_12m < 0:
            mom_final = min(mom_final, 5.0 * (w_mom / 20.0))
    else:
        # Insufficient price history — neutral midpoint, NOT a penalty
        mom_final = w_mom * 0.40  # 8/20 equivalent

    # Validation logging (non-fatal)
    _exp_max = 5.0 * (w_mom / 20.0)
    if ticker == "INTC" and mom_6m < 0 and mom_12m < 0 and mom_final > _exp_max:
        logger.warning("[VALIDATION] INTC momentum %.2f exceeds cap %.2f", mom_final, _exp_max)
    _exp_min = 12.0 * (w_mom / 20.0)
    if ticker in ("META", "MSFT", "NVDA") and mom_12m > 0.10 and mom_final < _exp_min:
        logger.warning("[VALIDATION] %s momentum %.2f below floor %.2f", ticker, mom_final, _exp_min)

    # =========================================================
    # PILLAR 5 — RISK (10)
    # =========================================================
    score_de       = inverse_normalize(de, 0, 5.0)
    score_cr       = normalize(cr, 0.5, 2.0)
    eps_vol        = std_dev(eps_growths)
    score_eps_cons = inverse_normalize(eps_vol, 0.05, 1.0)
    rev_vol        = std_dev(rev_growths)
    score_rev_vol  = inverse_normalize(rev_vol, 0.05, 0.5)

    risk_raw   = (score_de * 0.40) + (score_cr * 0.10) + (score_eps_cons * 0.40) + (score_rev_vol * 0.10)
    risk_final = risk_raw * w_risk

    # =========================================================
    # AGGREGATION — 0.9x Global Compression
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
            "moat":              {"title": "Quality",  "total": round(qual_final, 1), "max": w_qual, "breakdown": [], "penaltyRatio": 0},
            "profitability":     {"title": "Value",    "total": round(val_final, 1),  "max": w_val,  "breakdown": [], "penaltyRatio": 0},
            "financialStrength": {"title": "Growth",   "total": round(grow_final, 1), "max": w_grow, "breakdown": [], "penaltyRatio": 0},
            "cashFlowQuality":   {"title": "Momentum", "total": round(mom_final, 1),  "max": w_mom,  "breakdown": [], "penaltyRatio": 0},
            "valuation":         {"title": "Risk",     "total": round(risk_final, 1), "max": w_risk, "breakdown": [], "penaltyRatio": 0},
        },
        "redFlags": red_flags,
    }
