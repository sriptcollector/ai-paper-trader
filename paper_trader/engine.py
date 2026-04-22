"""Core paper trading engine.

Fetches live market data, runs strategies via backtrader to extract signals,
executes paper trades, and manages portfolio state.
"""

import sys
import traceback
from datetime import datetime, date, timedelta

import backtrader as bt
import numpy as np
import pandas as pd
import yfinance as yf

from paper_trader.config import (
    UNIVERSE, LOOKBACK_DAYS, STRATEGY_CONFIGS, COMMISSION_RATE,
    MAX_POSITION_PCT, MAX_POSITIONS, BUY_CONSENSUS_THRESHOLD,
    SELL_CONSENSUS_THRESHOLD, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
    TRAILING_STOP_PCT, DATA_DIR, LEVERAGE,
)
from paper_trader.database import PortfolioDB


# Strategy class imports
from ai_trader.backtesting.strategies.classic import (
    BBandsStrategy,
    CrossSMAStrategy,
    MACDStrategy,
    RsiBollingerBandsStrategy,
    MomentumStrategy,
    TripleRsiStrategy,
)

STRATEGY_CLASSES = {
    "BBandsStrategy": BBandsStrategy,
    "CrossSMAStrategy": CrossSMAStrategy,
    "MACDStrategy": MACDStrategy,
    "RsiBollingerBandsStrategy": RsiBollingerBandsStrategy,
    "MomentumStrategy": MomentumStrategy,
    "TripleRsiStrategy": TripleRsiStrategy,
}

# Custom Python-only strategies
from paper_trader.custom_strategies import CUSTOM_STRATEGIES


def fetch_market_data(symbols: list[str], lookback_days: int = LOOKBACK_DAYS,
                       interval: str = "1d") -> dict[str, pd.DataFrame]:
    """Fetch recent OHLCV data for all symbols using yfinance.

    interval: "1d" for daily, "15m" for 15-minute intraday, etc.
    """
    end_date = date.today()

    # Intraday data has yfinance limits: 15m/5m/1m only up to 60 days
    if interval != "1d":
        start_date = end_date - timedelta(days=min(lookback_days, 58))
    else:
        start_date = end_date - timedelta(days=int(lookback_days * 1.5))

    data = {}
    try:
        # Batch download
        tickers_str = " ".join(symbols)
        raw = yf.download(tickers_str, start=start_date.isoformat(),
                          end=end_date.isoformat(), group_by="ticker",
                          auto_adjust=True, progress=False, interval=interval)

        if raw.empty:
            return data

        for symbol in symbols:
            try:
                if len(symbols) == 1:
                    df = raw.copy()
                else:
                    df = raw[symbol].copy()

                df = df.dropna()
                if len(df) < 50:  # Need minimum data for indicators
                    continue

                # Standardize column names
                df.columns = [c.lower() for c in df.columns]
                # Flatten MultiIndex columns if present
                if hasattr(df.columns, 'levels'):
                    df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]

                required = {"open", "high", "low", "close", "volume"}
                if not required.issubset(set(df.columns)):
                    continue

                data[symbol] = df
            except Exception:
                continue

    except Exception as e:
        print(f"Error fetching market data: {e}")

    return data


def get_signal_for_strategy(df: pd.DataFrame, strategy_name: str,
                            strategy_config: dict) -> str:
    """Run a strategy via full backtest and determine signal from final state.

    We run the actual strategy on historical data. If the strategy ends with a
    position, it's bullish (BUY signal for new entries). If it recently sold or
    has no position, check the last action to determine SELL or HOLD.
    """
    try:
        cls_name = strategy_config["class"]
        cls = STRATEGY_CLASSES.get(cls_name)
        if cls is None:
            return "HOLD"

        params = strategy_config.get("params", {})

        cerebro = bt.Cerebro()
        cerebro.broker.setcash(1_000_000)
        cerebro.broker.setcommission(commission=0.001)

        feed = bt.feeds.PandasData(dataname=df, timeframe=bt.TimeFrame.Days)
        cerebro.adddata(feed)

        if params:
            cerebro.addstrategy(cls, **params)
        else:
            cerebro.addstrategy(cls)

        cerebro.addsizer(bt.sizers.PercentSizer, percents=90)
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

        results = cerebro.run()
        if not results:
            return "HOLD"

        strat = results[0]

        # Check if strategy has an open position at end
        has_position = strat.position.size > 0

        # Also look at recent trade activity
        trades_analysis = strat.analyzers.trades.get_analysis()
        total_trades = trades_analysis.get("total", {}).get("total", 0)

        if has_position:
            # Strategy is currently long -> it would BUY if not already in
            return "BUY"
        elif total_trades > 0:
            # Strategy exited recently -> SELL signal
            return "SELL"
        else:
            return "HOLD"

    except Exception as e:
        return "HOLD"


def get_current_prices(symbols: list[str]) -> dict[str, float]:
    """Get latest prices for symbols."""
    prices = {}
    try:
        for symbol in symbols:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            if not hist.empty:
                prices[symbol] = float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return prices


def run_trading_cycle(intraday: bool = False):
    """Execute one complete trading cycle.

    intraday=True uses 15-minute bars for more frequent signals (60-day lookback).
    """
    db = PortfolioDB()
    mode = "INTRADAY (15m)" if intraday else "DAILY"
    db.log("INFO", f"Starting {mode} trading cycle",
           f"Time: {datetime.now().isoformat()}")

    print(f"\n{'='*60}")
    print(f"PAPER TRADING CYCLE - {mode} - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    # 1. Fetch market data
    print("\n[1/6] Fetching market data...")
    interval = "15m" if intraday else "1d"
    # Intraday: use crypto + liquid leveraged ETFs only (yf intraday is limited)
    if intraday:
        intraday_universe = [s for s in UNIVERSE if "-USD" in s or s in
                             {"TQQQ", "SOXL", "SPXL", "UPRO", "TNA", "LABU",
                              "NVDA", "TSLA", "AMD", "AAPL", "MSFT", "GOOGL", "AMZN", "META"}]
        market_data = fetch_market_data(intraday_universe, lookback_days=58, interval="15m")
    else:
        market_data = fetch_market_data(UNIVERSE)
    available_symbols = list(market_data.keys())
    print(f"  Got data for {len(available_symbols)}/{len(UNIVERSE)} symbols")

    if not available_symbols:
        db.log("ERROR", "No market data available")
        print("  ERROR: No data available. Aborting.")
        return

    # 2. Get current prices
    print("\n[2/6] Getting current prices...")
    current_prices = {}
    for symbol in available_symbols:
        df = market_data[symbol]
        current_prices[symbol] = float(df["close"].iloc[-1])
    print(f"  Prices for {len(current_prices)} symbols")

    # 3. Generate signals from all strategies
    print("\n[3/6] Running strategies and generating signals...")
    all_signals = {}  # symbol -> {strategy: signal}

    for symbol in available_symbols:
        all_signals[symbol] = {}
        df = market_data[symbol]

        # Backtrader-based strategies
        for strat_name, strat_config in STRATEGY_CONFIGS.items():
            if strat_config.get("class") == "_custom":
                continue  # handled below
            signal = get_signal_for_strategy(df, strat_name, strat_config)
            all_signals[symbol][strat_name] = signal
            db.save_signal(symbol, strat_name, signal)

        # Custom Python-only strategies (breakout, momentum surge, etc.)
        for strat_name, strat_config in CUSTOM_STRATEGIES.items():
            try:
                signal = strat_config["func"](df, **strat_config["params"])
            except Exception:
                signal = "HOLD"
            all_signals[symbol][strat_name] = signal
            db.save_signal(symbol, strat_name, signal)

    # Print signal summary
    for symbol in available_symbols:
        signals = all_signals[symbol]
        buys = sum(1 for s in signals.values() if s == "BUY")
        sells = sum(1 for s in signals.values() if s == "SELL")
        if buys > 0 or sells > 0:
            print(f"  {symbol}: BUY={buys} SELL={sells} HOLD={len(signals)-buys-sells}")

    # 4. Check risk management on existing positions
    print("\n[4/6] Checking risk management...")
    positions = db.get_positions()
    cash = db.get_cash()

    for pos in positions:
        symbol = pos["symbol"]
        if symbol not in current_prices:
            continue

        price = current_prices[symbol]
        avg_cost = pos["avg_cost"]
        pnl_pct = (price - avg_cost) / avg_cost

        # Update trailing stop
        db.update_trailing_stop(symbol, price)

        # Check stop loss
        if pnl_pct <= -STOP_LOSS_PCT:
            print(f"  STOP LOSS triggered for {symbol} (PnL: {pnl_pct*100:.1f}%)")
            _execute_sell(db, pos, price, "stop_loss")
            cash = db.get_cash()
            continue

        # Check take profit
        if pnl_pct >= TAKE_PROFIT_PCT:
            print(f"  TAKE PROFIT triggered for {symbol} (PnL: {pnl_pct*100:.1f}%)")
            _execute_sell(db, pos, price, "take_profit")
            cash = db.get_cash()
            continue

        # Check trailing stop
        trailing_high = pos.get("trailing_stop_high", avg_cost)
        if trailing_high and price < trailing_high * (1 - TRAILING_STOP_PCT):
            print(f"  TRAILING STOP triggered for {symbol}")
            _execute_sell(db, pos, price, "trailing_stop")
            cash = db.get_cash()
            continue

    # 5. Execute trades based on consensus signals
    print("\n[5/6] Executing paper trades...")
    positions = db.get_positions()  # Refresh after risk mgmt
    position_symbols = {p["symbol"] for p in positions}
    cash = db.get_cash()

    # Process SELL signals first
    for pos in positions:
        symbol = pos["symbol"]
        if symbol not in all_signals:
            continue

        signals = all_signals[symbol]
        num_strategies = len(signals)
        sell_votes = sum(1 for s in signals.values() if s == "SELL")
        sell_ratio = sell_votes / num_strategies if num_strategies > 0 else 0

        if sell_ratio >= SELL_CONSENSUS_THRESHOLD:
            strategies = [s for s, sig in signals.items() if sig == "SELL"]
            print(f"  SELL {symbol} (consensus: {sell_ratio*100:.0f}%, strategies: {', '.join(strategies)})")
            _execute_sell(db, pos, current_prices[symbol], f"consensus_sell ({sell_ratio*100:.0f}%)")
            cash = db.get_cash()

    # Process BUY signals
    positions = db.get_positions()  # Refresh
    position_symbols = {p["symbol"] for p in positions}

    buy_candidates = []
    for symbol in available_symbols:
        if symbol in position_symbols:
            continue

        signals = all_signals[symbol]
        num_strategies = len(signals)
        buy_votes = sum(1 for s in signals.values() if s == "BUY")
        buy_ratio = buy_votes / num_strategies if num_strategies > 0 else 0

        if buy_ratio >= BUY_CONSENSUS_THRESHOLD:
            buy_candidates.append((symbol, buy_ratio))

    # Sort by consensus strength, buy best candidates
    buy_candidates.sort(key=lambda x: x[1], reverse=True)

    for symbol, consensus in buy_candidates:
        positions = db.get_positions()
        if len(positions) >= MAX_POSITIONS:
            print(f"  Max positions ({MAX_POSITIONS}) reached, skipping remaining buys")
            break

        cash = db.get_cash()
        price = current_prices[symbol]

        # Compute equity (positions_value + cash - margin_used)
        positions_value = sum(
            p["shares"] * current_prices.get(p["symbol"], p["avg_cost"])
            for p in positions
        )
        equity = cash + positions_value
        buying_power = equity * LEVERAGE - positions_value  # how much more we can buy on margin

        # Scale position size by consensus strength: higher consensus = bigger bet
        size_multiplier = 1.0 + max(0, consensus - 0.5)  # 1.0x at 50%, up to 1.5x at 100%
        target_position_size = equity * MAX_POSITION_PCT * size_multiplier

        invest_amount = min(target_position_size, buying_power * 0.95)

        if invest_amount < 100:
            continue

        shares = int(invest_amount / price)
        if shares < 1:
            continue

        strategies = [s for s, sig in all_signals[symbol].items() if sig == "BUY"]
        leverage_note = f"${invest_amount:,.0f} on ${equity:,.0f} equity ({invest_amount/equity:.1f}x)"
        print(f"  BUY {shares} x {symbol} @ ${price:.2f} (consensus: {consensus*100:.0f}%, {leverage_note})")
        _execute_buy(db, symbol, shares, price, f"consensus_buy ({consensus*100:.0f}%)")

    # 6. Save daily snapshot
    print("\n[6/6] Saving portfolio snapshot...")
    positions = db.get_positions()
    cash = db.get_cash()
    positions_value = sum(
        p["shares"] * current_prices.get(p["symbol"], p["avg_cost"])
        for p in positions
    )
    total_value = cash + positions_value

    snapshot_data = {
        "positions": {p["symbol"]: {
            "shares": p["shares"],
            "avg_cost": p["avg_cost"],
            "current_price": current_prices.get(p["symbol"], p["avg_cost"]),
            "pnl_pct": ((current_prices.get(p["symbol"], p["avg_cost"]) - p["avg_cost"]) / p["avg_cost"] * 100),
        } for p in positions},
        "signals_summary": {
            symbol: {
                "buy_votes": sum(1 for s in sigs.values() if s == "BUY"),
                "sell_votes": sum(1 for s in sigs.values() if s == "SELL"),
                "total": len(sigs),
            } for symbol, sigs in all_signals.items()
        },
    }
    db.save_snapshot(cash, positions_value, len(positions), snapshot_data)

    # Update strategy performance
    for strat_name in STRATEGY_CONFIGS:
        db.update_strategy_performance(strat_name)

    db.log("INFO", "Trading cycle completed",
           f"Cash: ${cash:,.2f}, Positions: {len(positions)}, Total: ${total_value:,.2f}")

    print(f"\n{'='*60}")
    print(f"PORTFOLIO SUMMARY")
    print(f"{'='*60}")
    print(f"  Cash:            ${cash:>12,.2f}")
    print(f"  Positions Value: ${positions_value:>12,.2f}")
    print(f"  Total Value:     ${total_value:>12,.2f}")
    print(f"  Return:          {((total_value / 100000) - 1) * 100:>+11.2f}%")
    print(f"  Open Positions:  {len(positions)}")
    for p in positions:
        price = current_prices.get(p["symbol"], p["avg_cost"])
        pnl = (price - p["avg_cost"]) / p["avg_cost"] * 100
        print(f"    {p['symbol']:6s}: {p['shares']:>6.0f} shares @ ${p['avg_cost']:.2f} -> ${price:.2f} ({pnl:+.1f}%)")
    print(f"{'='*60}\n")


def _execute_buy(db: PortfolioDB, symbol: str, shares: int, price: float, reason: str):
    """Execute a paper BUY trade (margin allowed - cash can go negative up to leverage limit)."""
    cost = shares * price
    commission = cost * COMMISSION_RATE
    total_cost = cost + commission

    cash = db.get_cash()
    # Margin allowed - we just deduct; cash can go negative (borrowed funds)
    db.update_cash(cash - total_cost)
    db.open_position(
        symbol=symbol,
        shares=shares,
        price=price,
        stop_loss=price * (1 - STOP_LOSS_PCT),
        take_profit=price * (1 + TAKE_PROFIT_PCT),
        strategy=reason,
    )
    db.record_trade(symbol, "BUY", shares, price, commission, strategy=reason, reason=reason)


def _execute_sell(db: PortfolioDB, position: dict, price: float, reason: str):
    """Execute a paper SELL trade."""
    shares = position["shares"]
    revenue = shares * price
    commission = revenue * COMMISSION_RATE
    net_revenue = revenue - commission

    pnl = (price - position["avg_cost"]) * shares - commission
    pnl_pct = (price - position["avg_cost"]) / position["avg_cost"] * 100

    cash = db.get_cash()
    db.update_cash(cash + net_revenue)
    db.close_position(position["symbol"])
    db.record_trade(
        position["symbol"], "SELL", shares, price, commission,
        pnl=pnl, pnl_pct=pnl_pct,
        strategy=position.get("strategy_source", ""),
        reason=reason,
    )


if __name__ == "__main__":
    run_trading_cycle()
