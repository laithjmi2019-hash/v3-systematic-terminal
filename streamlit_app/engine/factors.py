import statsmodels.api as sm
from statsmodels.regression.rolling import RollingOLS
import numpy as np
import pandas as pd

def calculate_factor_loads(port_returns: list, spy_returns: list) -> dict:
    """
    V6 Rolling Factor Regression Module (Phase 9 constraint)
    Generates point-in-time sequential regressions instead of full-sample static beta.
    """
    if len(port_returns) < 252 or len(spy_returns) < 252:
        return {"MarketBeta": 1.0, "Alpha": 0.0, "R_squared": 0.0, "BetaSeries": [], "AlphaSeries": []}
        
    y = np.array(port_returns)
    X = np.array(spy_returns)
    X_sm = sm.add_constant(X)
    
    try:
        # Use a 12-month (252 day) rolling window
        mod = RollingOLS(y, X_sm, window=252)
        rres = mod.fit()
        
        # params layout: [Alpha, Beta]
        params = rres.params
        
        alphas = params[:, 0] * 252 # annualized roughly
        betas = params[:, 1]
        
        valid_b = betas[~np.isnan(betas)]
        valid_a = alphas[~np.isnan(alphas)]
        
        if len(valid_b) > 0:
            final_beta = valid_b[-1]
            final_alpha = valid_a[-1]
        else:
            final_beta = 1.0 
            final_alpha = 0.0
            
        return {
            "MarketBeta": round(final_beta, 2),
            "Alpha": round(final_alpha, 4),
            "R_squared": 0.0, # rolling r_quared requires extra extraction, omitted for speed
            "BetaSeries": [b if not np.isnan(b) else 1.0 for b in betas.tolist()[-252:]],
        }
    except:
        return {"MarketBeta": 1.0, "Alpha": 0.0, "R_squared": 0.0, "BetaSeries": [], "AlphaSeries": []}
