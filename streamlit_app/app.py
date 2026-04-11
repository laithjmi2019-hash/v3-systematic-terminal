import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data.fmp import get_quote, get_historical_financials, resolve_ticker, search_companies
from data.macro import get_macro_state
from engine.scoring import evaluate_stock
from engine.alpha import calculate_alpha_and_rank
from engine.portfolio import evaluate_portfolio
from streamlit_searchbox import st_searchbox

# V4 Imports
from engine.backtest import run_simulation
from engine.factors import calculate_factor_loads
from data.ingester import ingest_historical_data
from engine.paper import get_live_holdings, execute_rebalance
import datetime

st.set_page_config(page_title="V4 Institutional Terminal", layout="wide", page_icon="📈")

# ----------- AI STUB -------------
def get_ai_insight(result: dict) -> dict:
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
    st.write("Search Company or Ticker:")
    
    selected_ticker = st_searchbox(
        search_companies,
        key="ticker_search_box"
    )
    
    if selected_ticker:
        with st.spinner(f"Fetching fundamentals for {selected_ticker}..."):
            ticker = resolve_ticker(selected_ticker).upper()
            quote = get_quote(ticker)
            financials = get_historical_financials(ticker, 10)
            macro = get_macro_state()
            
            if not financials:
                st.error("Engine failure: Could not extract timeline metrics.")
                return
                
            base_result = evaluate_stock(ticker, financials, quote, macro["multiplier"])
            final_result = calculate_alpha_and_rank(base_result)
            ai = get_ai_insight(final_result)
            
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
                
            st.info(f"Data Quality: {final_result.get('dataQualityLabel')} ({final_result.get('dataQualityPct', 0)*100:.0f}% metrics acquired)")

            flags = final_result.get("redFlags", [])
            if flags:
                st.error(f"**{len(flags)} HARD ALERTS DETECTED:**")
                for f in flags:
                    st.write(f"- [{f['severity']}] {f['metric']}: {f['message']}")

            st.markdown("---")
            st.subheader("AI Decision Intelligence")
            ai_c1, ai_c2, ai_c3 = st.columns(3)
            ai_c1.metric("Confidence Level", ai["ConfidenceLevel"])
            ai_c2.metric("System Action", ai["Action"])
            ai_c3.write(ai["Reason"])
            
            st.markdown("---")
            st.subheader("Pillar Breakdown")
            categories = ['Moat', 'Profitability', 'Financial Strength', 'Cash Flow', 'Valuation']
            pillars = final_result["pillars"]
            
            r_vals = [
                pillars["moat"]["total"] / max(pillars["moat"]["max"], 1),
                pillars["profitability"]["total"] / max(pillars["profitability"]["max"], 1),
                pillars["financialStrength"]["total"] / max(pillars["financialStrength"]["max"], 1),
                pillars["cashFlowQuality"]["total"] / max(pillars["cashFlowQuality"]["max"], 1),
                pillars["valuation"]["total"] / max(pillars["valuation"]["max"], 1)
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


def page_screener():
    st.title("Prebuilt Intelligence Screener")
    st.write("Using mock batch data for MVP. Connect to FMP batch logic for live run.")
    preset = st.selectbox("Select Filter Preset", ["Elite Compounders", "Undervalued Quality", "High Risk Stocks"])
    if st.button("Run Scan"):
         st.write(f"Executing `{preset}` scan via Python backend equivalents...")
         df = pd.DataFrame([
             {"Ticker": "AAPL", "Score": 68, "AlphaRank": "Elite Alpha", "FwdPE": 28, "Moat": 18, "Status": "PASS"},
             {"Ticker": "MSFT", "Score": 72, "AlphaRank": "Elite Alpha", "FwdPE": 30, "Moat": 19, "Status": "PASS"}
         ])
         st.dataframe(df)

def page_portfolio():
    st.title("Portfolio Downside Risk Optimizer")
    tickers_input = st.text_input("Enter Tickers", "AAPL, MSFT, GOOGL")
    if st.button("Evaluate Portfolio"):
        t_list = [x.strip() for x in tickers_input.split(",")]
        holdings = [{"ticker": t, "weight": 1.0/len(t_list)} for t in t_list]
        with st.spinner("Aggregating historical returns and correlations..."):
            port = evaluate_portfolio(holdings)
            c1, c2 = st.columns(2)
            c1.metric("Risk Score", f"{port['portfolioRiskScore']:.1f}/100")
            c2.metric("Max Drawdown (1y)", f"{port['maxDrawdown']*100:.1f}%")
            if port["signals"]:
                st.warning("Warnings: " + " | ".join(port["signals"]))
            st.dataframe(pd.DataFrame(port["correlationMatrix"]).style.background_gradient(cmap='coolwarm', axis=None))


def page_macro():
    st.title("Macro Environment Tracker")
    macro = get_macro_state()
    st.metric("Economic Phase", macro["phase"])
    st.metric("System Engine Multiplier", f"{macro['multiplier']}x Override")

# --- V4 SPECIFIC PAGES ---
def page_validation():
    st.title("Strategy Validation Engine")
    st.warning("**SURVIVORSHIP BIAS DISCLOSURE:** This backtest operates dynamically on currently surviving S&P subset equities and may overestimate historical returns due to the absence of delisted entities.")
    
    if st.button("Full Bootstrap & Ingest (Run Once)"):
        with st.spinner("Bootstrapping localized data lake (S&P subset)..."):
            done = ingest_historical_data()
            if done: st.success("Local SQLite Cache Populated")
            else: st.info("Database already cached.")
            
    if st.button("Execute Validated Backtest"):
        with st.spinner("Processing point-in-time scores over 15 years..."):
            res = run_simulation(2010)
            if "error" in res:
                st.error(res["error"])
                return
                
            stats = res["stats"]
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Strategy CAGR", f"{stats['CAGR']*100:.2f}%")
            col2.metric("Benchmark (SPY) CAGR", f"{stats['SPY_CAGR']*100:.2f}%")
            col3.metric("Strategy Max DD", f"{stats['MDD']*100:.2f}%")
            col4.metric("Benchmark Max DD", f"{stats['SPY_MDD']*100:.2f}%")
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=res['dates'], y=res['portfolio'], name='Alpha Strategy'))
            fig.add_trace(go.Scatter(x=res['dates'], y=res['benchmark'], name='SPY Benchmark'))
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Factor Exposure (OLS Beta)")
            factor = calculate_factor_loads(res['returns_streams'][0], res['returns_streams'][1])
            st.json(factor)
            
            st.subheader("Crisis Regime Stress Testing")
            for r_name, r_data in res["regimes"].items():
                if r_data:
                    passed = r_data["PortMDD"] <= r_data["SpyMDD"]
                    st.write(f"**{r_name}**: {'✅ BEAT SPY' if passed else '❌ LAGGED SPY'}")
                    st.write(f"↪ Port Drawdown: {r_data['PortMDD']*100:.1f}% vs SPY Drawdown: {r_data['SpyMDD']*100:.1f}%")

def page_paper():
    st.title("Live Paper Portfolio Tracker")
    st.info("The production layer connecting offline backtests to out-of-sample forward verification.")
    
    holdings = get_live_holdings()
    if holdings:
        st.dataframe(pd.DataFrame(holdings))
    else:
        st.write("No active positions currently simulated.")
        
    st.markdown("---")
    if st.button("Trigger Structural Rebalance (EOD Execution)"):
        with st.spinner("Evaluating engine rules..."):
            # Dummy representation of top engine pull
            execute_rebalance([
                {"ticker": "MSFT", "date": str(datetime.date.today()), "weight": 0.5, "entry_price": 400},
                {"ticker": "NVDA", "date": str(datetime.date.today()), "weight": 0.5, "entry_price": 800}
            ])
            st.success("Forward PnL markers updated in database.")

# ----------- NAV -----------------
nav = st.sidebar.radio("Navigation", [
    "Terminal", 
    "Portfolio Risk", 
    "Prebuilt Screener", 
    "Macro Tracker",
    "Backtest Validator",
    "Paper Portfolio"
])

if nav == "Terminal": page_terminal()
elif nav == "Portfolio Risk": page_portfolio()
elif nav == "Prebuilt Screener": page_screener()
elif nav == "Macro Tracker": page_macro()
elif nav == "Backtest Validator": page_validation()
elif nav == "Paper Portfolio": page_paper()
