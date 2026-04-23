"""SQLite database for paper trading state."""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from paper_trader.config import DB_PATH, INITIAL_CASH


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Optional[Path] = None):
    """Create all tables if they don't exist."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cash REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            shares REAL NOT NULL,
            avg_cost REAL NOT NULL,
            opened_at TEXT NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            trailing_stop_high REAL,
            strategy_source TEXT,
            UNIQUE(symbol)
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
            shares REAL NOT NULL,
            price REAL NOT NULL,
            total_value REAL NOT NULL,
            commission REAL NOT NULL,
            pnl REAL,
            pnl_pct REAL,
            strategy TEXT,
            reason TEXT,
            executed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            cash REAL NOT NULL,
            positions_value REAL NOT NULL,
            total_value REAL NOT NULL,
            daily_return_pct REAL,
            cumulative_return_pct REAL,
            num_positions INTEGER NOT NULL,
            snapshot_data TEXT
        );

        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            strategy TEXT NOT NULL,
            signal TEXT NOT NULL CHECK (signal IN ('BUY', 'SELL', 'HOLD')),
            strength REAL,
            metadata TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS strategy_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            date TEXT NOT NULL,
            total_trades INTEGER NOT NULL DEFAULT 0,
            winning_trades INTEGER NOT NULL DEFAULT 0,
            losing_trades INTEGER NOT NULL DEFAULT 0,
            total_pnl REAL NOT NULL DEFAULT 0,
            avg_pnl REAL NOT NULL DEFAULT 0,
            win_rate REAL NOT NULL DEFAULT 0,
            weight REAL NOT NULL DEFAULT 1.0,
            backtest_return_pct REAL,
            backtest_sharpe REAL,
            backtest_max_drawdown REAL,
            backtest_win_rate REAL,
            description TEXT,
            UNIQUE(strategy, date)
        );

        CREATE TABLE IF NOT EXISTS system_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        );
    """)

    # Initialize portfolio if not exists
    existing = cursor.execute("SELECT id FROM portfolio WHERE id = 1").fetchone()
    if not existing:
        now = datetime.utcnow().isoformat()
        cursor.execute(
            "INSERT INTO portfolio (id, cash, created_at, updated_at) VALUES (1, ?, ?, ?)",
            (INITIAL_CASH, now, now),
        )

    conn.commit()
    conn.close()


class PortfolioDB:
    """Database access layer for the paper trading portfolio."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        init_db(self.db_path)

    def _conn(self):
        return get_connection(self.db_path)

    # --- Portfolio ---
    def get_cash(self) -> float:
        conn = self._conn()
        row = conn.execute("SELECT cash FROM portfolio WHERE id = 1").fetchone()
        conn.close()
        return row["cash"]

    def update_cash(self, new_cash: float):
        conn = self._conn()
        conn.execute(
            "UPDATE portfolio SET cash = ?, updated_at = ? WHERE id = 1",
            (new_cash, datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()

    # --- Positions ---
    def get_positions(self) -> list[dict]:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM positions ORDER BY symbol").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_position(self, symbol: str) -> Optional[dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM positions WHERE symbol = ?", (symbol,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def open_position(self, symbol: str, shares: float, price: float,
                      stop_loss: float = None, take_profit: float = None,
                      strategy: str = None):
        conn = self._conn()
        conn.execute(
            """INSERT INTO positions (symbol, shares, avg_cost, opened_at, stop_loss, take_profit, trailing_stop_high, strategy_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, shares, price, datetime.utcnow().isoformat(),
             stop_loss, take_profit, price, strategy),
        )
        conn.commit()
        conn.close()

    def close_position(self, symbol: str):
        conn = self._conn()
        conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        conn.commit()
        conn.close()

    def update_trailing_stop(self, symbol: str, new_high: float):
        conn = self._conn()
        conn.execute(
            "UPDATE positions SET trailing_stop_high = MAX(trailing_stop_high, ?) WHERE symbol = ?",
            (new_high, symbol),
        )
        conn.commit()
        conn.close()

    # --- Trades ---
    def record_trade(self, symbol: str, side: str, shares: float, price: float,
                     commission: float, pnl: float = None, pnl_pct: float = None,
                     strategy: str = None, reason: str = None):
        total_value = shares * price
        conn = self._conn()
        conn.execute(
            """INSERT INTO trades (symbol, side, shares, price, total_value, commission,
               pnl, pnl_pct, strategy, reason, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, side, shares, price, total_value, commission,
             pnl, pnl_pct, strategy, reason, datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()

    def get_trades(self, limit: int = 100, symbol: str = None) -> list[dict]:
        conn = self._conn()
        if symbol:
            rows = conn.execute(
                "SELECT * FROM trades WHERE symbol = ? ORDER BY executed_at DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY executed_at DESC LIMIT ?", (limit,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- Snapshots ---
    def save_snapshot(self, cash: float, positions_value: float, num_positions: int,
                      snapshot_data: dict = None):
        now = datetime.utcnow()
        today = now.date().isoformat()
        timestamp = now.isoformat()
        total_value = cash + positions_value

        conn = self._conn()
        prev = conn.execute(
            "SELECT total_value FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()

        if prev:
            ret_since_last = ((total_value / prev["total_value"]) - 1) * 100
        else:
            ret_since_last = 0.0

        cumulative_return = ((total_value / INITIAL_CASH) - 1) * 100

        # New row per cycle so we get an intraday equity curve
        conn.execute(
            """INSERT INTO portfolio_snapshots
               (date, timestamp, cash, positions_value, total_value, daily_return_pct,
                cumulative_return_pct, num_positions, snapshot_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (today, timestamp, cash, positions_value, total_value, ret_since_last,
             cumulative_return, num_positions, json.dumps(snapshot_data or {})),
        )
        conn.commit()
        conn.close()

    def get_snapshots(self, days: int = 365) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in reversed(rows)]

    # --- Signals ---
    def save_signal(self, symbol: str, strategy: str, signal: str,
                    strength: float = None, metadata: dict = None):
        today = date.today().isoformat()
        conn = self._conn()
        conn.execute(
            """INSERT INTO signals (date, symbol, strategy, signal, strength, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (today, symbol, strategy, signal, strength,
             json.dumps(metadata or {}), datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()

    def get_signals(self, date_str: str = None, symbol: str = None) -> list[dict]:
        conn = self._conn()
        query = "SELECT * FROM signals WHERE 1=1"
        params = []
        if date_str:
            query += " AND date = ?"
            params.append(date_str)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        query += " ORDER BY created_at DESC LIMIT 500"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- Strategy Performance ---
    def update_strategy_performance(self, strategy: str, weight: float = None,
                                     backtest_return_pct: float = None,
                                     backtest_sharpe: float = None,
                                     backtest_max_drawdown: float = None,
                                     backtest_win_rate: float = None,
                                     description: str = None):
        today = date.today().isoformat()
        conn = self._conn()

        # Get trade stats for this strategy
        stats = conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(pnl), 0) as total_pnl,
                COALESCE(AVG(pnl), 0) as avg_pnl
               FROM trades WHERE strategy = ? AND side = 'SELL'""",
            (strategy,),
        ).fetchone()

        total = stats["total"] or 0
        wins = stats["wins"] or 0
        win_rate = (wins / total * 100) if total > 0 else 0

        conn.execute(
            """INSERT OR REPLACE INTO strategy_performance
               (strategy, date, total_trades, winning_trades, losing_trades,
                total_pnl, avg_pnl, win_rate, weight,
                backtest_return_pct, backtest_sharpe, backtest_max_drawdown,
                backtest_win_rate, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (strategy, today, total, wins, stats["losses"] or 0,
             stats["total_pnl"], stats["avg_pnl"], win_rate,
             weight if weight is not None else 1.0,
             backtest_return_pct, backtest_sharpe, backtest_max_drawdown,
             backtest_win_rate, description),
        )
        conn.commit()
        conn.close()

    def get_strategy_performance(self) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            """SELECT * FROM strategy_performance
               WHERE date = (SELECT MAX(date) FROM strategy_performance)
               ORDER BY total_pnl DESC"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- System Log ---
    def log(self, level: str, message: str, details: str = None):
        conn = self._conn()
        conn.execute(
            "INSERT INTO system_log (level, message, details, created_at) VALUES (?, ?, ?, ?)",
            (level, message, details, datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()

    def get_logs(self, limit: int = 50, level: str = None) -> list[dict]:
        conn = self._conn()
        if level:
            rows = conn.execute(
                "SELECT * FROM system_log WHERE level = ? ORDER BY created_at DESC LIMIT ?",
                (level, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM system_log ORDER BY created_at DESC LIMIT ?", (limit,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
