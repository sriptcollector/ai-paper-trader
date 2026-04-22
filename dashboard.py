"""AI Paper Trader Dashboard — streamlit run dashboard.py"""

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent / "paper_trader.db"
INITIAL_CASH = 100_000.0

# ── Strategy metadata (descriptions for the strategy pages) ──
STRATEGY_INFO = {
    "RSI_BBands": {
        "full_name": "RSI + Bollinger Bands",
        "short": "Buys when RSI says oversold AND price hits the lower Bollinger Band. Sells when either indicator says overbought.",
        "how": "Combines two signals — RSI below 30 (oversold) with price below the lower band. This double-confirmation filters out false signals that either indicator alone would give.",
        "best_for": "Ranging / sideways markets where prices bounce between support and resistance.",
        "risk": "Can miss big breakouts. In a strong downtrend, price can stay oversold for a long time.",
    },
    "BBands": {
        "full_name": "Bollinger Bands",
        "short": "Buys when price drops below the lower band (oversold). Sells when price rises above the upper band (overbought).",
        "how": "Bollinger Bands draw two lines around a moving average at 2 standard deviations. When price touches the bottom, it's statistically likely to bounce back. When it touches the top, it's likely to pull back.",
        "best_for": "Mean-reversion plays in stocks that trade in a range.",
        "risk": "Gets crushed in strong trends — a stock breaking out will keep hitting the upper band.",
    },
    "Momentum": {
        "full_name": "Momentum",
        "short": "Buys when price momentum turns positive. Sells when price drops below the 50-day moving average.",
        "how": "Measures the rate of price change over 14 days. Positive momentum means the stock is accelerating upward. The 50-day SMA acts as a safety net — if price falls below it, the trend is broken.",
        "best_for": "Trending markets and stocks with clear directional moves.",
        "risk": "Whipsaws in choppy markets. Momentum can reverse suddenly.",
    },
    "CrossSMA": {
        "full_name": "SMA Crossover",
        "short": "Buys when the fast moving average crosses above the slow one (golden cross). Sells on the opposite (death cross).",
        "how": "Uses a 5-day fast SMA and 37-day slow SMA. When the short-term trend overtakes the long-term trend, it signals a new uptrend is forming. Classic trend-following logic.",
        "best_for": "Catching medium to long-term trend changes.",
        "risk": "Lags behind fast moves. By the time the cross happens, you've missed the initial move.",
    },
    "MACD": {
        "full_name": "MACD",
        "short": "Buys on bullish MACD crossover when both lines are above zero. Sells on bearish crossover.",
        "how": "MACD is the difference between a 12-day and 26-day EMA. When this difference crosses above its own signal line AND both are positive, it confirms strong upward momentum.",
        "best_for": "Confirming trend direction with momentum. Works well on daily charts.",
        "risk": "Slow to react. Can give late signals in fast markets. Relies on TA-Lib indicators.",
    },
    "TripleRSI": {
        "full_name": "Triple RSI",
        "short": "Uses three RSI timeframes (20, 60, 120 days) that must all agree before entering. Exits after a minimum holding period.",
        "how": "Requires alignment across short, medium, and long-term RSI — all three must signal the same direction. This triple confirmation dramatically reduces false signals but trades less frequently.",
        "best_for": "Patient, high-conviction entries. Works well for swing trading.",
        "risk": "Very few signals. The 60-day minimum hold means you ride through pullbacks.",
    },
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE CONFIG + CSS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(page_title="Paper Trader", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
*{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif!important}
.stApp{background:#000}
#MainMenu,footer,header{visibility:hidden}
.stDeployButton{display:none}

/* sidebar */
section[data-testid="stSidebar"]{background:#000;border-right:1px solid #1a1a1a}

/* metrics */
div[data-testid="stMetric"]{background:#0a0a0a;border:1px solid #1a1a1a;border-radius:14px;padding:18px 22px}
div[data-testid="stMetric"] label{color:#666!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:.8px}
div[data-testid="stMetric"] div[data-testid="stMetricValue"]{font-size:26px!important;font-weight:600!important;color:#fff!important}

/* typography */
h1{font-size:28px!important;font-weight:700!important;color:#fff!important;letter-spacing:-.5px!important}
h2{font-size:20px!important;font-weight:600!important;color:#fff!important}
h3{font-size:15px!important;font-weight:600!important;color:#888!important;text-transform:uppercase;letter-spacing:.5px!important}

/* tabs */
.stTabs [data-baseweb="tab-list"]{gap:0;border-bottom:1px solid #1a1a1a;background:transparent}
.stTabs [data-baseweb="tab"]{background:transparent;color:#555;font-weight:500;font-size:14px;padding:10px 20px;border:none}
.stTabs [aria-selected="true"]{color:#fff!important;border-bottom:2px solid #fff}

/* dataframes */
.stDataFrame [data-testid="stDataFrameResizable"]{border:1px solid #1a1a1a;border-radius:10px}

hr{border-color:#111!important;margin:28px 0!important}
.stAlert{background:#0a0a0a!important;border:1px solid #1a1a1a!important;border-radius:10px!important;color:#666!important}
</style>""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA LOADING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if not DB_PATH.exists():
    try:
        from init_cloud import seed_sample_data
        seed_sample_data()
        st.rerun()
    except Exception:
        st.markdown("## No data yet")
        st.caption("Run `python run_trader.py trade` to start.")
        st.stop()


@st.cache_data(ttl=30)
def load_data():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    d = {}
    d["cash"] = (conn.execute("SELECT cash FROM portfolio WHERE id=1").fetchone() or {"cash": INITIAL_CASH})["cash"]
    d["positions"] = pd.read_sql("SELECT * FROM positions ORDER BY symbol", conn)
    d["trades"] = pd.read_sql("SELECT * FROM trades ORDER BY executed_at DESC LIMIT 500", conn)
    d["snapshots"] = pd.read_sql("SELECT * FROM portfolio_snapshots ORDER BY date", conn)
    d["strategies"] = pd.read_sql("SELECT * FROM strategy_performance WHERE date=(SELECT MAX(date) FROM strategy_performance) ORDER BY backtest_return_pct DESC NULLS LAST", conn)
    d["signals"] = pd.read_sql("SELECT * FROM signals WHERE date=(SELECT MAX(date) FROM signals) ORDER BY symbol, strategy", conn)
    d["logs"] = pd.read_sql("SELECT * FROM system_log ORDER BY created_at DESC LIMIT 50", conn)
    conn.close()
    if not d["trades"].empty:
        d["trades"]["executed_at"] = pd.to_datetime(d["trades"]["executed_at"])
    if not d["snapshots"].empty:
        d["snapshots"]["date"] = pd.to_datetime(d["snapshots"]["date"])
    return d


D = load_data()

# Computed values
cash = D["cash"]
positions = D["positions"]
snapshots = D["snapshots"]
trades = D["trades"]
strategies = D["strategies"]
signals = D["signals"]

pos_value = snapshots.iloc[-1]["positions_value"] if not snapshots.empty else (positions["shares"] * positions["avg_cost"]).sum() if not positions.empty else 0
total_value = cash + pos_value
total_return = ((total_value / INITIAL_CASH) - 1) * 100
daily_ret = snapshots.iloc[-1]["daily_return_pct"] if not snapshots.empty else 0

# Leverage metrics
margin_used = max(0, -cash)  # Negative cash = borrowed
leverage_ratio = pos_value / total_value if total_value > 0 else 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CHART HELPER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
G = "#34c759"
R = "#ff453a"

def clayout(h=400, xa=None, ya=None, **kw):
    base = dict(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#666", size=12),
        margin=dict(l=0, r=0, t=36, b=0), showlegend=False,
        hoverlabel=dict(bgcolor="#111", font_color="#fff", bordercolor="rgba(0,0,0,0)"),
        height=h,
    )
    ax_def = dict(gridcolor="#111", zerolinecolor="#1a1a1a")
    base["xaxis"] = {**ax_def, **(xa or {})}
    base["yaxis"] = {**ax_def, **(ya or {})}
    base.update(kw)
    return base


def show_chart(fig):
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SIDEBAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    st.markdown(f"""
    <div style="padding:16px 0 20px">
        <div style="font-size:20px;font-weight:700;color:#fff">Paper Trader</div>
        <div style="font-size:11px;color:#444;margin-top:2px">AI Strategy Ensemble</div>
    </div>""", unsafe_allow_html=True)

    # Mode tabs
    mode = st.radio("Mode", ["Paper", "Live"], horizontal=True, label_visibility="collapsed")
    if mode == "Live":
        st.info("Live trading not connected yet. Showing paper trading data.")

    st.markdown("---")

    # Build nav options: base pages + individual strategies
    nav_options = ["Dashboard", "Leaderboard", "Positions", "Trades", "Signals"]
    if not strategies.empty:
        nav_options.append("---")  # visual separator
        for _, row in strategies.iterrows():
            nav_options.append(f"  {row['strategy']}")

    page = st.radio("Pages", [o for o in nav_options if o != "---"], label_visibility="collapsed")

    st.markdown("---")

    # Portfolio summary in sidebar
    ret_color = G if total_return >= 0 else R
    st.markdown(f"""
    <div style="background:#0a0a0a;border:1px solid #1a1a1a;border-radius:12px;padding:16px">
        <div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1px;font-weight:600">Portfolio</div>
        <div style="font-size:22px;font-weight:700;color:#fff;margin:4px 0">${total_value:,.0f}</div>
        <div style="font-size:13px;font-weight:600;color:{ret_color}">{total_return:+.2f}%</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("")
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption(date.today().strftime("%B %d, %Y"))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DASHBOARD PAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if page == "Dashboard":
    # Aggressive mode banner
    if leverage_ratio > 1.0:
        st.markdown(f"""
        <div style="background:linear-gradient(90deg,rgba(255,69,58,0.15),rgba(255,149,0,0.15));
                    border:1px solid rgba(255,149,0,0.3);border-radius:10px;
                    padding:8px 16px;margin-bottom:16px;display:flex;justify-content:space-between">
            <span style="color:#ff9500;font-weight:600;font-size:13px">⚡ AGGRESSIVE MODE — 3x Leverage Enabled</span>
            <span style="color:#ff9500;font-size:12px">Leverage: {leverage_ratio:.2f}x &middot; Margin Used: ${margin_used:,.0f}</span>
        </div>""", unsafe_allow_html=True)

    st.markdown("# Dashboard")

    # Top metrics - 6 columns including leverage
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Value", f"${total_value:,.2f}", f"{total_return:+.2f}%")
    c2.metric("Equity", f"${total_value:,.0f}")
    c3.metric("Exposure", f"${pos_value:,.0f}", f"{leverage_ratio:.2f}x" if leverage_ratio > 0 else None)
    c4.metric("Margin", f"${margin_used:,.0f}" if margin_used > 0 else "$0")
    c5.metric("Positions", str(len(positions)))
    c6.metric("Today", f"{daily_ret:+.2f}%" if daily_ret else "---")

    st.markdown("")

    # Equity curve
    if not snapshots.empty:
        tab1, tab2 = st.tabs(["Equity Curve", "Daily Returns"])
        with tab1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=snapshots["date"], y=snapshots["total_value"],
                mode="lines", line=dict(color="#fff", width=2),
                fill="tonexty", fillcolor="rgba(255,255,255,0.02)",
                hovertemplate="$%{y:,.0f}<extra></extra>",
            ))
            fig.add_hline(y=INITIAL_CASH, line_dash="dot", line_color="#222",
                          annotation_text=f"Start ${INITIAL_CASH:,.0f}",
                          annotation_font=dict(color="#444", size=11))
            fig.update_layout(**clayout(h=400, ya=dict(tickprefix="$", tickformat=",.0f")))
            show_chart(fig)

        with tab2:
            colors = [G if x >= 0 else R for x in snapshots["daily_return_pct"]]
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=snapshots["date"], y=snapshots["daily_return_pct"],
                marker_color=colors, marker_line_width=0,
                hovertemplate="%{y:+.2f}%<extra></extra>",
            ))
            fig2.update_layout(**clayout(h=350, ya=dict(ticksuffix="%")))
            show_chart(fig2)
    else:
        st.info("No snapshots yet. Run a trading cycle to see your equity curve.")

    # Risk metrics
    if not snapshots.empty and len(snapshots) > 2:
        st.markdown("")
        st.markdown("### Risk Metrics")
        rets = snapshots["daily_return_pct"].dropna()
        r1, r2, r3, r4 = st.columns(4)

        if len(rets) > 0:
            cum = (1 + rets / 100).cumprod()
            dd = ((cum - cum.cummax()) / cum.cummax() * 100).min()
            r1.metric("Max Drawdown", f"{dd:.2f}%")
        else:
            r1.metric("Max Drawdown", "---")

        if len(rets) > 1 and rets.std() > 0:
            r2.metric("Sharpe Ratio", f"{(rets.mean() / rets.std()) * 252**0.5:.2f}")
        else:
            r2.metric("Sharpe Ratio", "---")

        r3.metric("Avg Daily", f"{rets.mean():+.3f}%" if len(rets) > 0 else "---")
        r4.metric("Volatility", f"{rets.std() * 252**0.5:.1f}%" if len(rets) > 1 else "---")

    # Quick positions overview
    if not positions.empty:
        st.markdown("")
        st.markdown("### Open Positions")

        price_map = {}
        if not snapshots.empty:
            try:
                sd = json.loads(snapshots.iloc[-1]["snapshot_data"])
                price_map = {s: info["current_price"] for s, info in sd.get("positions", {}).items()}
            except Exception:
                pass

        rows = []
        for _, p in positions.iterrows():
            cp = price_map.get(p["symbol"], p["avg_cost"])
            pnl = ((cp - p["avg_cost"]) / p["avg_cost"]) * 100
            rows.append({
                "Symbol": p["symbol"],
                "Shares": int(p["shares"]),
                "Avg Cost": f"${p['avg_cost']:.2f}",
                "Current": f"${cp:.2f}",
                "P&L %": f"{pnl:+.1f}%",
                "Value": f"${p['shares'] * cp:,.0f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEADERBOARD PAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "Leaderboard":
    st.markdown("# Strategy Leaderboard")
    st.caption("Ranked by 90-day backtest return. Updated weekly by the optimizer.")

    if strategies.empty:
        st.info("Run `python run_trader.py optimize` to generate strategy rankings.")
    else:
        strats = strategies.sort_values("backtest_return_pct", ascending=False, na_position="last").reset_index(drop=True)

        # Bar chart
        fig = go.Figure()
        colors = [G if (r or 0) >= 0 else R for r in strats["backtest_return_pct"]]
        fig.add_trace(go.Bar(
            x=strats["strategy"], y=strats["backtest_return_pct"].fillna(0),
            marker_color=colors, marker_line_width=0,
            text=[f"{(r or 0):+.1f}%" for r in strats["backtest_return_pct"]],
            textposition="outside", textfont=dict(size=13, color="#999"),
            hovertemplate="%{x}: %{y:+.2f}%<extra></extra>",
        ))
        fig.update_layout(**clayout(h=260, ya=dict(ticksuffix="%", title=None), xa=dict(title=None), bargap=0.35))
        show_chart(fig)

        st.markdown("")

        # Leaderboard cards
        for i, row in strats.iterrows():
            ret = row["backtest_return_pct"] or 0
            sharpe = row["backtest_sharpe"] or 0
            dd = row["backtest_max_drawdown"] or 0
            wr = row["backtest_win_rate"] or 0
            w = row["weight"] or 1
            name = row["strategy"]
            desc = row["description"] or ""
            info = STRATEGY_INFO.get(name, {})
            short = info.get("short", desc)

            rc = G if ret > 0 else (R if ret < 0 else "#555")
            badge_bg = "rgba(52,199,89,0.12)" if i == 0 else "#111"
            badge_fg = G if i == 0 else "#555"

            st.markdown(f"""
            <div style="background:#0a0a0a;border:1px solid #1a1a1a;border-radius:14px;padding:24px;margin-bottom:12px">
                <div style="display:flex;justify-content:space-between;align-items:flex-start">
                    <div>
                        <span style="background:{badge_bg};color:{badge_fg};font-size:11px;font-weight:700;padding:3px 10px;border-radius:6px">#{i+1}</span>
                        <span style="font-size:18px;font-weight:600;color:#fff;margin-left:10px">{name}</span>
                        <div style="font-size:13px;color:#555;margin-top:6px;max-width:600px">{short}</div>
                    </div>
                    <div style="text-align:right">
                        <div style="font-size:32px;font-weight:700;color:{rc};letter-spacing:-1px">{ret:+.1f}%</div>
                        <div style="font-size:11px;color:#444;margin-top:2px">90-day return</div>
                    </div>
                </div>
                <div style="display:flex;gap:32px;margin-top:18px;padding-top:14px;border-top:1px solid #1a1a1a">
                    <div><div style="font-size:10px;color:#444;text-transform:uppercase;letter-spacing:.8px;font-weight:600">Sharpe</div><div style="font-size:15px;font-weight:600;color:#ccc;margin-top:2px">{sharpe:.2f}</div></div>
                    <div><div style="font-size:10px;color:#444;text-transform:uppercase;letter-spacing:.8px;font-weight:600">Win Rate</div><div style="font-size:15px;font-weight:600;color:#ccc;margin-top:2px">{wr:.0f}%</div></div>
                    <div><div style="font-size:10px;color:#444;text-transform:uppercase;letter-spacing:.8px;font-weight:600">Max DD</div><div style="font-size:15px;font-weight:600;color:#ccc;margin-top:2px">{dd:.1f}%</div></div>
                    <div><div style="font-size:10px;color:#444;text-transform:uppercase;letter-spacing:.8px;font-weight:600">Weight</div><div style="font-size:15px;font-weight:600;color:#ccc;margin-top:2px">{w:.2f}x</div></div>
                    <div><div style="font-size:10px;color:#444;text-transform:uppercase;letter-spacing:.8px;font-weight:600">Live P&L</div><div style="font-size:15px;font-weight:600;color:{G if (row['total_pnl'] or 0)>=0 else R};margin-top:2px">${(row['total_pnl'] or 0):+,.0f}</div></div>
                </div>
            </div>""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POSITIONS PAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "Positions":
    st.markdown("# Positions")

    if positions.empty:
        st.info("No open positions.")
    else:
        price_map = {}
        if not snapshots.empty:
            try:
                sd = json.loads(snapshots.iloc[-1]["snapshot_data"])
                price_map = {s: info["current_price"] for s, info in sd.get("positions", {}).items()}
            except Exception:
                pass

        total_inv = 0
        total_cur = 0

        for _, p in positions.iterrows():
            cp = price_map.get(p["symbol"], p["avg_cost"])
            inv = p["shares"] * p["avg_cost"]
            cur = p["shares"] * cp
            pnl = ((cp - p["avg_cost"]) / p["avg_cost"]) * 100
            pnl_d = cur - inv
            total_inv += inv
            total_cur += cur
            pc = G if pnl >= 0 else R

            st.markdown(f"""
            <div style="background:#0a0a0a;border:1px solid #1a1a1a;border-radius:12px;padding:16px 20px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
                <div>
                    <div style="font-size:17px;font-weight:600;color:#fff">{p['symbol']}</div>
                    <div style="font-size:12px;color:#555">{int(p['shares'])} shares &middot; avg ${p['avg_cost']:.2f} &middot; ${inv:,.0f} invested</div>
                </div>
                <div style="text-align:right">
                    <div style="font-size:20px;font-weight:700;color:{pc}">{pnl:+.1f}%</div>
                    <div style="font-size:12px;color:{pc}">${pnl_d:+,.0f}</div>
                </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("")
        c1, c2, c3 = st.columns(3)
        c1.metric("Invested", f"${total_inv:,.0f}")
        c2.metric("Current", f"${total_cur:,.0f}")
        ov = ((total_cur / total_inv) - 1) * 100 if total_inv > 0 else 0
        c3.metric("Unrealized", f"{ov:+.2f}%")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TRADES PAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "Trades":
    st.markdown("# Trade History")

    if trades.empty:
        st.info("No trades yet.")
    else:
        c1, c2 = st.columns(2)
        side_f = c1.selectbox("Filter by side", ["All", "BUY", "SELL"])
        sym_f = c2.selectbox("Filter by symbol", ["All"] + sorted(trades["symbol"].unique().tolist()))

        f = trades.copy()
        if side_f != "All":
            f = f[f["side"] == side_f]
        if sym_f != "All":
            f = f[f["symbol"] == sym_f]

        disp = f[["executed_at", "side", "symbol", "shares", "price", "pnl", "pnl_pct", "reason"]].copy()
        disp.columns = ["Date", "Side", "Symbol", "Shares", "Price", "P&L $", "P&L %", "Reason"]
        disp["Date"] = disp["Date"].dt.strftime("%Y-%m-%d %H:%M")
        disp["Price"] = disp["Price"].map(lambda x: f"${x:,.2f}")
        disp["Shares"] = disp["Shares"].map(lambda x: f"{x:.0f}")
        disp["P&L $"] = disp["P&L $"].map(lambda x: f"${x:+,.2f}" if pd.notna(x) else "")
        disp["P&L %"] = disp["P&L %"].map(lambda x: f"{x:+.1f}%" if pd.notna(x) else "")
        st.dataframe(disp, use_container_width=True, hide_index=True, height=450)

        # Stats from closed trades
        sells = trades[trades["side"] == "SELL"].dropna(subset=["pnl"])
        if not sells.empty:
            st.markdown("")
            st.markdown("### Closed Trade Stats")
            s1, s2, s3, s4 = st.columns(4)
            w = len(sells[sells["pnl"] > 0])
            l = len(sells[sells["pnl"] <= 0])
            t = w + l
            s1.metric("Closed Trades", str(t))
            s2.metric("Win Rate", f"{w/t*100:.0f}%" if t > 0 else "---")
            s3.metric("Total P&L", f"${sells['pnl'].sum():+,.2f}")
            s4.metric("Avg P&L", f"${sells['pnl'].mean():+,.2f}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SIGNALS PAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "Signals":
    st.markdown("# Latest Signals")
    st.caption("Each cell shows what a strategy recommends for that stock right now.")

    if signals.empty:
        st.info("No signals yet.")
    else:
        smap = {"BUY": 1, "HOLD": 0, "SELL": -1}
        signals["v"] = signals["signal"].map(smap)
        piv = signals.pivot_table(index="symbol", columns="strategy", values="v", aggfunc="first").fillna(0)

        txt = [[{1: "BUY", 0: "", -1: "SELL"}.get(int(v), "") for v in row] for row in piv.values]

        fig = go.Figure(data=go.Heatmap(
            z=piv.values, x=piv.columns.tolist(), y=piv.index.tolist(),
            colorscale=[[0, R], [0.5, "#0a0a0a"], [1, G]],
            zmin=-1, zmax=1, text=txt, texttemplate="%{text}",
            textfont=dict(size=10, color="#999"), showscale=False, xgap=2, ygap=2,
        ))
        fig.update_layout(**clayout(h=max(400, len(piv) * 26 + 80), xa=dict(side="top")))
        show_chart(fig)

        # Consensus list
        st.markdown("")
        st.markdown("### Consensus Summary")
        for sym in piv.index:
            rv = piv.loc[sym]
            b = int((rv == 1).sum())
            s = int((rv == -1).sum())
            n = len(rv)
            if b > s and b / n >= 0.4:
                tag = f'<span style="color:{G};font-weight:600">BUY ({b}/{n})</span>'
            elif s > b and s / n >= 0.3:
                tag = f'<span style="color:{R};font-weight:600">SELL ({s}/{n})</span>'
            else:
                tag = '<span style="color:#444">HOLD</span>'
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #111"><span style="font-weight:500;color:#ccc">{sym}</span>{tag}</div>', unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INDIVIDUAL STRATEGY PAGES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page.startswith("  "):
    strat_name = page.strip()

    # Get strategy data
    strat_row = strategies[strategies["strategy"] == strat_name]
    info = STRATEGY_INFO.get(strat_name, {})

    st.markdown(f"# {info.get('full_name', strat_name)}")

    if strat_row.empty:
        st.info(f"No performance data for {strat_name}.")
    else:
        sr = strat_row.iloc[0]
        ret = sr["backtest_return_pct"] or 0
        sharpe = sr["backtest_sharpe"] or 0
        dd = sr["backtest_max_drawdown"] or 0
        wr = sr["backtest_win_rate"] or 0
        w = sr["weight"] or 1
        live_pnl = sr["total_pnl"] or 0
        live_trades = sr["total_trades"] or 0

        rc = G if ret > 0 else (R if ret < 0 else "#555")

        # Hero return
        st.markdown(f"""
        <div style="text-align:center;padding:30px 0 20px">
            <div style="font-size:56px;font-weight:700;color:{rc};letter-spacing:-2px">{ret:+.1f}%</div>
            <div style="font-size:13px;color:#555;margin-top:4px">90-day backtest return</div>
        </div>""", unsafe_allow_html=True)

        # Key stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sharpe Ratio", f"{sharpe:.2f}")
        c2.metric("Win Rate", f"{wr:.0f}%")
        c3.metric("Max Drawdown", f"{dd:.1f}%")
        c4.metric("Voting Weight", f"{w:.2f}x")

        st.markdown("---")

        # Description sections
        if info:
            st.markdown("### How It Works")
            st.markdown(f'<div style="color:#999;font-size:15px;line-height:1.7;max-width:700px">{info.get("how", "")}</div>', unsafe_allow_html=True)

            st.markdown("")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Best For")
                st.markdown(f'<div style="color:#999;font-size:14px;line-height:1.6">{info.get("best_for", "")}</div>', unsafe_allow_html=True)
            with col2:
                st.markdown("### Risks")
                st.markdown(f'<div style="color:#999;font-size:14px;line-height:1.6">{info.get("risk", "")}</div>', unsafe_allow_html=True)

        st.markdown("---")

        # Live performance
        st.markdown("### Live Performance")
        l1, l2, l3 = st.columns(3)
        l1.metric("Live Trades", str(live_trades))
        l2.metric("Live P&L", f"${live_pnl:+,.2f}")
        live_wr = sr["win_rate"] or 0
        l3.metric("Live Win Rate", f"{live_wr:.0f}%")

        # Signals from this strategy
        strat_signals = signals[signals["strategy"] == strat_name] if not signals.empty else pd.DataFrame()
        if not strat_signals.empty:
            st.markdown("")
            st.markdown("### Current Signals")

            for _, sig in strat_signals.iterrows():
                s = sig["signal"]
                sc = G if s == "BUY" else (R if s == "SELL" else "#444")
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #111"><span style="color:#ccc;font-weight:500">{sig["symbol"]}</span><span style="color:{sc};font-weight:600">{s}</span></div>', unsafe_allow_html=True)

        # Related trades
        strat_trades = trades[trades["strategy"].str.contains(strat_name, na=False)] if not trades.empty else pd.DataFrame()
        if not strat_trades.empty:
            st.markdown("")
            st.markdown("### Trade History")
            td = strat_trades[["executed_at", "side", "symbol", "shares", "price", "pnl", "pnl_pct"]].copy()
            td.columns = ["Date", "Side", "Symbol", "Shares", "Price", "P&L $", "P&L %"]
            td["Date"] = td["Date"].dt.strftime("%Y-%m-%d")
            td["Price"] = td["Price"].map(lambda x: f"${x:,.2f}")
            td["Shares"] = td["Shares"].map(lambda x: f"{x:.0f}")
            td["P&L $"] = td["P&L $"].map(lambda x: f"${x:+,.2f}" if pd.notna(x) else "")
            td["P&L %"] = td["P&L %"].map(lambda x: f"{x:+.1f}%" if pd.notna(x) else "")
            st.dataframe(td, use_container_width=True, hide_index=True)
