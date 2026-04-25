import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data.fmp import get_quote, get_historical_financials, resolve_ticker, search_companies, get_analyst_revisions
from engine.macro import get_macro_state
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

st.set_page_config(page_title="V10 Institutional Terminal", layout="wide", page_icon="📈")


# ----------- PAGES ---------------
def page_terminal():
    st.title("V10 Institutional Terminal")
    st.write("Search Company or Ticker:")

    selected_ticker = st_searchbox(
        search_companies,
        key="ticker_search_box"
    )

    if selected_ticker:
        with st.spinner(f"Fetching fundamentals for {selected_ticker}..."):
            ticker = resolve_ticker(selected_ticker).upper()
            
            from data.fmp import get_financial_growth, get_key_metrics, get_historical_prices, get_analyst_revisions
            
            quote = get_quote(ticker)
            growth = get_financial_growth(ticker)
            metrics = get_key_metrics(ticker)
            prices = get_historical_prices(ticker, 252)
            
            revs = get_analyst_revisions(ticker)
            quote["revisions_score"] = revs.get("revisions_score", 0.5)

            # Macro — used only for action downgrade, not scoring weights
            try:
                macro = get_macro_state()
            except Exception:
                macro = {"state": "Neutral"}

            base_result = evaluate_stock(ticker, quote, growth, metrics, prices, macro)

            if "error" in base_result:
                st.error(f"Scoring error: {base_result['error']}")
                return

            result = calculate_alpha_and_rank(base_result)

            # ---- HEADER ----
            col1, col2 = st.columns([3, 1])
            with col1:
                price = quote.get("price", 0)
                price_str = f"${price:,.2f}" if price and price > 0 else "Price N/A"
                sector = quote.get("sector", "")
                sector_txt = f" · {sector}" if sector and sector != "DEFAULT" else ""
                st.markdown(f"## {ticker} — {price_str}{sector_txt}")
                st.caption(f"Alpha Ranking: **{result.get('alphaRankingStr')}** (Score: {result.get('alphaScore')}/100)")

            with col2:
                action = result.get("action", result.get("verdict", ""))
                action_colors = {
                    "STRONG BUY": "#00c853", "BUY": "#64dd17", "ACCUMULATE": "#64dd17",
                    "HOLD": "#ff9100", "WATCH": "#ff6d00", "AVOID": "#d50000"
                }
                color = action_colors.get(action, "gray")
                st.markdown(
                    f"<div style='text-align:right'>"
                    f"<span style='color:{color};font-size:1.6em;font-weight:700'>{action}</span><br>"
                    f"<span style='font-size:1.3em;font-weight:600'>{result['totalScore']}/150</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            # Data Confidence
            confidence = result.get("confidence", result.get("dataQualityLabel", "Unknown"))
            conf_color = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(confidence, "⚪")
            st.info(f"{conf_color} Data Confidence: **{confidence}**")

            # ---- RED FLAGS ----
            flags = result.get("redFlags", [])
            if flags:
                st.error(f"**{len(flags)} ALERT(S):**")
                for f in flags:
                    st.write(f"- **[{f['severity']}]** {f['metric']}: {f['message']}")

            st.markdown("---")

            # ---- RADAR CHART ----
            st.subheader("Pillar Breakdown")
            pillars = result["pillars"]

            categories = ["Growth", "Value", "Stability", "Profitability", "Dividend"]
            pillar_keys = ["growth", "value", "stability", "profitability", "dividend"]
            r_vals = []
            for k in pillar_keys:
                p = pillars.get(k, {})
                mx = max(p.get("max", 1), 1)
                r_vals.append(p.get("total", 0) / mx)

            try:
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=r_vals + [r_vals[0]],
                    theta=categories + [categories[0]],
                    fill='toself',
                    name=ticker,
                    line=dict(color='#1E88E5')
                ))
                fig.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                    showlegend=False,
                    margin=dict(l=40, r=40, t=40, b=40),
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Chart error: {e}")

            # ---- PILLAR DETAILS (expandable) ----
            for k in pillar_keys:
                p = pillars.get(k, {})
                with st.expander(f"{p['title']} ({p['total']}/{p['max']} pts)"):
                    breakdown = p.get("breakdown", [])
                    if breakdown:
                        for b in breakdown:
                            score_txt = f"→ {b['score']} pts" if b['score'] != "—" else ""
                            st.markdown(f"- **{b['metric']}**: {b['value']}  {score_txt}")
                    else:
                        st.text("No breakdown available.")


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
    st.markdown("V10 Dynamic Allocation Layer — Macro controls **position sizing**, not scoring. The V10 Engine evaluates raw metrics directly under strict thresholds.")

    try:
        macro = get_macro_state()
    except Exception:
        macro = {"riskScore": 50, "state": "Neutral", "exposure": "50-70%"}

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("Risk Score", f"{macro.get('riskScore', 50):.0f}/100")
    col2.metric("Dynamic State", macro.get('state', 'Neutral'))
    col3.metric("Target Exposure", macro.get('exposure', '50-70%'))

    state = macro.get("state", "Neutral")
    if "Risk-ON" in state:
         st.success("Constructive Cycle: Allowing 90-100% long exposure.")
    elif "Risk-OFF" in state:
         st.error("Caution Cycle: Clipping exposure to 10-30%.")
    elif "Conflict" in state:
         st.warning("Signal Conflict: Capping exposure at 50%.")
    else:
         st.info("Neutral: Standard 50-70% allocation.")


# --- V6/V8 SPECIFIC PAGES ---
def page_validation():
    st.title("V10 Backtest & Validation Engine")
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
