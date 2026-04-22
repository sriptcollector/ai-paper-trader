"""Configuration for the paper trading system."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "paper_trader.db"

# Portfolio settings - MAX AGGRESSIVE MODE
INITIAL_CASH = 100_000.00
COMMISSION_RATE = 0.001  # 0.1% per trade
LEVERAGE = 3.0           # 3x simulated margin (total buying power = cash * leverage)
MAX_POSITION_PCT = 0.40  # Max 40% per position on highest conviction trades
MAX_POSITIONS = 5        # Concentrated bets

# Interest on margin (simulated)
MARGIN_INTEREST_APR = 0.06  # 6% annual on borrowed funds

# Universe - high-volatility mix for higher return potential
UNIVERSE = [
    # Leveraged ETFs (3x daily moves)
    "TQQQ",   # 3x Nasdaq
    "SOXL",   # 3x Semiconductors
    "SPXL",   # 3x S&P 500
    "LABU",   # 3x Biotech
    "TNA",    # 3x Russell 2000
    "UPRO",   # 3x S&P 500
    # High-beta tech
    "NVDA", "TSLA", "AMD", "META", "PLTR",
    "COIN", "MSTR", "SMCI", "ARM", "AVGO",
    # Crypto
    "BTC-USD", "ETH-USD", "SOL-USD",
    # High-vol / meme
    "GME", "AMC", "MARA", "RIOT",
    # Standard large caps for stability
    "AAPL", "MSFT", "GOOGL", "AMZN",
]

# Lookback period for strategy signals (trading days)
LOOKBACK_DAYS = 252  # ~1 year of trading data

# Strategy configurations - each strategy gets a weight for ensemble voting
STRATEGY_CONFIGS = {
    "BBands": {
        "class": "BBandsStrategy",
        "params": {"period": 20, "devfactor": 2.0},
        "weight": 1.0,
        "description": "Bollinger Bands mean reversion",
    },
    "CrossSMA": {
        "class": "CrossSMAStrategy",
        "params": {},
        "weight": 1.0,
        "description": "SMA crossover trend following",
    },
    "MACD": {
        "class": "MACDStrategy",
        "params": {"fastperiod": 12, "slowperiod": 26, "signalperiod": 9},
        "weight": 1.0,
        "description": "MACD trend following",
    },
    "RSI_BBands": {
        "class": "RsiBollingerBandsStrategy",
        "params": {"rsi_period": 14, "bb_period": 20, "bb_dev": 2, "oversold": 30, "overbought": 70},
        "weight": 1.0,
        "description": "RSI + Bollinger Bands combo",
    },
    "Momentum": {
        "class": "MomentumStrategy",
        "params": {},
        "weight": 1.0,
        "description": "Momentum-based strategy",
    },
    "TripleRSI": {
        "class": "TripleRsiStrategy",
        "params": {},
        "weight": 1.0,
        "description": "Triple RSI multi-timeframe",
    },
    # Custom Python-only strategies
    "Breakout": {
        "class": "_custom",
        "params": {},
        "weight": 1.5,  # High weight - breakouts are strong signals
        "description": "20-day high breakout with volume surge",
    },
    "MomentumSurge": {
        "class": "_custom",
        "params": {},
        "weight": 1.5,
        "description": "5-day momentum surge with rising volume",
    },
    "RSIDivergence": {
        "class": "_custom",
        "params": {},
        "weight": 1.0,
        "description": "RSI bouncing from deep oversold/overbought",
    },
}

# Signal thresholds
BUY_CONSENSUS_THRESHOLD = 0.4   # 40% consensus - with 9 strategies that's 4+ agreeing
SELL_CONSENSUS_THRESHOLD = 0.25 # cut fast

# Risk management - aggressive
STOP_LOSS_PCT = 0.05       # 5% stop loss (with 3x leverage = 15% loss)
TAKE_PROFIT_PCT = 0.30     # 30% take profit (let winners run hard)
TRAILING_STOP_PCT = 0.08   # 8% trailing stop

# Intraday settings
INTRADAY_INTERVAL = "15m"  # 15-minute bars
INTRADAY_LOOKBACK_DAYS = 30
