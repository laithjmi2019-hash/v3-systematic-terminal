def calculate_alpha_and_rank(result: dict) -> dict:
    """
    V8 — Alpha score IS the total score. No separate re-computation.
    Just classifies into ranking tiers.
    """
    if "error" in result:
        return result

    score = result.get("totalScore", 0)

    if score > 80:
        ranking = "Elite Alpha"
    elif score > 65:
        ranking = "High Alpha"
    elif score > 50:
        ranking = "Market Outperformer"
    elif score > 35:
        ranking = "Near-Market"
    else:
        ranking = "Underperformer"

    action = result.get("action", result.get("verdict", ""))
    if action == "AVOID":
        ranking = "Underperformer"

    result["alphaScore"]      = score
    result["alphaRankingStr"] = ranking

    return result
