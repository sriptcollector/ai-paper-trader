#!/usr/bin/env python3
"""Auto-trader: runs the trading engine continuously.

Trades on 15-minute intraday bars every 15 minutes during market hours (9:30-16:00 ET),
plus a daily close cycle and weekly optimization.

Usage:
    python auto_trader.py            # Run forever
    python auto_trader.py --once     # Run one cycle and exit
"""

import sys
import time
import traceback
from datetime import datetime, date, timedelta
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from paper_trader.database import PortfolioDB
from paper_trader.engine import run_trading_cycle
from paper_trader.optimizer import optimize_weights


INTERVAL_SECONDS = 15 * 60  # 15 minutes


def is_market_open() -> bool:
    """Rough check: US market hours M-F 9:30-16:00 ET (treating local as ET)."""
    now = datetime.now()
    weekday = now.weekday()  # Mon=0, Sun=6
    if weekday >= 5:
        return False
    # Simplified: assume local timezone maps close to ET
    hour_min = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= hour_min <= 16 * 60


def crypto_only_time() -> bool:
    """Outside US market hours - can still trade crypto 24/7."""
    return not is_market_open()


def run_loop(once: bool = False):
    db = PortfolioDB()
    print(f"\n{'='*60}")
    print(f"AUTO-TRADER STARTED - {datetime.now().isoformat()}")
    print(f"Interval: {INTERVAL_SECONDS}s ({INTERVAL_SECONDS//60} min)")
    print(f"{'='*60}\n")

    last_optimize_date = None
    last_daily_close = None

    while True:
        try:
            now = datetime.now()
            today_str = now.date().isoformat()

            # Weekly optimize on Monday (only once per day)
            if now.weekday() == 0 and last_optimize_date != today_str:
                print(f"[{now.strftime('%H:%M:%S')}] Running weekly optimization...")
                try:
                    optimize_weights()
                    last_optimize_date = today_str
                except Exception as e:
                    db.log("ERROR", f"Optimize failed: {e}")
                    print(f"  OPTIMIZE ERROR: {e}")

            # Main trading cycle
            market_open = is_market_open()
            if market_open:
                print(f"[{now.strftime('%H:%M:%S')}] Running INTRADAY cycle (market open)")
                run_trading_cycle(intraday=True)
            else:
                # Outside market hours: just run crypto-aware daily cycle less often
                if last_daily_close != today_str:
                    print(f"[{now.strftime('%H:%M:%S')}] Running DAILY cycle (market closed)")
                    run_trading_cycle(intraday=False)
                    last_daily_close = today_str
                else:
                    print(f"[{now.strftime('%H:%M:%S')}] Market closed, already ran daily cycle. Sleeping...")

        except Exception as e:
            db.log("ERROR", f"Cycle crashed: {e}", traceback.format_exc())
            print(f"\nCYCLE ERROR: {e}")
            traceback.print_exc()

        if once:
            break

        # Sleep until next interval
        print(f"  Sleeping {INTERVAL_SECONDS}s until next cycle...\n")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    once = "--once" in sys.argv
    try:
        run_loop(once=once)
    except KeyboardInterrupt:
        print("\nAuto-trader stopped.")
