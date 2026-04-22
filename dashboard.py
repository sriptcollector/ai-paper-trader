"""AI Paper Trader Dashboard.

Run: streamlit run dashboard.py
"""

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent / "paper_trader.db"
INITIAL_CASH = 100_000.0

# ─── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Paper Trader",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Apple-style CSS ──────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }

    .stApp {
        background: #000000;
    }

    /* Hide default streamlit chrome */
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #000000;
        border-right: 1px solid rgba(255,255,255,0.06);
    }
    section[data-testid="stSidebar"] .stRadio > label {
        color: rgba(255,255,255,0.5);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        font-weight: 600;
    }
    section[data-testid="stSidebar"] .stRadio > div > label {
        padding: 10px 16px;
        border-radius: 10px;
        transition: all 0.2s ease;
        font-weight: 500;
        font-size: 15px;
    }
    section[data-testid="stSidebar"] .stRadio > div > label:hover {
        background: rgba(255,255,255,0.04);
    }
    section[data-testid="stSidebar"] .stRadio > div > label[data-checked="true"] {
        background: rgba(255,255,255,0.08);
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px;
        padding: 20px 24px;
    }
    div[data-testid="stMetric"] label {
        color: rgba(255,255,255,0.45) !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 28px !important;
        font-weight: 600 !important;
        color: #ffffff !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
        font-size: 13px !important;
        font-weight: 500 !important;
    }

    /* Headings */
    h1, h2, h3 {
        font-weight: 600 !important;
        letter-spacing: -0.5px !important;
        color: #ffffff !important;
    }
    h1 { font-size: 32px !important; }
    h2 { font-size: 22px !important; color: rgba(255,255,255,0.9) !important; }
    h3 { font-size: 17px !important; color: rgba(255,255,255,0.7) !important; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: transparent;
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: rgba(255,255,255,0.4);
        font-weight: 500;
        font-size: 14px;
        padding: 12px 20px;
        border: none;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: rgba(255,255,255,0.7);
    }
    .stTabs [aria-selected="true"] {
        color: #ffffff !important;
        border-bottom: 2px solid #ffffff;
    }

    /* Dataframes */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }
    .stDataFrame [data-testid="stDataFrameResizable"] {
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
    }

    /* Dividers */
    hr {
        border-color: rgba(255,255,255,0.04) !important;
        margin: 32px 0 !important;
    }

    /* Captions / small text */
    .stCaption, small, .caption-text {
        color: rgba(255,255,255,0.35) !important;
        font-size: 12px !important;
    }

    /* Strategy card */
    .strategy-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px;
        padding: 28px;
        margin-bottom: 16px;
        transition: all 0.2s ease;
    }
    .strategy-card:hover {
        border-color: rgba(255,255,255,0.12);
        background: rgba(255,255,255,0.05);
    }
    .strategy-name {
        font-size: 20px;
        font-weight: 600;
        color: #ffffff;
        margin-bottom: 4px;
    }
    .strategy-desc {
        font-size: 13px;
        color: rgba(255,255,255,0.4);
        margin-bottom: 20px;
    }
    .strategy-return {
        font-size: 36px;
        font-weight: 700;
        letter-spacing: -1px;
    }
    .strategy-return.positive { color: #34c759; }
    .strategy-return.negative { color: #ff453a; }
    .strategy-return.neutral { color: rgba(255,255,255,0.4); }
    .strategy-stat {
        display: inline-block;
        margin-right: 28px;
    }
    .strategy-stat-label {
        font-size: 11px;
        color: rgba(255,255,255,0.35);
        text-transform: uppercase;
        letter-spacing: 0.8px;
        font-weight: 500;
    }
    .strategy-stat-value {
        font-size: 16px;
        font-weight: 600;
        color: rgba(255,255,255,0.85);
        margin-top: 2px;
    }
    .rank-badge {
        display: inline-block;
        background: rgba(255,255,255,0.06);
        border-radius: 8px;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: 600;
        color: rgba(255,255,255,0.5);
        margin-bottom: 12px;
    }
    .rank-badge.top { background: rgba(52,199,89,0.15); color: #34c759; }

    /* Position row */
    .pos-card {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 8px;
    }
    .pos-symbol {
        font-size: 17px;
        font-weight: 600;
        color: #ffffff;
    }
    .pos-detail {
        font-size: 13px;
        color: rgba(255,255,255,0.4);
    }
    .pos-pnl {
        font-size: 20px;
        font-weight: 600;
        text-align: right;
    }
    .pos-pnl.positive { color: #34c759; }
    .pos-pnl.negative { color: #ff453a; }

    /* Info boxes */
    .stAlert {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 12px !important;
        color: rgba(255,255,255,0.5) !important;
    }
</style>
""", unsafe_allow_html=True)


# ─── Data Loading ─────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_all_data():
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    data = {}

    # Portfolio
    row = conn.execute("SELECT cash FROM portfolio WHERE id = 1").fetchone()
    data["cash"] = row["cash"] if row else INITIAL_CASH

    # Positions
    data["positions"] = pd.read_sql_query("SELECT * FROM positions ORDER BY symbol", conn)

    # Trades
    data["trades"] = pd.read_sql_query(
        "SELECT * FROM trades ORDER BY executed_at DESC LIMIT 200", conn)
    if not data["trades"].empty:
        data["trades"]["executed_at"] = pd.to_datetime(data["trades"]["executed_at"])

    # Snapshots
    data["snapshots"] = pd.read_sql_query(
        "SELECT * FROM portfolio_snapshots ORDER BY date", conn)
    if not data["snapshots"].empty:
        data["snapshots"]["date"] = pd.to_datetime(data["snapshots"]["date"])

    # Strategy performance
    data["strategies"] = pd.read_sql_query(
        """SELECT * FROM strategy_performance
           WHERE date = (SELECT MAX(date) FROM strategy_performance)
           ORDER BY backtest_return_pct DESC NULLS LAST""", conn)

    # Signals
    data["signals"] = pd.read_sql_query(
        """SELECT * FROM signals
           WHERE date = (SELECT MAX(date) FROM signals)
           ORDER BY symbol, strategy""", conn)

    # Logs
    data["logs"] = pd.read_sql_query(
        "SELECT * FROM system_log ORDER BY created_at DESC LIMIT 30", conn)

    conn.close()
    return data


# ─── Plotly defaults ──────────────────────────────────────────
_AXIS_DEFAULTS = dict(gridcolor="rgba(255,255,255,0.03)", zerolinecolor="rgba(255,255,255,0.06)")

_BASE_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, -apple-system, sans-serif", color="rgba(255,255,255,0.6)", size=12),
    margin=dict(l=0, r=0, t=40, b=0),
    hoverlabel=dict(bgcolor="#1c1c1e", font_color="#ffffff", bordercolor="rgba(0,0,0,0)"),
)

def chart_layout(height=400, showlegend=False, xaxis=None, yaxis=None, **kwargs):
    """Build a plotly layout dict, merging axis defaults with overrides."""
    layout = {**_BASE_LAYOUT, "height": height, "showlegend": showlegend}
    layout["xaxis"] = {**_AXIS_DEFAULTS, **(xaxis or {})}
    layout["yaxis"] = {**_AXIS_DEFAULTS, **(yaxis or {})}
    layout.update(kwargs)
    return layout

GREEN = "#34c759"
RED = "#ff453a"
BLUE = "#0a84ff"
GRAY = "rgba(255,255,255,0.15)"


# ─── Check DB ─────────────────────────────────────────────────
if not DB_PATH.exists():
    # Auto-init with sample data for cloud deployments
    try:
        from init_cloud import seed_sample_data
        seed_sample_data()
        st.rerun()
    except Exception:
        st.markdown("### No data yet")
        st.caption("Run `python run_trader.py trade` to start.")
        st.stop()

data = load_all_data()
if not data:
    st.stop()

cash = data["cash"]
snapshots = data["snapshots"]
positions = data["positions"]
trades = data["trades"]
strategies = data["strategies"]
signals = data["signals"]


# ─── Compute values ──────────────────────────────────────────
positions_value = 0
if not snapshots.empty:
    positions_value = snapshots.iloc[-1]["positions_value"]
elif not positions.empty:
    positions_value = (positions["shares"] * positions["avg_cost"]).sum()

total_value = cash + positions_value
total_return_pct = ((total_value / INITIAL_CASH) - 1) * 100
daily_return = snapshots.iloc[-1]["daily_return_pct"] if not snapshots.empty and len(snapshots) > 0 else 0


# ─── Sidebar Navigation ──────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 20px 0 24px 0;">
        <div style="font-size: 22px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">
            Paper Trader
        </div>
        <div style="font-size: 12px; color: rgba(255,255,255,0.3); margin-top: 4px;">
            AI-Powered Trading System
        </div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "NAVIGATE",
        ["Overview", "Strategies", "Positions", "Trades", "Signals"],
        label_visibility="collapsed",
    )

    st.markdown("<br>" * 3, unsafe_allow_html=True)
    st.markdown(f"""
    <div style="padding: 16px; background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px solid rgba(255,255,255,0.04);">
        <div style="font-size: 11px; color: rgba(255,255,255,0.3); text-transform: uppercase; letter-spacing: 0.8px; font-weight: 500;">Portfolio</div>
        <div style="font-size: 24px; font-weight: 700; color: #ffffff; margin: 4px 0;">${total_value:,.0f}</div>
        <div style="font-size: 13px; font-weight: 500; color: {'#34c759' if total_return_pct >= 0 else '#ff453a'};">{total_return_pct:+.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown(f"""
    <div style="position: fixed; bottom: 20px; font-size: 11px; color: rgba(255,255,255,0.2);">
        {date.today().strftime('%B %d, %Y')}
    </div>
    """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OVERVIEW PAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if page == "Overview":
    st.markdown("# Overview")
    st.markdown("")

    # Metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Value", f"${total_value:,.2f}", f"{total_return_pct:+.2f}%")
    c2.metric("Cash", f"${cash:,.2f}")
    c3.metric("Invested", f"${positions_value:,.2f}")
    c4.metric("Positions", str(len(positions)))
    c5.metric("Daily", f"{daily_return:+.2f}%" if daily_return else "---")

    st.markdown("")

    # Portfolio chart
    if not snapshots.empty:
        tab1, tab2 = st.tabs(["Value", "Returns"])

        with tab1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=snapshots["date"], y=snapshots["total_value"],
                mode="lines", name="Portfolio",
                line=dict(color="#ffffff", width=2),
                fill="tonexty", fillcolor="rgba(255,255,255,0.02)",
            ))
            fig.add_hline(y=INITIAL_CASH, line_dash="dot",
                          line_color="rgba(255,255,255,0.1)",
                          annotation_text=f"${INITIAL_CASH:,.0f}",
                          annotation_font_color="rgba(255,255,255,0.25)")
            fig.update_layout(**chart_layout(
                height=420, yaxis=dict(tickprefix="$", tickformat=",.0f"),
            ))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with tab2:
            if "daily_return_pct" in snapshots.columns:
                colors = [GREEN if x >= 0 else RED for x in snapshots["daily_return_pct"]]
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(
                    x=snapshots["date"], y=snapshots["daily_return_pct"],
                    marker_color=colors, marker_line_width=0,
                ))
                fig2.update_layout(**chart_layout(
                    height=380, yaxis=dict(ticksuffix="%"),
                ))
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Run a trading cycle to see performance data.")

    st.markdown("")

    # Risk metrics
    if not snapshots.empty and len(snapshots) > 3:
        st.markdown("### Risk")
        returns = snapshots["daily_return_pct"].dropna()

        rc1, rc2, rc3, rc4 = st.columns(4)

        if len(returns) > 0:
            cumulative = (1 + returns / 100).cumprod()
            running_max = cumulative.cummax()
            drawdown = (cumulative - running_max) / running_max * 100
            max_dd = drawdown.min()
            rc1.metric("Max Drawdown", f"{max_dd:.2f}%")
        else:
            rc1.metric("Max Drawdown", "---")

        if len(returns) > 1 and returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * (252 ** 0.5)
            rc2.metric("Sharpe Ratio", f"{sharpe:.2f}")
        else:
            rc2.metric("Sharpe Ratio", "---")

        rc3.metric("Avg Daily", f"{returns.mean():+.3f}%" if len(returns) > 0 else "---")
        rc4.metric("Volatility", f"{returns.std() * (252**0.5):.2f}%" if len(returns) > 1 else "---")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STRATEGIES PAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "Strategies":
    st.markdown("# Strategies")
    st.markdown('<p style="color: rgba(255,255,255,0.4); font-size: 15px; margin-top: -8px;">Ranked by 90-day backtest return</p>', unsafe_allow_html=True)
    st.markdown("")

    if strategies.empty:
        st.info("Run `python run_trader.py optimize` to evaluate strategies.")
    else:
        # Sort by backtest return
        strats = strategies.sort_values("backtest_return_pct", ascending=False, na_position="last").reset_index(drop=True)

        # Summary bar chart
        fig = go.Figure()
        colors = [GREEN if (r or 0) >= 0 else RED for r in strats["backtest_return_pct"]]
        fig.add_trace(go.Bar(
            x=strats["strategy"],
            y=strats["backtest_return_pct"].fillna(0),
            marker_color=colors,
            marker_line_width=0,
            text=[f"{(r or 0):+.1f}%" for r in strats["backtest_return_pct"]],
            textposition="outside",
            textfont=dict(size=14, color="rgba(255,255,255,0.7)"),
        ))
        fig.update_layout(**chart_layout(
            height=280, yaxis=dict(ticksuffix="%", title=None),
            xaxis=dict(title=None), bargap=0.4,
        ))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.markdown("")

        # Strategy detail cards
        for i, row in strats.iterrows():
            ret = row["backtest_return_pct"] or 0
            sharpe = row["backtest_sharpe"] or 0
            dd = row["backtest_max_drawdown"] or 0
            wr = row["backtest_win_rate"] or 0
            weight = row["weight"] or 1
            desc = row["description"] or ""
            live_pnl = row["total_pnl"] or 0
            live_trades = row["total_trades"] or 0
            live_wins = row["winning_trades"] or 0
            live_wr = row["win_rate"] or 0

            ret_class = "positive" if ret > 0 else ("negative" if ret < 0 else "neutral")
            rank_class = "top" if i == 0 else ""

            st.markdown(f"""
            <div class="strategy-card">
                <div class="rank-badge {rank_class}">#{i+1}</div>
                <div class="strategy-name">{row['strategy']}</div>
                <div class="strategy-desc">{desc}</div>
                <div class="strategy-return {ret_class}">{ret:+.1f}%</div>
                <div style="margin-top: 20px;">
                    <span class="strategy-stat">
                        <div class="strategy-stat-label">Sharpe</div>
                        <div class="strategy-stat-value">{sharpe:.2f}</div>
                    </span>
                    <span class="strategy-stat">
                        <div class="strategy-stat-label">Win Rate</div>
                        <div class="strategy-stat-value">{wr:.0f}%</div>
                    </span>
                    <span class="strategy-stat">
                        <div class="strategy-stat-label">Max Drawdown</div>
                        <div class="strategy-stat-value">{dd:.1f}%</div>
                    </span>
                    <span class="strategy-stat">
                        <div class="strategy-stat-label">Weight</div>
                        <div class="strategy-stat-value">{weight:.2f}x</div>
                    </span>
                    <span class="strategy-stat">
                        <div class="strategy-stat-label">Live Trades</div>
                        <div class="strategy-stat-value">{live_trades}</div>
                    </span>
                    <span class="strategy-stat">
                        <div class="strategy-stat-label">Live P&L</div>
                        <div class="strategy-stat-value" style="color: {GREEN if live_pnl >= 0 else RED};">${live_pnl:+,.0f}</div>
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("")

        # Weight distribution
        st.markdown("### Weight Distribution")
        st.caption("Auto-optimized weekly. Higher weight = more influence in trade decisions.")

        fig_w = go.Figure()
        fig_w.add_trace(go.Bar(
            x=strats["strategy"],
            y=strats["weight"],
            marker_color="rgba(255,255,255,0.15)",
            marker_line_width=0,
            text=[f"{w:.2f}x" for w in strats["weight"]],
            textposition="outside",
            textfont=dict(size=13, color="rgba(255,255,255,0.5)"),
        ))
        fig_w.update_layout(**chart_layout(
            height=240, yaxis=dict(title=None),
            xaxis=dict(title=None), bargap=0.4,
        ))
        st.plotly_chart(fig_w, use_container_width=True, config={"displayModeBar": False})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POSITIONS PAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "Positions":
    st.markdown("# Positions")
    st.markdown("")

    if positions.empty:
        st.info("No open positions.")
    else:
        # Get latest prices from snapshot
        price_map = {}
        if not snapshots.empty:
            try:
                snap_data = json.loads(snapshots.iloc[-1]["snapshot_data"])
                for sym, info in snap_data.get("positions", {}).items():
                    price_map[sym] = info.get("current_price", 0)
            except (json.JSONDecodeError, TypeError):
                pass

        total_invested = 0
        total_current = 0

        for _, pos in positions.iterrows():
            symbol = pos["symbol"]
            shares = pos["shares"]
            avg_cost = pos["avg_cost"]
            invested = shares * avg_cost
            current_price = price_map.get(symbol, avg_cost)
            current_val = shares * current_price
            pnl_pct = ((current_price - avg_cost) / avg_cost) * 100
            pnl_dollar = current_val - invested

            total_invested += invested
            total_current += current_val

            pnl_class = "positive" if pnl_pct >= 0 else "negative"
            pnl_color = GREEN if pnl_pct >= 0 else RED

            st.markdown(f"""
            <div class="pos-card" style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div class="pos-symbol">{symbol}</div>
                    <div class="pos-detail">{shares:.0f} shares &middot; avg ${avg_cost:.2f} &middot; ${invested:,.0f} invested</div>
                </div>
                <div style="text-align: right;">
                    <div class="pos-pnl {pnl_class}">{pnl_pct:+.1f}%</div>
                    <div class="pos-detail" style="color: {pnl_color};">${pnl_dollar:+,.0f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Invested", f"${total_invested:,.0f}")
        c2.metric("Current Value", f"${total_current:,.0f}")
        overall_pnl = ((total_current / total_invested) - 1) * 100 if total_invested > 0 else 0
        c3.metric("Unrealized P&L", f"{overall_pnl:+.2f}%")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TRADES PAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "Trades":
    st.markdown("# Trades")
    st.markdown("")

    if trades.empty:
        st.info("No trades executed yet.")
    else:
        # Filters
        c1, c2 = st.columns(2)
        side_filter = c1.selectbox("Side", ["All", "BUY", "SELL"], label_visibility="collapsed")
        symbol_opts = ["All"] + sorted(trades["symbol"].unique().tolist())
        sym_filter = c2.selectbox("Symbol", symbol_opts, label_visibility="collapsed")

        filtered = trades.copy()
        if side_filter != "All":
            filtered = filtered[filtered["side"] == side_filter]
        if sym_filter != "All":
            filtered = filtered[filtered["symbol"] == sym_filter]

        # Table
        display = filtered[["executed_at", "side", "symbol", "shares", "price", "pnl", "pnl_pct", "reason"]].copy()
        display.columns = ["Date", "Side", "Symbol", "Shares", "Price", "P&L", "P&L %", "Reason"]
        display["Date"] = display["Date"].dt.strftime("%Y-%m-%d %H:%M")
        display["Price"] = display["Price"].apply(lambda x: f"${x:,.2f}")
        display["Shares"] = display["Shares"].apply(lambda x: f"{x:.0f}")
        display["P&L"] = display["P&L"].apply(lambda x: f"${x:+,.2f}" if pd.notna(x) else "")
        display["P&L %"] = display["P&L %"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "")

        st.dataframe(display, use_container_width=True, hide_index=True, height=500)

        st.markdown("")

        # Stats
        sells = trades[trades["side"] == "SELL"].dropna(subset=["pnl"])
        if not sells.empty:
            st.markdown("### Performance")
            sc1, sc2, sc3, sc4 = st.columns(4)

            wins = len(sells[sells["pnl"] > 0])
            losses = len(sells[sells["pnl"] <= 0])
            total = wins + losses

            sc1.metric("Total Closed", str(total))
            sc2.metric("Win Rate", f"{wins/total*100:.0f}%" if total > 0 else "---")
            sc3.metric("Total P&L", f"${sells['pnl'].sum():+,.2f}")
            sc4.metric("Avg P&L", f"${sells['pnl'].mean():+,.2f}")

            st.markdown("")

            # P&L distribution
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=sells["pnl"], nbinsx=25,
                marker_color="rgba(255,255,255,0.12)",
                marker_line_width=0,
            ))
            fig.add_vline(x=0, line_dash="dot", line_color="rgba(255,255,255,0.15)")
            fig.update_layout(**chart_layout(
                height=280, xaxis=dict(title=None, tickprefix="$"),
                yaxis=dict(title=None),
            ))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SIGNALS PAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "Signals":
    st.markdown("# Signals")
    st.markdown('<p style="color: rgba(255,255,255,0.4); font-size: 15px; margin-top: -8px;">Latest strategy consensus across all symbols</p>', unsafe_allow_html=True)
    st.markdown("")

    if signals.empty:
        st.info("No signals generated yet.")
    else:
        signal_map = {"BUY": 1, "HOLD": 0, "SELL": -1}
        signals["signal_val"] = signals["signal"].map(signal_map)

        pivot = signals.pivot_table(
            index="symbol", columns="strategy",
            values="signal_val", aggfunc="first"
        ).fillna(0)

        text_labels = [[{1: "BUY", 0: "", -1: "SELL"}.get(int(v), "") for v in row] for row in pivot.values]

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[
                [0, RED],
                [0.5, "rgba(255,255,255,0.03)"],
                [1, GREEN],
            ],
            zmin=-1, zmax=1,
            text=text_labels,
            texttemplate="%{text}",
            textfont=dict(size=10, color="rgba(255,255,255,0.6)"),
            showscale=False,
            xgap=2, ygap=2,
        ))
        fig.update_layout(**chart_layout(
            height=max(450, len(pivot) * 28 + 80),
            xaxis=dict(side="top"),
        ))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Consensus summary
        st.markdown("")
        st.markdown("### Consensus")

        for symbol in pivot.index:
            row_vals = pivot.loc[symbol]
            buys = int((row_vals == 1).sum())
            sells = int((row_vals == -1).sum())
            total = len(row_vals)

            if buys > sells and buys / total >= 0.4:
                consensus = f'<span style="color: {GREEN}; font-weight: 600;">BUY ({buys}/{total})</span>'
            elif sells > buys and sells / total >= 0.3:
                consensus = f'<span style="color: {RED}; font-weight: 600;">SELL ({sells}/{total})</span>'
            else:
                consensus = f'<span style="color: rgba(255,255,255,0.3);">HOLD</span>'

            st.markdown(
                f'<div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.04);">'
                f'<span style="font-weight: 500; color: rgba(255,255,255,0.8);">{symbol}</span>'
                f'{consensus}'
                f'</div>',
                unsafe_allow_html=True,
            )
