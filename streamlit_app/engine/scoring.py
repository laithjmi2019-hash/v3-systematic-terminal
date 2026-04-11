from engine.math_utils import clamp, normalize, inverse_normalize, calculate_volatility_penalty, std_dev

def evaluate_stock(ticker: str, financials: list, quote: dict, macro_multiplier: float = 1.0, is_momentum_run=False):
    red_flags = []
    
    # Sort newest first
    sorted_fin = sorted(financials, key=lambda x: x.get("date", ""), reverse=True)
    if not sorted_fin:
        return {"error": "No financials"}
        
    current = sorted_fin[0]
    
    # Data Quality Check
    key_metrics = ["revenue", "grossMargin", "netMargin", "roe", "roa", "freeCashFlow", "totalAssets", "sharesOutstanding", "totalDebt", "totalEquity", "interestExpense"]
    valid_count = sum(1 for k in key_metrics if current.get(k) is not None and current.get(k) != 0)
    data_quality_pct = valid_count / len(key_metrics)
    dq_label = "Reliable" if data_quality_pct > 0.9 else "Moderate" if data_quality_pct >= 0.7 else "Low Confidence"

    # Series for Penalties
    gm_series = [f.get("grossMargin", 0) for f in sorted_fin]
    nm_series = [f.get("netMargin", 0) for f in sorted_fin]
    fcf_series = [f.get("freeCashFlow", 0) for f in sorted_fin]
    
    def build_breakdown(metric, raw_score, weight, max_pillar, val_str, exp):
        base_points = raw_score * (weight * max_pillar)
        return {
            "metric": metric, "points": base_points, "basePoints": base_points, 
            "maxPoints": weight * max_pillar, "passed": raw_score > 0.4, 
            "value": val_str, "explanation": exp
        }

    # 1. MOAT (Max 20)
    current_gm = current.get("grossMargin", 0)
    gm_score = normalize(current_gm, 0.20, 0.80)
    
    rev_growths = []
    for i in range(len(sorted_fin)-1):
        if sorted_fin[i+1].get("revenue", 0) > 0:
            rev_growths.append((sorted_fin[i]["revenue"] - sorted_fin[i+1]["revenue"]) / sorted_fin[i+1]["revenue"])
    
    rev_cons_score = 1.0 / (1.0 + std_dev(rev_growths))
    gm_stab_score = 1.0 / (1.0 + std_dev(gm_series))

    moat_raw = (0.4 * gm_score) + (0.3 * gm_stab_score) + (0.3 * rev_cons_score)
    moat_base = moat_raw * 20
    moat_penalty = calculate_volatility_penalty(rev_growths)
    moat_total = moat_base * (1 - moat_penalty)

    p_moat = {
        "title": "Moat & Stability", "total": round(moat_total, 1), "baseScore": round(moat_base, 1), 
        "penaltyRatio": moat_penalty, "max": 20, "breakdown": [
            build_breakdown("Gross Margin", gm_score, 0.4, 20, f"{current_gm*100:.1f}%", "Normalized 20-80%"),
            build_breakdown("Margin Stability", gm_stab_score, 0.3, 20, f"{std_dev(gm_series):.2f} SD", "Inverse Volatility"),
            build_breakdown("Revenue Consistency", rev_cons_score, 0.3, 20, f"{std_dev(rev_growths):.2f} SD", "Inverse Volatility")
        ]
    }

    # 2. PROFITABILITY (Max 15)
    current_roe = current.get("roe", 0)
    current_nm = current.get("netMargin", 0)
    current_roa = current.get("roa", 0)
    
    roe_score = normalize(current_roe, 0, 0.30)
    nm_score = normalize(current_nm, 0, 0.25)
    roa_score = normalize(current_roa, 0, 0.15)
    
    prof_base = ((0.4 * roe_score) + (0.3 * nm_score) + (0.3 * roa_score)) * 15
    prof_penalty = calculate_volatility_penalty(nm_series)
    prof_total = prof_base * (1 - prof_penalty)

    p_prof = {
        "title": "Profitability", "total": round(prof_total, 1), "baseScore": round(prof_base, 1), 
        "penaltyRatio": prof_penalty, "max": 15, "breakdown": [
            build_breakdown("ROE", roe_score, 0.4, 15, f"{current_roe*100:.1f}%", "Normalized 0-30%"),
            build_breakdown("Net Margin", nm_score, 0.3, 15, f"{current_nm*100:.1f}%", "Normalized 0-25%"),
            build_breakdown("ROA", roa_score, 0.3, 15, f"{current_roa*100:.1f}%", "Normalized 0-15%")
        ]
    }

    # 3. FINANCIAL STRENGTH (Max 15)
    de = current.get("totalDebt", 0) / current.get("totalEquity", 1) if current.get("totalEquity", 0) > 0 else 2.5
    de_score = inverse_normalize(de, 0, 2.0)
    
    # Int Cov
    ie = abs(current.get("interestExpense", 0))
    ic = (current.get("netIncome", 0) + ie) / ie if ie > 0 else 10
    ic_score = normalize(ic, 1, 10)
    
    cr = 1.5 # stub
    cr_score = normalize(cr, 1, 3)
    
    fin_base = ((0.4 * cr_score) + (0.4 * de_score) + (0.2 * ic_score)) * 15

    p_fin = {
        "title": "Financial Strength", "total": round(fin_base, 1), "baseScore": round(fin_base, 1), 
        "penaltyRatio": 0, "max": 15, "breakdown": [
            build_breakdown("Current Ratio", cr_score, 0.4, 15, f"{cr:.1f}", "Normalized 1-3"),
            build_breakdown("Debt to Equity", de_score, 0.4, 15, f"{de:.1f}", "Inverted 0-2"),
            build_breakdown("Interest Coverage", ic_score, 0.2, 15, f"{ic:.1f}", "Normalized 1-10"),
        ]
    }

    # 4. CASH FLOW QUALITY (Max 15)
    fcf_growths = []
    for i in range(min(len(sorted_fin)-1, 5)):
        if sorted_fin[i+1].get("freeCashFlow", 0) != 0:
            fcf_growths.append((sorted_fin[i]["freeCashFlow"] - sorted_fin[i+1]["freeCashFlow"]) / abs(sorted_fin[i+1]["freeCashFlow"]))
    
    fcf_g_avg = sum(fcf_growths)/len(fcf_growths) if fcf_growths else 0
    fcf_g_score = normalize(fcf_g_avg, 0, 0.20)
    
    # Capital Allocation (V3 Rule: Dilution trend, Buybacks, ROE consist)
    shares_now = current.get("sharesOutstanding", 0)
    shares_old = sorted_fin[min(len(sorted_fin)-1, 3)].get("sharesOutstanding", shares_now) if len(sorted_fin) > 1 else shares_now
    dilution_growth = (shares_now - shares_old) / shares_old if shares_old > 0 else 0
    cap_alloc_score = inverse_normalize(dilution_growth, -0.05, 0.05) # rewarded for negative (buybacks), penalized for positive
    
    cf_base = ((0.5 * fcf_g_score) + (0.5 * cap_alloc_score)) * 15
    cf_penalty = calculate_volatility_penalty(fcf_series)
    cf_total = cf_base * (1 - cf_penalty)

    p_cf = {
        "title": "Cash Flow Quality", "total": round(cf_total, 1), "baseScore": round(cf_base, 1),
        "penaltyRatio": cf_penalty, "max": 15, "breakdown": [
            build_breakdown("FCF Growth", fcf_g_score, 0.5, 15, f"{fcf_g_avg*100:.1f}%", "Normalized 0-20%"),
            build_breakdown("Capital Allocation", cap_alloc_score, 0.5, 15, "Composite", "Buyback vs Dilution")
        ]
    }

    # 5. VALUATION (Max 15)
    fwd_pe = quote.get("peForward", 0)
    
    # Historical PE computation: Avg Price / EPS (or NI/Shares) over 5 yrs
    hist_pes = []
    for i in range(min(len(sorted_fin), 5)):
        ni = sorted_fin[i].get("netIncome", 0)
        sh = sorted_fin[i].get("sharesOutstanding", 1)
        eps = ni / sh if sh > 0 else 0
        if eps > 0:
            hist_pes.append(quote.get("price", 0) / eps) # simplified hist PE using current price, true hist PE requires hist price!
            
    hist_pe = sum(hist_pes)/len(hist_pes) if hist_pes else 15
    
    pe_score = inverse_normalize(fwd_pe if fwd_pe > 0 else hist_pe, 10, 40)
    pfcf_score = inverse_normalize(quote.get("pfcf", 0), 8, 30)

    val_base = ((0.5 * pe_score) + (0.5 * pfcf_score)) * 15

    p_val = {
        "title": "Valuation", "total": round(val_base, 1), "baseScore": round(val_base, 1),
        "penaltyRatio": 0, "max": 15, "breakdown": [
             build_breakdown("P/E Ratio", pe_score, 0.5, 15, f"{fwd_pe if fwd_pe>0 else hist_pe:.1f}", "Inverted 10-40"),
             build_breakdown("P/FCF", pfcf_score, 0.5, 15, f"{quote.get('pfcf',0):.1f}", "Inverted 8-30")
        ]
    }

    # --- Accruals Earnings Quality & PE Check (V3) ---
    ni = current.get("netIncome", 0)
    fcf = current.get("freeCashFlow", 0)
    ta = current.get("totalAssets", 1) or 1
    accruals = (ni - fcf) / ta
    if accruals > 0.20:
        red_flags.append({"severity": "CRITICAL", "message": "High Accruals Ratio. Manipulated earnings risk.", "metric": "Accruals", "value": f"{accruals*100:.1f}%"})
    elif accruals > 0.10:
        red_flags.append({"severity": "WARNING", "message": "Elevated Accruals Ratio.", "metric": "Accruals", "value": f"{accruals*100:.1f}%"})

    if fwd_pe > hist_pe * 1.2 and hist_pe > 0:
        red_flags.append({"severity": "WARNING", "message": "Forward PE >> Historical PE. Over-optimism.", "metric": "Valuation", "value": "Elevated"})

    # Aggregate
    base_total = p_moat["total"] + p_prof["total"] + p_fin["total"] + p_cf["total"] + p_val["total"]
    sys_total = base_total * macro_multiplier

    # --- Hard Fails ---
    neg_fcf_years = sum(1 for f in sorted_fin[:3] if f.get("freeCashFlow", 0) < 0)
    hard_fail = False

    if de > 2: red_flags.append({"severity": "CRITICAL", "message": "Debt/Equity > 2.", "metric": "D/E"}); hard_fail = True;
    if neg_fcf_years >= 3: red_flags.append({"severity": "CRITICAL", "message": "Neg FCF 3+ yrs.", "metric": "FCF"}); hard_fail = True;
    if dilution_growth > 0.05: red_flags.append({"severity": "CRITICAL", "message": "Dilution > 5%.", "metric": "Dilution"}); hard_fail = True;
    if ic < 2: red_flags.append({"severity": "CRITICAL", "message": "Int Cov < 2.", "metric": "Coverage"}); hard_fail = True;

    # --- Pillar Cap Constraint ---
    pillars_obj = [p_moat, p_prof, p_fin, p_cf, p_val]
    # Check if ANY pillar < 20%
    if any((p["total"] / p["max"]) < 0.20 for p in pillars_obj) and not hard_fail:
        strong_pillars = sum(1 for p in pillars_obj if (p["total"] / p["max"]) > 0.60)
        max_cap = 30 + (strong_pillars * 5)
        sys_total = min(sys_total, max_cap)
        red_flags.append({"severity": "WARNING", "message": f"Pillar imbalance detected. Score capped at {max_cap}.", "metric": "Cap Limit"})

    if hard_fail:
        sys_total = min(sys_total, 30)
        red_flags.append({"severity": "CRITICAL", "message": "Systematic Hard Fail active.", "metric": "VERDICT"})

    verdict = "PASS" if sys_total >= 50 else ("WATCH" if sys_total >= 30 else "AVOID")
    if hard_fail: verdict = "AVOID"

    # --- Momentum calculation ---
    score_momentum = 0
    if not is_momentum_run and len(sorted_fin) > 1:
        prev_res = evaluate_stock(ticker, sorted_fin[1:], quote, macro_multiplier, is_momentum_run=True)
        if isinstance(prev_res, dict) and "totalScore" in prev_res:
            score_momentum = sys_total - prev_res["totalScore"]

    return {
        "ticker": ticker,
        "baseScore": round(base_total, 1),
        "totalScore": round(sys_total, 1),
        "macroMultiplier": macro_multiplier,
        "verdict": verdict,
        "scoreMomentum": round(score_momentum, 1),
        "dataQualityLabel": dq_label,
        "dataQualityPct": data_quality_pct,
        "pillars": {
            "moat": p_moat,
            "profitability": p_prof,
            "financialStrength": p_fin,
            "cashFlowQuality": p_cf,
            "valuation": p_val
        },
        "redFlags": red_flags
    }
