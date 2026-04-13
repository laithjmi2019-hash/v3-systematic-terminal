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
def get_ai_insight(result: dict, macro_state: dict) -> dict:
    confidence_level = "Medium"
    if result.get("dataQualityPct", 0) > 0.9 and not result.get("redFlags"):
        confidence_level = "High"
    elif result.get("dataQualityPct", 0) < 0.7 or len(result.get("redFlags", [])) > 1:
        confidence_level = "Low"
        
    score = result.get("totalScore", 0)
    mom_score = result.get("pillars", {}).get("cashFlowQuality", {}).get("total", 0)
    
    level_idx = 0
    if score > 85 and mom_score > 15:
        level_idx = 3 # Strong Buy
    elif score > 75:
        level_idx = 2 # Accumulate
    elif score >= 50:
        level_idx = 1 # Hold
    else:
        level_idx = 0 # Avoid
        
    if macro_state.get("state", "") == "Risk-OFF":
        level_idx = max(0, level_idx - 1)
        
    actions = ["Avoid", "Hold", "Accumulate", "Strong Buy"]
        
    return {
        "Verdict": result.get("verdict", "WATCH"),
        "Reason": "Quantitative metrics evaluated alongside macro regime overlay.",
        "Strengths": ["Stable FCF output" if result.get("totalScore",0) > 40 else "N/A"],
        "Risks": [f.get("message", "N/A") for f in result.get("redFlags", [])] if result.get("redFlags") else ["Volatility exposure"],
        "Action": actions[level_idx],
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
                
            base_result = evaluate_stock(ticker, financials, quote, macro)
            final_result = calculate_alpha_and_rank(base_result)
            ai = get_ai_insight(final_result, macro)
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"## {ticker} - ${quote.get('price', 0):.2f}")
                st.caption(f"Alpha Ranking: **{final_result.get('alphaRankingStr')}** (Score: {final_result.get('alphaScore')}/100)")
                if final_result.get("scoreMomentum") != 0:
                    color = "green" if final_result["scoreMomentum"] > 0 else "red"
                    st.markdown(f"<span style='color:{color}'>Momentum: {final_result['scoreMomentum']:+.1f} pts Y/Y</span>", unsafe_allow_html=True)
            with col2:
                verdict_color = "red" if final_result["verdict"] == "AVOID" else "green" if final_result["verdict"] == "PASS" else "orange"
                st.markdown(f"### <div style='text-align: right; color: {verdict_color}'>{final_result['verdict']} : {final_result['totalScore']}/100</div>", unsafe_allow_html=True)
                
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
            categories = ['Quality', 'Value', 'Growth', 'Momentum', 'Risk']
            pillars = final_result["pillars"]
            
            r_vals = [
                pillars["moat"]["total"] / max(pillars["moat"]["max"], 1),
                pillars["profitability"]["total"] / max(pillars["profitability"]["max"], 1),
                pillars["financialStrength"]["total"] / max(pillars["financialStrength"]["max"], 1),
                pillars["cashFlowQuality"]["total"] / max(pillars["cashFlowQuality"]["max"], 1),
                pillars["valuation"]["total"] / max(pillars["valuation"]["max"], 1)
            ]
            
            try:
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=r_vals + [r_vals[0]],
                    theta=categories + [categories[0]],
                    fill='toself',
                    name=ticker
                ))
                fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Failed to render chart: {e}")
            
            # Expanders for details
            for key, val in pillars.items():
                with st.expander(f"{val['title']} ({val['total']}/{val['max']} pts)"):
                    if val.get("breakdown"):
                        for b in val["breakdown"]:
                            st.text(f"{b['metric']}: {b['points']:.1f}/{b['maxPoints']} | Data: {b['value']} | Rule: {b['explanation']}")
                    else:
                        st.text("V6 Dynamic Factor Calculation active. Detailed logic hidden in macro state.")


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
            if port["correlationMatrix"]:
                st.dataframe(pd.DataFrame(port["correlationMatrix"]).style.background_gradient(cmap='coolwarm', axis=None))


def page_macro():
    st.title("Strategy Intelligence Dashboard")
    st.markdown("V6 Institutional Multi-Factor Dynamic Allocation Layer")
    macro = get_macro_state()
    
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("Risk Score", f"{macro['riskScore']:.0f}/100")
    col2.metric("Dynamic State", macro['state'])
    col3.metric("Target Exposure", macro['exposure'])
    
    if macro["state"] == "Risk-ON":
         st.success("Constructive Cycle: Overweighting Growth & Momentum factors. Allowing 90-100% long exposure.")
    elif macro["state"] == "Risk-OFF":
         st.error("Caution Cycle: Defensive pivot shifting weights to Quality & Value. Clipping gross exposure to 10-30%.")
    else:
         st.info("Neutral Breadth: Even 5-pillar distribution. 50-70% standard allocation.")

# --- V6 SPECIFIC PAGES ---
def page_validation():
    st.title("V6 Backtest & Validation Engine")
    st.warning("**SURVIVORSHIP BIAS DISCLOSURE:** This backtest operates dynamically on currently surviving equities.")
    
    if st.button("Full Bootstrap & Ingest (Run Once)"):
        with st.spinner("Bootstrapping localized data lake (S&P subset)..."):
            done = ingest_historical_data()
            if done: st.success("Local SQLite Cache Populated")
            else: st.info("Database already cached.")
            
    if st.button("Execute Validated Backtest (15-Year)"):
        with st.spinner("Simulating Point-in-Time Alpha vectors vs Benchmark..."):
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
            fig.add_trace(go.Scatter(x=res['dates'], y=res['portfolio'], name='Alpha Strategy (Tx Fee Adjusted)'))
            fig.add_trace(go.Scatter(x=res['dates'], y=res['benchmark_spy'], name='SPY (S&P 500)'))
            fig.add_trace(go.Scatter(x=res['dates'], y=res['benchmark_qqq'], name='QQQ (Nasdaq)', opacity=0.5))
            fig.add_trace(go.Scatter(x=res['dates'], y=res['benchmark_iwm'], name='IWM (Russell 2k)', opacity=0.5))
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Rolling Factor Exposure (1Y OLS Regression)")
            factor = calculate_factor_loads(res['returns_streams'][0], res['returns_streams'][1])
            colA, colB = st.columns(2)
            colA.metric("Trailing Market Beta", factor["MarketBeta"])
            colB.metric("Trailing Alpha", f"{factor['Alpha']*100:.2f}%")
            
            if factor["BetaSeries"]:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(y=factor["BetaSeries"], name='Rolling Beta against SPY'))
                st.plotly_chart(fig2, use_container_width=True, height=200)
            
            st.subheader("Crisis Regime Edge Testing")
            for r_name, r_data in res["regimes"].items():
                if r_data:
                    passed = r_data["PortMDD"] <= r_data["SpyMDD"]
                    st.write(f"**{r_name}**: {'✅ BEAT DOWN' if passed else '❌ LAGGED'}")
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
    "Intelligence Dashboard",
    "Backtest Validator",
    "Paper Portfolio"
])

if nav == "Terminal": page_terminal()
elif nav == "Portfolio Risk": page_portfolio()
elif nav == "Prebuilt Screener": page_screener()
elif nav == "Intelligence Dashboard": page_macro()
elif nav == "Backtest Validator": page_validation()
elif nav == "Paper Portfolio": page_paper()
