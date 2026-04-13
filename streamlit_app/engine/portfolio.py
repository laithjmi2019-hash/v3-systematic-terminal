import numpy as np
import pandas as pd
from engine.math_utils import std_dev

def allocate_capital(scored_stocks: list, max_pos=0.15, min_pos=0.02, sector_cap=0.30) -> list:
    """
    V9 Mean-Variance Optimization (MVO) Engine.
    Maximizes Conviction-Adjusted Sharpe Ratio using Modern Portfolio Theory.
    """
    from scipy.optimize import minimize
    import warnings
    warnings.filterwarnings("ignore")
    
    if not scored_stocks:
        return []
    
    n = len(scored_stocks)
    if n == 1:
        return [{"ticker": scored_stocks[0]["ticker"], "weight": 1.0}]
        
    # Build Returns Matrix
    min_len = min([len(s.get("return_history", [])) for s in scored_stocks])
    if min_len < 20: 
        # Fallback to naive score weighting if history too short
        total_score = sum([max(s['score'], 1) for s in scored_stocks])
        return [{"ticker": s["ticker"], "weight": max(s['score'], 1) / total_score} for s in scored_stocks]
        
    ret_matrix = []
    scores = []
    for s in scored_stocks:
        ret_matrix.append(s["return_history"][-min_len:])
        scores.append(s["score"] / 100.0) # V9: Use structural score as forward expected drift
        
    ret_matrix = np.array(ret_matrix)
    cov_matrix = np.cov(ret_matrix)
    exp_returns = np.array(scores)
    
    # Objective: Minimize Negative Sharpe Ratio
    def objective(weights):
        port_return = np.dot(weights, exp_returns)
        port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        if port_vol == 0: return 0
        return - (port_return / port_vol)
        
    cons = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0})
    bounds = tuple((min_pos, max_pos) for _ in range(n))
    initial_w = np.array([1.0/n for _ in range(n)])
    
    try:
        opt_res = minimize(objective, initial_w, method='SLSQP', bounds=bounds, constraints=cons)
        weights = opt_res.x if opt_res.success else initial_w
    except:
        weights = initial_w
        
    # Ensure precision mapping
    weights = weights / np.sum(weights)
    
    allocations = []
    for i, s in enumerate(scored_stocks):
        w = float(weights[i])
        if w > 0.001:
            allocations.append({"ticker": s["ticker"], "weight": w})
            
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
