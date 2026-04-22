"""Configuration for the paper trading system."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "paper_trader.db"

# Portfolio settings
INITIAL_CASH = 100_000.00
COMMISSION_RATE = 0.001  # 0.1% per trade (typical for discount brokers)
MAX_POSITION_PCT = 0.15  # Max 15% of portfolio per position
MAX_POSITIONS = 10       # Max simultaneous positions

# Universe of stocks to trade
UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "JPM", "V", "JNJ",
    "WMT", "PG", "MA", "UNH", "HD",
    "DIS", "NFLX", "AMD", "PYPL", "INTC",
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

# Signal thresholds
BUY_CONSENSUS_THRESHOLD = 0.4   # 40% of strategies must agree to buy
SELL_CONSENSUS_THRESHOLD = 0.3  # 30% of strategies must agree to sell

# Risk management
STOP_LOSS_PCT = 0.07       # 7% stop loss
TAKE_PROFIT_PCT = 0.15     # 15% take profit
TRAILING_STOP_PCT = 0.05   # 5% trailing stop
