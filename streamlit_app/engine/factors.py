import statsmodels.api as sm
import numpy as np
import pandas as pd

def calculate_factor_loads(port_returns: list, spy_returns: list) -> dict:
    # Requires arrays of equal length. We align them prior to calling.
    if len(port_returns) < 10 or len(spy_returns) < 10:
        return {"MarketBeta": 1.0, "Alpha": 0.0, "R_squared": 0.0}
        
    y = np.array(port_returns)
    X = np.array(spy_returns)
    
    # Add constant for Alpha
    X_sm = sm.add_constant(X)
    
    try:
        model = sm.OLS(y, X_sm)
        results = model.fit()
        
        alpha = float(results.params[0])
        beta = float(results.params[1] if len(results.params) > 1 else 1.0)
        r2 = float(results.rsquared)
        
        return {
            "MarketBeta": round(beta, 2),
            "Alpha": round(alpha * 252, 4), # Annualized alpha rough proxy
            "R_squared": round(r2, 2)
        }
    except:
        return {"MarketBeta": 1.0, "Alpha": 0.0, "R_squared": 0.0}
