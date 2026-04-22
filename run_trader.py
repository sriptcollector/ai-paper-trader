#!/usr/bin/env python3
"""Entry point for the paper trading system.

Usage:
    python run_trader.py trade      # Run one trading cycle
    python run_trader.py optimize   # Run strategy optimization
    python run_trader.py full       # Run optimization + trading cycle
    python run_trader.py reset      # Reset portfolio to initial state
    python run_trader.py status     # Print current portfolio status
"""

import sys
from datetime import date

from paper_trader.database import PortfolioDB, init_db
from paper_trader.engine import run_trading_cycle, get_current_prices
from paper_trader.optimizer import optimize_weights
from paper_trader.config import INITIAL_CASH, UNIVERSE


def print_status():
    db = PortfolioDB()
    cash = db.get_cash()
    positions = db.get_positions()

    # Get current prices for held positions
    held_symbols = [p["symbol"] for p in positions]
    prices = get_current_prices(held_symbols) if held_symbols else {}

    positions_value = sum(
        p["shares"] * prices.get(p["symbol"], p["avg_cost"])
        for p in positions
    )
    total = cash + positions_value
    ret = ((total / INITIAL_CASH) - 1) * 100

    print(f"\n{'='*60}")
    print(f"PORTFOLIO STATUS - {date.today().isoformat()}")
    print(f"{'='*60}")
    print(f"  Cash:            ${cash:>12,.2f}")
    print(f"  Positions Value: ${positions_value:>12,.2f}")
    print(f"  Total Value:     ${total:>12,.2f}")
    print(f"  Return:          {ret:>+11.2f}%")
    print(f"  Open Positions:  {len(positions)}")

    if positions:
        print(f"\n  {'Symbol':8s} {'Shares':>8s} {'Avg Cost':>10s} {'Current':>10s} {'P&L %':>8s}")
        print(f"  {'-'*48}")
        for p in positions:
            price = prices.get(p["symbol"], p["avg_cost"])
            pnl = (price - p["avg_cost"]) / p["avg_cost"] * 100
            print(f"  {p['symbol']:8s} {p['shares']:>8.0f} ${p['avg_cost']:>9.2f} ${price:>9.2f} {pnl:>+7.1f}%")

    # Recent trades
    trades = db.get_trades(limit=10)
    if trades:
        print(f"\n  Recent Trades:")
        print(f"  {'Date':12s} {'Side':6s} {'Symbol':8s} {'Shares':>8s} {'Price':>10s} {'P&L':>10s}")
        print(f"  {'-'*58}")
        for t in trades:
            pnl_str = f"${t['pnl']:>+9.2f}" if t['pnl'] is not None else "         -"
            dt = t['executed_at'][:10]
            print(f"  {dt:12s} {t['side']:6s} {t['symbol']:8s} {t['shares']:>8.0f} ${t['price']:>9.2f} {pnl_str}")

    print(f"{'='*60}\n")


def reset_portfolio():
    """Reset portfolio to initial state."""
    import os
    from paper_trader.config import DB_PATH
    if DB_PATH.exists():
        os.remove(DB_PATH)
    init_db()
    print(f"Portfolio reset to ${INITIAL_CASH:,.2f}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "trade":
        run_trading_cycle()
    elif command == "intraday":
        run_trading_cycle(intraday=True)
    elif command == "optimize":
        optimize_weights()
    elif command == "full":
        optimize_weights()
        run_trading_cycle()
    elif command == "reset":
        reset_portfolio()
    elif command == "status":
        print_status()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
