"""Initialize a sample database for cloud deployment demos.

Run this once after deploying to seed the database with sample data
so the dashboard has something to display.
"""

import sys
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from paper_trader.database import PortfolioDB, init_db
from paper_trader.config import INITIAL_CASH


def seed_sample_data():
    init_db()
    db = PortfolioDB()

    # Save a baseline snapshot
    db.save_snapshot(INITIAL_CASH, 0, 0, {"positions": {}, "signals_summary": {}})

    # Add strategy descriptions
    strategies = [
        ("RSI_BBands", 3.2, 0.17, 5.1, 40, 2.0, "RSI + Bollinger Bands combo"),
        ("BBands", 2.2, -0.31, 12.5, 60, 1.61, "Bollinger Bands mean reversion"),
        ("Momentum", 2.6, -0.32, 4.7, 30, 1.42, "Momentum-based strategy"),
        ("TripleRSI", 0.0, 0.0, 0.0, 0, 1.47, "Triple RSI multi-timeframe"),
        ("MACD", -2.5, -0.58, 2.6, 0, 0.82, "MACD trend following"),
        ("CrossSMA", 0.5, -1.23, 3.6, 0, 0.20, "SMA crossover trend following"),
    ]
    for name, ret, sharpe, dd, wr, weight, desc in strategies:
        db.update_strategy_performance(
            name, weight=weight,
            backtest_return_pct=ret, backtest_sharpe=sharpe,
            backtest_max_drawdown=dd, backtest_win_rate=wr,
            description=desc,
        )

    db.log("INFO", "Cloud database initialized with sample data")
    print("Sample database created.")


if __name__ == "__main__":
    seed_sample_data()
