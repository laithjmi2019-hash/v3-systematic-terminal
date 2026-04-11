def calculate_alpha_and_rank(result: dict) -> dict:
    if "error" in result:
        return result
        
    moat = result["pillars"]["moat"]
    prof = result["pillars"]["profitability"]
    val = result["pillars"]["valuation"]
    fin = result["pillars"]["financialStrength"]

    quality_score = ((moat["total"] / moat["max"]) + (prof["total"] / prof["max"])) / 2
    valuation_score = val["total"] / val["max"]
    fin_strength = fin["total"] / fin["max"]
    
    pen_avg = (moat["penaltyRatio"] + prof["penaltyRatio"] + result["pillars"]["cashFlowQuality"]["penaltyRatio"]) / 3
    consistency_score = 1 - pen_avg
    
    # Macro
    macro = max(0.0, min(1.0, (result["macroMultiplier"] - 0.7) / 0.4))
    
    alpha_decimal = (0.35 * quality_score) + (0.25 * valuation_score) + (0.20 * consistency_score) + (0.10 * fin_strength) + (0.10 * macro)
    alpha_score = round(alpha_decimal * 100, 1)
    
    alpha_ranking = "Underperformer"
    if alpha_score > 85: 
        alpha_ranking = "Elite Alpha"
    elif alpha_score > 75: 
        alpha_ranking = "High Alpha"
    elif alpha_score > 60: 
        alpha_ranking = "Market Outperformer"
        
    if result["verdict"] == "AVOID":
        alpha_ranking = "Underperformer"
        alpha_score = min(alpha_score, 30)
        
    result["alphaScore"] = alpha_score
    result["alphaRankingStr"] = alpha_ranking
    
    return result
