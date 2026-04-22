"""Custom high-aggression strategies not in ai-trader.

These generate signals directly from OHLCV DataFrames without going through
backtrader - faster and easier to add volume/breakout logic.
"""

import pandas as pd
import numpy as np


def breakout_signal(df: pd.DataFrame, lookback: int = 20, volume_mult: float = 1.5) -> str:
    """Detect a breakout: new 20-day high on above-average volume.

    Returns BUY on breakout, SELL if price fails back below breakout level,
    otherwise HOLD.
    """
    if len(df) < lookback + 5:
        return "HOLD"

    try:
        close = df["close"]
        high = df["high"]
        vol = df["volume"]

        # Current bar stats
        curr_close = close.iloc[-1]
        curr_vol = vol.iloc[-1]

        # Previous N-day high (excluding current bar)
        prev_high = high.iloc[-lookback-1:-1].max()
        avg_vol = vol.iloc[-lookback-1:-1].mean()

        # Bullish breakout: new high + volume surge
        if curr_close > prev_high and curr_vol > avg_vol * volume_mult:
            return "BUY"

        # Breakdown: closing below the recent range with volume
        prev_low = df["low"].iloc[-lookback-1:-1].min()
        if curr_close < prev_low and curr_vol > avg_vol * volume_mult:
            return "SELL"

        return "HOLD"
    except Exception:
        return "HOLD"


def momentum_surge_signal(df: pd.DataFrame, period: int = 5, threshold: float = 0.05) -> str:
    """5-day momentum surge: strong short-term momentum with volume.

    Returns BUY when 5-day return exceeds threshold on rising volume.
    """
    if len(df) < period + 10:
        return "HOLD"

    try:
        close = df["close"]
        vol = df["volume"]

        recent_return = (close.iloc[-1] / close.iloc[-period-1]) - 1
        recent_vol_avg = vol.iloc[-period:].mean()
        baseline_vol_avg = vol.iloc[-period-20:-period].mean()

        vol_rising = recent_vol_avg > baseline_vol_avg

        if recent_return > threshold and vol_rising:
            return "BUY"
        if recent_return < -threshold:
            return "SELL"
        return "HOLD"
    except Exception:
        return "HOLD"


def rsi_divergence_signal(df: pd.DataFrame, rsi_period: int = 14) -> str:
    """RSI bouncing from deep oversold (<25) or hitting overbought (>75)."""
    if len(df) < rsi_period + 10:
        return "HOLD"

    try:
        close = df["close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()
        loss = -delta.where(delta < 0, 0).rolling(rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        curr_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]

        if pd.isna(curr_rsi) or pd.isna(prev_rsi):
            return "HOLD"

        # Bullish: RSI was below 25, now rising above 30
        if prev_rsi < 25 and curr_rsi > 30:
            return "BUY"
        # Bearish: RSI was above 75, now dropping below 70
        if prev_rsi > 75 and curr_rsi < 70:
            return "SELL"
        return "HOLD"
    except Exception:
        return "HOLD"


CUSTOM_STRATEGIES = {
    "Breakout": {
        "func": breakout_signal,
        "params": {"lookback": 20, "volume_mult": 1.5},
        "description": "20-day high breakout with volume surge",
    },
    "MomentumSurge": {
        "func": momentum_surge_signal,
        "params": {"period": 5, "threshold": 0.05},
        "description": "5-day momentum surge with rising volume",
    },
    "RSIDivergence": {
        "func": rsi_divergence_signal,
        "params": {"rsi_period": 14},
        "description": "RSI bouncing from deep oversold/overbought",
    },
}
