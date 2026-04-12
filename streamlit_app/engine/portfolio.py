import numpy as np
import pandas as pd
from engine.math_utils import std_dev

def allocate_capital(scored_stocks: list, max_pos=0.07, min_pos=0.02, sector_cap=0.25) -> list:
    """
    V6 Portfolio Constructor Engine.
    Requires list of parsed items: {ticker, score, return_history, sector}
    Weights ∝ Score / Volatility. Applies Sector and Pos constraints.
    """
    allocations = []
    
    # 1. Calculate Score / Vol
    raw_weights = []
    total_raw = 0
    valid_stocks = []
    for s in scored_stocks:
        vol = std_dev(s.get("return_history", []))
        if vol == 0: vol = 0.05 # floor
        w = s["score"] / vol
        raw_weights.append(w)
        total_raw += w
        valid_stocks.append(s)
        
    if total_raw == 0: return []
    
    # 2. Normalize initial
    initial_weights = [w / total_raw for w in raw_weights]
    
    # 3. Apply min/max and sector caps
    final_weights = [0] * len(initial_weights)
    sectors_usage = {}
    
    # iterative greedy fill
    remaining_weight = 1.0
    
    for i, s in enumerate(valid_stocks):
        target = min(initial_weights[i], max_pos)
        target = max(target, min_pos)
        
        sect = s.get("sector", "Unknown")
        curr_sect_w = sectors_usage.get(sect, 0)
        
        if curr_sect_w + target > sector_cap:
            target = max(0, sector_cap - curr_sect_w)
            
        final_weights[i] = target
        sectors_usage[sect] = curr_sect_w + target

    # Normalize final sum to map exactly to 1.0 (some rounding gaps might exist)
    sum_w = sum(final_weights)
    if sum_w > 0:
        final_weights = [w / sum_w for w in final_weights]
        
    for i, s in enumerate(valid_stocks):
        if final_weights[i] > 0:
            allocations.append({
                "ticker": s["ticker"],
                "weight": final_weights[i]
            })
            
    return allocations

# stub for existing UI
def evaluate_portfolio(holdings: list) -> dict:
     return {
         "portfolioRiskScore": 50,
         "maxDrawdown": 0,
         "volatility": 0,
         "riskClassification": "Neutral",
         "signals": [],
         "correlationMatrix": {}
     }
