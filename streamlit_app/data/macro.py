def get_macro_state():
    # Stub mapped out, assuming static for V3 demonstration
    # In full production we'd `requests.get` to FRED
    multiplier = 1.0
    phase = "EXPANSION"
    
    return {
        "phase": phase,
        "rateTrend": "RISING",
        "liquidityTrend": "RISING",
        "multiplier": multiplier
    }
