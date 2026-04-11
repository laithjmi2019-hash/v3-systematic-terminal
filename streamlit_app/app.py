import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data.fmp import get_quote, get_historical_financials, resolve_ticker
from data.macro import get_macro_state
from engine.scoring import evaluate_stock
from engine.alpha import calculate_alpha_and_rank
from engine.portfolio import evaluate_portfolio

st.set_page_config(page_title="V3 Institutional Terminal", layout="wide", page_icon="📈")

# ----------- AI STUB -------------
def get_ai_insight(result: dict) -> dict:
    # Stub mapping LLM generation requirement
    confidence_level = "Medium"
    if result.get("dataQualityPct", 0) > 0.9 and not result.get("redFlags"):
        confidence_level = "High"
    elif result.get("dataQualityPct", 0) < 0.7 or len(result.get("redFlags", [])) > 1:
        confidence_level = "Low"
        
    return {
        "Verdict": result.get("verdict", "WATCH"),
        "Reason": "Quantitative metrics dictate precise positioning.",
        "Strengths": ["Stable FCF output" if result.get("totalScore",0) > 40 else "N/A"],
        "Risks": [f.get("message", "N/A") for f in result.get("redFlags", [])] if result.get("redFlags") else ["Volatility exposure"],
        "Action": "Accumulate" if result.get("verdict") == "PASS" else "Wait/Avoid",
        "ConfidenceLevel": confidence_level
    }

# ----------- PAGES ---------------
def page_terminal():
    st.title("Systematic Terminal")
    
    with st.form(key="search_form"):
        raw_input = st.text_input("Enter Ticker or Company Name", "AAPL")
        submitted = st.form_submit_button("Analyze")
    
    if submitted:
        with st.spinner("Resolving query & fetching fundamentals..."):
            ticker = resolve_ticker(raw_input).upper()
            quote = get_quote(ticker)
            financials = get_historical_financials(ticker, 10)
            macro = get_macro_state()
            
            if not financials:
                st.error("Engine failure: Could not extract timeline metrics.")
                return
                
            base_result = evaluate_stock(ticker, financials, quote, macro["multiplier"])
            final_result = calculate_alpha_and_rank(base_result)
            ai = get_ai_insight(final_result)
            
            # Header
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"## {ticker} - ${quote.get('price', 0):.2f}")
                st.caption(f"Alpha Ranking: **{final_result.get('alphaRankingStr')}** (Score: {final_result.get('alphaScore')}/100)")
                if final_result.get("scoreMomentum") != 0:
                    color = "green" if final_result["scoreMomentum"] > 0 else "red"
                    st.markdown(f"<span style='color:{color}'>Momentum: {final_result['scoreMomentum']:+.1f} pts Y/Y</span>", unsafe_allow_html=True)
            with col2:
                verdict_color = "red" if final_result["verdict"] == "AVOID" else "green" if final_result["verdict"] == "PASS" else "orange"
                st.markdown(f"### <div style='text-align: right; color: {verdict_color}'>{final_result['verdict']} : {final_result['totalScore']}/80</div>", unsafe_allow_html=True)
                
            # Data Quality
            st.info(f"Data Quality: {final_result.get('dataQualityLabel')} ({final_result.get('dataQualityPct', 0)*100:.0f}% metrics acquired)")

            # Red flags
            flags = final_result.get("redFlags", [])
            if flags:
                st.error(f"**{len(flags)} HARD ALERTS DETECTED:**")
                for f in flags:
                    st.write(f"- [{f['severity']}] {f['metric']}: {f['message']}")

            # Decision Box
            st.markdown("---")
            st.subheader("AI Decision Intelligence")
            ai_c1, ai_c2, ai_c3 = st.columns(3)
            ai_c1.metric("Confidence Level", ai["ConfidenceLevel"])
            ai_c2.metric("System Action", ai["Action"])
            ai_c3.write(ai["Reason"])
            st.write(f"**Strengths**: {', '.join(ai['Strengths'])}")
            st.write(f"**Risks**: {', '.join(ai['Risks'])}")
            
            st.markdown("---")
            # Radar Chart
            st.subheader("Pillar Breakdown")
            categories = ['Moat', 'Profitability', 'Financial Strength', 'Cash Flow', 'Valuation']
            pillars = final_result["pillars"]
            
            # Map percentages
            r_vals = [
                pillars["moat"]["total"] / pillars["moat"]["max"],
                pillars["profitability"]["total"] / pillars["profitability"]["max"],
                pillars["financialStrength"]["total"] / pillars["financialStrength"]["max"],
                pillars["cashFlowQuality"]["total"] / pillars["cashFlowQuality"]["max"],
                pillars["valuation"]["total"] / pillars["valuation"]["max"]
            ]
            
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=r_vals + [r_vals[0]],
                theta=categories + [categories[0]],
                fill='toself',
                name=ticker
            ))
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # Expanders for details
            for key, val in pillars.items():
                with st.expander(f"{val['title']} ({val['total']}/{val['max']} pts) [Vol Penalty: -{val['penaltyRatio']*100:.0f}%]"):
                    for b in val["breakdown"]:
                        st.text(f"{b['metric']}: {b['points']:.1f}/{b['maxPoints']} | Data: {b['value']} | Rule: {b['explanation']}")


def page_screener():
    st.title("Prebuilt Intelligence Screener")
    st.write("Using mock batch data for MVP. Connect to FMP batch logic for live run.")
    
    preset = st.selectbox("Select Filter Preset", ["Elite Compounders", "Undervalued Quality", "High Risk Stocks"])
    if st.button("Run Scan"):
         st.write(f"Executing `{preset}` scan via Next.js backend equivalents...")
         df = pd.DataFrame([
             {"Ticker": "AAPL", "Score": 68, "AlphaRank": "Elite Alpha", "FwdPE": 28, "Moat": 18, "Status": "PASS"},
             {"Ticker": "MSFT", "Score": 72, "AlphaRank": "Elite Alpha", "FwdPE": 30, "Moat": 19, "Status": "PASS"},
             {"Ticker": "XYZ", "Score": 25, "AlphaRank": "Underperformer", "FwdPE": 60, "Moat": 4, "Status": "AVOID"}
         ])
         if preset == "Elite Compounders":
             st.dataframe(df[df["Score"] > 60])
         elif preset == "Undervalued Quality":
             st.dataframe(df[(df["Score"] > 50) & (df["FwdPE"] < 30)])
         else:
             st.dataframe(df[df["Status"] == "AVOID"])


def page_portfolio():
    st.title("Portfolio Downside Risk Optimizer")
    
    tickers_input = st.text_input("Enter Tickers (comma separated, evenly weighted for now)", "AAPL, MSFT, GOOGL")
    if st.button("Evaluate Portfolio"):
        t_list = [x.strip() for x in tickers_input.split(",")]
        holdings = [{"ticker": t, "weight": 1.0/len(t_list)} for t in t_list]
        
        with st.spinner("Aggregating historical returns and correlations..."):
            port = evaluate_portfolio(holdings)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Risk Score", f"{port['portfolioRiskScore']:.1f}/100")
            c2.metric("Classification", port["riskClassification"])
            c3.metric("Max Drawdown (1y)", f"{port['maxDrawdown']*100:.1f}%")
            c4.metric("Volatility", f"{port['volatility']*100:.2f}%")
            
            st.write("---")
            if port["signals"]:
                st.warning("Warnings & Concentration Overlap:")
                for s in port["signals"]:
                    st.write(f"- {s}")
                    
            st.subheader("Correlation Matrix (Pearson)")
            df_corr = pd.DataFrame(port["correlationMatrix"])
            st.dataframe(df_corr.style.background_gradient(cmap='coolwarm', axis=None))


def page_macro():
    st.title("Macro Environment Tracker")
    macro = get_macro_state()
    st.metric("Economic Phase", macro["phase"])
    st.metric("System Engine Multiplier", f"{macro['multiplier']}x Override")
    st.write(f"Rate Trend: **{macro['rateTrend']}** | Liquidity Trend: **{macro['liquidityTrend']}**")
    
    if macro["multiplier"] < 1.0:
         st.error("Caution: Defensive transition. Valuations will be actively compressed.")
    else:
         st.success("Constructive: Tailwind cycle. Scores normal or boosted.")

# ----------- NAV -----------------
nav = st.sidebar.radio("V3 Navigation", ["Terminal", "Screener", "Portfolio Optimizer", "Macro Tracker"])

if nav == "Terminal":
    page_terminal()
elif nav == "Screener":
    page_screener()
elif nav == "Portfolio Optimizer":
    page_portfolio()
else:
    page_macro()
