import logging
from engine.math_utils import normalize, inverse_normalize, std_dev

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  V8 Institutional Alpha Engine
#
#  4 Pillars:  Quality(30) | Value(25) | Growth(25) | Momentum(20) = 100
#
#  Design Rules:
#    1. Fixed weights. Macro does NOT change scoring. (Macro → position sizing)
#    2. No penalty stacking. Each sub-score is one normalization.
#       Each pillar gets ONE cap layer at most.
#    3. Missing data → slight pessimism (0.35), NOT death spiral.
#    4. Risk is a hard-fail gate, not a scored pillar.
#    5. No global compression. If pillars are calibrated, you don't need it.
#    6. Quality uses 3-year averages for stability (penalises one-year spikes).
#    7. ROIC is computed properly, not proxied.
# ---------------------------------------------------------------------------

MISSING = 0.35        # default sub-score when data is unavailable
W_QUAL  = 30
W_VAL   = 25
W_GROW  = 25
W_MOM   = 20


def evaluate_stock(ticker: str, financials: list, quote: dict,
                   macro_state: dict = None, hist_returns: dict = None):

    red_flags = []

    sorted_fin = sorted(financials, key=lambda x: x.get("date", ""), reverse=True)
    if not sorted_fin:
        return {"error": "No financials"}

    current  = sorted_fin[0]
    recent_3 = sorted_fin[:min(len(sorted_fin), 3)]

    # ----- raw data -----
    fwd_pe    = float(quote.get("peForward", 0) or 0)
    curr_pfcf = float(quote.get("pfcf", 0) or 0)
    div_yield = float(quote.get("dividendYield", 0) or 0)
    has_pe    = fwd_pe > 0
    has_pfcf  = curr_pfcf > 0

    de = (current.get("totalDebt", 0) / current.get("totalEquity", 1)
          if current.get("totalEquity", 0) > 0 else 3.0)

    # ----- hard-fail gates (binary, not scored) -----
    hard_fail = False
    if de > 5.0:
        red_flags.append({"severity": "CRITICAL",
                          "message": "Extreme leverage (D/E > 5)", "metric": "D/E"})
        hard_fail = True

    neg_fcf_yrs = sum(1 for f in sorted_fin[:3] if (f.get("freeCashFlow", 0) or 0) < 0)
    if neg_fcf_yrs >= 3:
        red_flags.append({"severity": "CRITICAL",
                          "message": "Persistent negative FCF (3 yr)", "metric": "FCF"})
        hard_fail = True

    # ==================================================================
    #  QUALITY  (30)   —   3-yr averaged: ROE, ROIC, Net Margin, FCF Margin
    # ==================================================================
    roe_vals = [f.get("roe", 0) or 0 for f in recent_3]
    avg_roe  = sum(roe_vals) / len(roe_vals)

    # Real ROIC = NOPAT / Invested Capital
    roic_vals = []
    for f in recent_3:
        ni = f.get("netIncome", 0) or 0
        ie = f.get("interestExpense", 0) or 0
        td = f.get("totalDebt", 0) or 0
        te = f.get("totalEquity", 0) or 0
        invested = td + te
        nopat = ni + ie * 0.75          # after-tax interest add-back (25% rate)
        roic_vals.append(nopat / invested if invested > 0 else 0)
    avg_roic = sum(roic_vals) / len(roic_vals) if roic_vals else 0

    nm_vals = [f.get("netMargin", 0) or 0 for f in recent_3]
    avg_nm  = sum(nm_vals) / len(nm_vals)

    fcfm_vals = []
    for f in recent_3:
        rev = f.get("revenue", 0) or 0
        fcf = f.get("freeCashFlow", 0) or 0
        if rev > 0:
            fcfm_vals.append(fcf / rev)
    avg_fcfm = sum(fcfm_vals) / len(fcfm_vals) if fcfm_vals else 0

    s_roe  = normalize(avg_roe,  0, 0.18)     # 18% = max
    s_roic = normalize(avg_roic, 0, 0.15)     # 15% = max
    s_nm   = normalize(avg_nm,   0, 0.20)     # 20% = max
    s_fcfm = normalize(avg_fcfm, 0, 0.15)     # 15% = max

    qual_raw   = s_roe*0.30 + s_roic*0.30 + s_nm*0.20 + s_fcfm*0.20
    qual_final = round(qual_raw * W_QUAL, 1)

    # ==================================================================
    #  VALUE  (25)   —   PE, PEG, P/FCF.  ONE cap layer.  No penalty chain.
    # ==================================================================
    # Growth rates (needed for PEG and Growth pillar)
    rev_growths = []
    for i in range(min(len(sorted_fin) - 1, 4)):
        r1 = sorted_fin[i].get("revenue", 0) or 0
        r2 = sorted_fin[i + 1].get("revenue", 0) or 0
        if r2 > 0:
            rev_growths.append((r1 - r2) / r2)
    avg_rev_g = sum(rev_growths) / len(rev_growths) if rev_growths else 0

    eps_growths = []
    for i in range(min(len(sorted_fin) - 1, 4)):
        e1 = sorted_fin[i].get("netIncome", 0) or 0
        e2 = sorted_fin[i + 1].get("netIncome", 0) or 0
        if e2 > 0:
            eps_growths.append((e1 - e2) / e2)
    avg_eps_g = sum(eps_growths) / len(eps_growths) if eps_growths else 0

    best_g_pct = max(avg_rev_g, avg_eps_g, 0.0) * 100

    # PE component (40%)
    score_pe = inverse_normalize(fwd_pe, 10, 35) if has_pe else MISSING

    # PEG component (30%)
    peg     = 0.0
    use_peg = best_g_pct >= 5.0 and has_pe
    if use_peg:
        peg       = fwd_pe / best_g_pct if best_g_pct > 0 else 5.0
        score_peg = inverse_normalize(peg, 0.8, 3.0)
    elif not has_pe:
        score_peg = MISSING
    else:
        # Low-growth: score on dividend yield instead
        d = normalize(div_yield, 0.0, 0.05)
        f = inverse_normalize(curr_pfcf, 5, 40) if has_pfcf else MISSING
        score_peg = d * 0.6 + f * 0.4

    # P/FCF component (30%)
    score_pfcf = inverse_normalize(curr_pfcf, 5, 40) if has_pfcf else MISSING

    val_raw   = score_pe * 0.40 + score_peg * 0.30 + score_pfcf * 0.30
    val_final = val_raw * W_VAL

    # V9: Sector-Relative Cap Layer
    if has_pe:
        SECTOR_PE = {
            "Technology": 28.0, "Healthcare": 22.0, "Financial Services": 14.0,
            "Consumer Cyclical": 20.0, "Industrials": 21.0, "Energy": 12.0,
            "Consumer Defensive": 20.0, "Utilities": 17.0, "Real Estate": 25.0,
            "Basic Materials": 15.0, "Communication Services": 19.0, "DEFAULT": 20.0
        }
        sec_pe = SECTOR_PE.get(quote.get("sector", "DEFAULT"), 20.0)
        pe_ratio = fwd_pe / sec_pe
        
        if   pe_ratio > 3.0:  val_final = min(val_final, 6.0)
        elif pe_ratio > 2.0:  val_final = min(val_final, 12.0)
        elif pe_ratio > 1.5:  val_final = min(val_final, 18.0)

    val_final = round(max(0.0, val_final), 1)

    logger.debug("[VALUE %s] pe=%.1f pfcf=%.1f peg=%.2f → val=%.1f",
                 ticker, fwd_pe, curr_pfcf, peg, val_final)

    # ==================================================================
    #  GROWTH  (25)   —   Revenue CAGR + EPS CAGR + Revisions Momentum
    # ==================================================================
    s_rev_g = normalize(avg_rev_g, 0, 0.15)   # 15% = max
    s_eps_g = normalize(avg_eps_g, 0, 0.20)   # 20% = max
    s_revs  = quote.get("revisions_score", 0.5)

    grow_raw   = s_rev_g * 0.40 + s_eps_g * 0.40 + s_revs * 0.20
    grow_final = round(grow_raw * W_GROW, 1)

    # ==================================================================
    #  MOMENTUM  (20)   —   12M(50%) + 6M(30%) + Rel vs SPY(20%)
    # ==================================================================
    mom_6m, mom_12m, mom_rel = 0.0, 0.0, 0.0
    has_mom = False

    p_t, p_spy = [], []

    if hist_returns and ticker in hist_returns and "SPY" in hist_returns:
        p_t   = hist_returns[ticker]
        p_spy = hist_returns["SPY"]
    else:
        from data.fmp import get_historical_prices
        t_px = get_historical_prices(ticker, days=252)
        s_px = get_historical_prices("SPY",   days=252)
        p_t   = [x["close"] for x in t_px]
        p_spy = [x["close"] for x in s_px]

    if len(p_t) >= 126 and p_t[-126] > 0:
        has_mom = True
        mom_6m = (p_t[-1] / p_t[-126]) - 1.0

    if len(p_t) >= 200:
        idx12 = min(len(p_t), 252)
        if p_t[-idx12] > 0:
            mom_12m = (p_t[-1] / p_t[-idx12]) - 1.0
        idx_s = min(len(p_spy), 252)
        if idx_s > 100 and p_spy[-idx_s] > 0:
            spy_12m = (p_spy[-1] / p_spy[-idx_s]) - 1.0
            mom_rel = mom_12m - spy_12m

    logger.debug("[MOM %s] 6m=%.3f 12m=%.3f rel=%.3f pts=%d",
                 ticker, mom_6m, mom_12m, mom_rel, len(p_t))

    if has_mom:
        import numpy as np
        
        # Calculate trailing volatility to penalize erratic returns
        ann_vol = 0.20
        if len(p_t) > 126:
            # We already have oldest-first daily prices
            arr = np.array(p_t[-252:])
            daily_returns = np.diff(arr) / arr[:-1]
            ann_vol = np.std(daily_returns) * np.sqrt(252) if len(daily_returns) > 0 else 0.20
            ann_vol = max(ann_vol, 0.05) # Prevent divide-by-zero
        
        # Risk-adjusted (Sharpe-esque)
        sharpe_12m = mom_12m / ann_vol
        sharpe_6m = mom_6m / ann_vol
        sharpe_rel = mom_rel / ann_vol
        
        # Normalize sharpe variants
        s_m12 = max(0.0, min(1.0, (sharpe_12m + 0.5) / 2.0))
        s_m6  = max(0.0, min(1.0, (sharpe_6m  + 0.5) / 2.0))
        s_mrl = max(0.0, min(1.0, (sharpe_rel + 0.5) / 2.0))

        mom_raw   = s_m12 * 0.50 + s_m6 * 0.30 + s_mrl * 0.20
        mom_final = mom_raw * W_MOM

        # Hard caps for negative trends (still apply the risk gates)
        if mom_12m < 0:
            mom_final = min(mom_final, 8.0)
        if mom_6m < 0 and mom_12m < 0:
            mom_final = min(mom_final, 5.0)
    else:
        mom_final = 8.0      # neutral when data missing

    mom_final = round(mom_final, 1)

    # ==================================================================
    #  AGGREGATION   —   no compression, no extra deductions
    # ==================================================================
    total = qual_final + val_final + grow_final + mom_final

    if hard_fail:
        total = min(total, 30.0)

    total = round(max(0.0, total), 1)

    # ----- action classification -----
    if hard_fail:
        action = "AVOID"
    elif total >= 75 and mom_final >= 14:
        action = "STRONG BUY"
    elif total >= 65:
        action = "ACCUMULATE"
    elif total >= 50:
        action = "HOLD"
    elif total >= 35:
        action = "WATCH"
    else:
        action = "AVOID"

    # Macro downgrade (only thing macro touches)
    if macro_state and "Risk-OFF" in str(macro_state.get("state", "")):
        order = ["AVOID", "WATCH", "HOLD", "ACCUMULATE", "STRONG BUY"]
        idx = order.index(action) if action in order else 0
        if idx > 0:
            action = order[idx - 1]

    confidence = ("High" if (has_pe and has_pfcf and has_mom)
                  else "Medium" if (has_pe or has_pfcf) and has_mom
                  else "Low")

    # ----- return -----
    return {
        "ticker":           ticker,
        "baseScore":        total,
        "totalScore":       total,
        "macroMultiplier":  1.0,
        "verdict":          action,
        "action":           action,
        "confidence":       confidence,
        "scoreMomentum":    0.0,
        "dataQualityLabel": confidence,
        "dataQualityPct":   {"High": 0.95, "Medium": 0.75, "Low": 0.50}[confidence],
        "pillars": {
            "moat": {
                "title": "Quality", "total": qual_final, "max": W_QUAL,
                "breakdown": [
                    {"metric": "ROE (3yr avg)",        "value": f"{avg_roe*100:.1f}%",  "score": round(s_roe  * W_QUAL * 0.30, 1)},
                    {"metric": "ROIC (3yr avg)",       "value": f"{avg_roic*100:.1f}%", "score": round(s_roic * W_QUAL * 0.30, 1)},
                    {"metric": "Net Margin (3yr avg)", "value": f"{avg_nm*100:.1f}%",   "score": round(s_nm   * W_QUAL * 0.20, 1)},
                    {"metric": "FCF Margin (3yr avg)", "value": f"{avg_fcfm*100:.1f}%", "score": round(s_fcfm * W_QUAL * 0.20, 1)},
                ],
                "penaltyRatio": 0,
            },
            "profitability": {
                "title": "Value", "total": val_final, "max": W_VAL,
                "breakdown": [
                    {"metric": "Forward P/E", "value": f"{fwd_pe:.1f}" if has_pe else "N/A",     "score": round(score_pe   * W_VAL * 0.40, 1)},
                    {"metric": "PEG Ratio",   "value": f"{peg:.2f}"    if use_peg else "N/A",    "score": round(score_peg  * W_VAL * 0.30, 1)},
                    {"metric": "P/FCF",       "value": f"{curr_pfcf:.1f}" if has_pfcf else "N/A","score": round(score_pfcf * W_VAL * 0.30, 1)},
                ],
                "penaltyRatio": 0,
            },
            "financialStrength": {
                "title": "Growth", "total": grow_final, "max": W_GROW,
                "breakdown": [
                    {"metric": "Revenue CAGR", "value": f"{avg_rev_g*100:.1f}%", "score": round(s_rev_g * W_GROW * 0.50, 1)},
                    {"metric": "EPS CAGR",     "value": f"{avg_eps_g*100:.1f}%", "score": round(s_eps_g * W_GROW * 0.50, 1)},
                ],
                "penaltyRatio": 0,
            },
            "cashFlowQuality": {
                "title": "Momentum", "total": mom_final, "max": W_MOM,
                "breakdown": [
                    {"metric": "12-Month Return", "value": f"{mom_12m*100:+.1f}%", "score": "—"},
                    {"metric": "6-Month Return",  "value": f"{mom_6m*100:+.1f}%",  "score": "—"},
                    {"metric": "Rel vs SPY",      "value": f"{mom_rel*100:+.1f}%", "score": "—"},
                ],
                "penaltyRatio": 0,
            },
        },
        "redFlags": red_flags,
    }
