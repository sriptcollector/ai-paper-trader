"""Configuration for the paper trading system."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "paper_trader.db"

# Portfolio settings - AGGRESSIVE MODE
INITIAL_CASH = 100_000.00
COMMISSION_RATE = 0.001  # 0.1% per trade
MAX_POSITION_PCT = 0.25  # Max 25% per position - concentrated bets
MAX_POSITIONS = 6        # Fewer, bigger positions

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
}

# Signal thresholds - higher bar for entry (quality over quantity)
BUY_CONSENSUS_THRESHOLD = 0.5   # 50% of strategies must agree to buy
SELL_CONSENSUS_THRESHOLD = 0.3  # 30% to sell (cut fast)

# Risk management - aggressive: tight stops, let winners run
STOP_LOSS_PCT = 0.04       # 4% stop loss (cut losers fast)
TAKE_PROFIT_PCT = 0.25     # 25% take profit (let winners run)
TRAILING_STOP_PCT = 0.06   # 6% trailing stop (protect gains)
