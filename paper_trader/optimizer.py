"""Strategy optimizer - adjusts strategy weights based on historical performance.

Runs periodic backtests on recent data to evaluate which strategies are
performing best, then adjusts their voting weights in the ensemble.
"""

import traceback
from datetime import date, timedelta

import backtrader as bt
import pandas as pd

from paper_trader.config import STRATEGY_CONFIGS, INITIAL_CASH
from paper_trader.database import PortfolioDB
from paper_trader.engine import fetch_market_data, STRATEGY_CLASSES, UNIVERSE


def backtest_strategy_recent(df: pd.DataFrame, strategy_class, params: dict,
                              lookback_days: int = 90) -> dict:
    """Run a backtest on recent data and return performance metrics."""
    try:
        # Use only recent data
        if len(df) > lookback_days:
            df = df.iloc[-lookback_days:]

        cerebro = bt.Cerebro()
        cerebro.broker.setcash(100_000)
        cerebro.broker.setcommission(commission=0.001)

        feed = bt.feeds.PandasData(dataname=df, timeframe=bt.TimeFrame.Days)
        cerebro.adddata(feed)
        cerebro.addstrategy(strategy_class, **params)
        cerebro.addsizer(bt.sizers.PercentSizer, percents=90)
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

        initial = cerebro.broker.getvalue()
        results = cerebro.run()
        final = cerebro.broker.getvalue()

        strat = results[0]
        sharpe = strat.analyzers.sharpe.get_analysis().get("sharperatio") or 0
        max_dd = strat.analyzers.drawdown.get_analysis().get("max", {}).get("drawdown", 0)
        total_return = ((final / initial) - 1) * 100

        trades_analysis = strat.analyzers.trades.get_analysis()
        total_trades = trades_analysis.get("total", {}).get("total", 0)
        won = trades_analysis.get("won", {}).get("total", 0)
        win_rate = (won / total_trades * 100) if total_trades > 0 else 0

        return {
            "return_pct": total_return,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "final_value": final,
        }
    except Exception as e:
        return {
            "return_pct": 0, "sharpe": 0, "max_drawdown": 0,
            "total_trades": 0, "win_rate": 0, "final_value": 100_000,
            "error": str(e),
        }


def optimize_weights():
    """Evaluate all strategies on recent data and update their weights."""
    db = PortfolioDB()
    db.log("INFO", "Starting strategy optimization")
    print("\nOptimizing strategy weights...")

    # Fetch data for a subset of the universe
    test_symbols = UNIVERSE[:10]  # Use top 10 for speed
    market_data = fetch_market_data(test_symbols, lookback_days=180)

    if not market_data:
        db.log("ERROR", "No data for optimization")
        return

    # Score each strategy across multiple stocks
    strategy_scores = {}

    for strat_name, strat_config in STRATEGY_CONFIGS.items():
        cls = STRATEGY_CLASSES.get(strat_config["class"])
        if cls is None:
            continue

        params = strat_config.get("params", {})
        results_list = []

        for symbol, df in market_data.items():
            result = backtest_strategy_recent(df, cls, params, lookback_days=90)
            results_list.append(result)

        if not results_list:
            continue

        # Aggregate metrics across stocks
        avg_return = sum(r["return_pct"] for r in results_list) / len(results_list)
        avg_sharpe = sum(r["sharpe"] for r in results_list) / len(results_list)
        avg_win_rate = sum(r["win_rate"] for r in results_list) / len(results_list)
        avg_drawdown = sum(r["max_drawdown"] for r in results_list) / len(results_list)

        # Composite score: reward returns and sharpe, penalize drawdown
        score = (avg_return * 0.3) + (avg_sharpe * 20) + (avg_win_rate * 0.2) - (avg_drawdown * 0.3)

        strategy_scores[strat_name] = {
            "score": score,
            "avg_return": avg_return,
            "avg_sharpe": avg_sharpe,
            "avg_win_rate": avg_win_rate,
            "avg_drawdown": avg_drawdown,
        }

        print(f"  {strat_name:20s}: score={score:+.2f}, return={avg_return:+.1f}%, "
              f"sharpe={avg_sharpe:.2f}, win_rate={avg_win_rate:.0f}%, dd={avg_drawdown:.1f}%")

    if not strategy_scores:
        db.log("WARNING", "No strategy scores computed")
        return

    # Normalize scores to weights (min 0.2, max 2.0)
    min_score = min(s["score"] for s in strategy_scores.values())
    max_score = max(s["score"] for s in strategy_scores.values())
    score_range = max_score - min_score if max_score != min_score else 1

    for strat_name, scores in strategy_scores.items():
        normalized = (scores["score"] - min_score) / score_range  # 0 to 1
        weight = 0.2 + (normalized * 1.8)  # Map to 0.2 - 2.0
        STRATEGY_CONFIGS[strat_name]["weight"] = weight
        desc = STRATEGY_CONFIGS[strat_name].get("description", "")
        db.update_strategy_performance(
            strat_name, weight=weight,
            backtest_return_pct=scores["avg_return"],
            backtest_sharpe=scores["avg_sharpe"],
            backtest_max_drawdown=scores["avg_drawdown"],
            backtest_win_rate=scores["avg_win_rate"],
            description=desc,
        )
        print(f"  {strat_name}: new weight = {weight:.2f}")

    db.log("INFO", "Strategy optimization complete",
           str({k: v["score"] for k, v in strategy_scores.items()}))
    print("Optimization complete.\n")


if __name__ == "__main__":
    optimize_weights()
