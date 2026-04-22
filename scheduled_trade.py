#!/usr/bin/env python3
"""Scheduled trading script - designed to run daily via Task Scheduler.

Runs at market close (4 PM ET) or any time after to process the day's data.
Performs optimization weekly (Sundays) and trading daily (Mon-Fri).
"""

import sys
import os
from datetime import date, datetime

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from paper_trader.database import PortfolioDB
from paper_trader.engine import run_trading_cycle
from paper_trader.optimizer import optimize_weights


def main():
    today = date.today()
    weekday = today.weekday()  # 0=Monday, 6=Sunday

    db = PortfolioDB()
    db.log("INFO", f"Scheduled run started (weekday={weekday})")

    # Skip weekends for trading (markets closed)
    if weekday >= 5:
        db.log("INFO", "Weekend - skipping trading cycle")
        print(f"Weekend ({today}) - skipping trading. Markets are closed.")

        # Run optimization on Sunday
        if weekday == 6:
            print("Running weekly strategy optimization...")
            optimize_weights()
        return

    # Run optimization on Mondays
    if weekday == 0:
        print("Monday - running weekly optimization first...")
        optimize_weights()

    # Run trading cycle
    print(f"Running trading cycle for {today}...")
    run_trading_cycle()

    db.log("INFO", "Scheduled run completed")


if __name__ == "__main__":
    main()
