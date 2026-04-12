import datetime
import pandas as pd
from data.database import get_price_history

def get_macro_state(date_str: str = None) -> dict:
    """
    V6 Dynamic Allocation Engine.
    Computes Risk Score (0-100) using: SPY trend (35%), Breadth proxy (30%), VIX (20%), Rates (15%).
    Output states: Risk-ON (>70), Neutral (40-70), Risk-OFF (<40).
    """
    try:
        spy_df = get_price_history("SPY")
        hyg_df = get_price_history("HYG")
        tlt_df = get_price_history("TLT")
        rsp_df = get_price_history("RSP")
        vix_df = get_price_history("^VIX")
        tnx_df = get_price_history("^TNX")

        if date_str:
            spy_df = spy_df[spy_df['date'] <= date_str]
            hyg_df = hyg_df[hyg_df['date'] <= date_str]
            tlt_df = tlt_df[tlt_df['date'] <= date_str]
            rsp_df = rsp_df[rsp_df['date'] <= date_str]
            vix_df = vix_df[vix_df['date'] <= date_str]
            tnx_df = tnx_df[tnx_df['date'] <= date_str]

        risk_score = 50.0 # Default Neutral
        
        if len(spy_df) > 200:
            # SPY Trend (35%)
            spy_close = spy_df.iloc[-1]['close']
            spy_200 = spy_df['close'].tail(200).mean()
            spy_signal = 35 if spy_close > spy_200 else 0

            # Breadth Proxy (30%)
            # Comp A: HYG/TLT short vs long MA
            hyg_tlt = (hyg_df['close'].tail(200).reset_index(drop=True) / tlt_df['close'].tail(200).reset_index(drop=True)).fillna(0)
            if len(hyg_tlt) >= 200:
                ht_50 = hyg_tlt.tail(50).mean()
                ht_200 = hyg_tlt.tail(200).mean()
                comp_a = 21 if ht_50 > ht_200 else 0 # 70% of 30 = 21
            else: comp_a = 10
            
            # Comp B: RSP vs SPY 3-month (63 days) return
            if len(rsp_df) > 63:
                rsp_ret = (rsp_df.iloc[-1]['close'] - rsp_df.iloc[-63]['close']) / rsp_df.iloc[-63]['close']
                spy_ret = (spy_df.iloc[-1]['close'] - spy_df.iloc[-63]['close']) / spy_df.iloc[-63]['close']
                comp_b = 9 if rsp_ret > spy_ret else 0 # 30% of 30 = 9
            else: comp_b = 4

            breadth_signal = comp_a + comp_b

            # VIX Level (20%)
            vix = vix_df.iloc[-1]['close'] if not vix_df.empty else 20.0
            if vix < 20: vix_signal = 20
            elif vix < 30: vix_signal = 10
            else: vix_signal = 0

            # 10Y Yield Trend (15%)
            if len(tnx_df) > 50:
                tnx_50 = tnx_df['close'].tail(50).mean()
                tnx_now = tnx_df.iloc[-1]['close']
                rates_signal = 15 if tnx_now < tnx_50 else 0 # Falling yields = risk positive
            else: rates_signal = 7
            
            risk_score = spy_signal + breadth_signal + vix_signal + rates_signal
            
        # Conflict Detection Layer (Phase 16)
        # SPY mapping: trend positive > 200ma (signal > 0), Breadth mapping: spread negative (signal < 15)
        is_conflicting = False
        if (spy_signal > 0 and breadth_signal < 15) or (spy_signal == 0 and breadth_signal > 20):
            is_conflicting = True

        # State assignment
        if risk_score > 70:
            state = "Risk-ON"
            exposure_limit = 1.0 # 100% target max
            exposure_range = "90-100%"
        elif risk_score < 40:
            state = "Risk-OFF"
            exposure_limit = 0.3 # 30% target max
            exposure_range = "10-30%"
        else:
            state = "Neutral"
            exposure_limit = 0.7 # 70% target max
            exposure_range = "50-70%"
            
        if is_conflicting:
            state += " (Conflict)"
            exposure_limit = min(exposure_limit, 0.5)
            exposure_range = "Maximum 50% (Hedged)"

        return {
            "riskScore": risk_score,
            "state": state,
            "exposure": exposure_range,
            "exposureTarget": exposure_limit,
            "multiplier": 1.1 if "Risk-ON" in state else (0.8 if "Risk-OFF" in state else 1.0)
        }
    except Exception as e:
        return {"riskScore": 50, "state": "Neutral", "exposure": "50-70%", "exposureTarget": 0.5, "multiplier": 1.0}
