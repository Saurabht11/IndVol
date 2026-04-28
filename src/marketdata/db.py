from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS underlyings (
    symbol TEXT PRIMARY KEY,
    provider_symbol TEXT NOT NULL,
    name TEXT,
    asset_type TEXT NOT NULL DEFAULT 'equity',
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS spot_prices (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    adj_close REAL,
    volume INTEGER,
    source TEXT NOT NULL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS option_eod (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    expiry TEXT NOT NULL,
    strike REAL NOT NULL,
    option_type TEXT NOT NULL CHECK (option_type IN ('CE', 'PE')),
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    underlying_price REAL,
    volume INTEGER,
    open_interest INTEGER,
    source TEXT NOT NULL,
    PRIMARY KEY (symbol, date, expiry, strike, option_type)
);

CREATE TABLE IF NOT EXISTS realized_vol (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    window_days INTEGER NOT NULL,
    realized_vol REAL NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (symbol, date, window_days)
);

CREATE TABLE IF NOT EXISTS vol_surface_points (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    expiry TEXT NOT NULL,
    strike REAL NOT NULL,
    option_type TEXT NOT NULL CHECK (option_type IN ('CE', 'PE')),
    spot REAL NOT NULL,
    moneyness REAL NOT NULL,
    days_to_expiry INTEGER NOT NULL,
    option_price REAL NOT NULL,
    implied_vol REAL NOT NULL,
    risk_free_rate REAL NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (symbol, date, expiry, strike, option_type)
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    ensure_migrations(conn)
    return conn


def ensure_migrations(conn: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(option_eod)").fetchall()
    }
    if "underlying_price" not in columns:
        conn.execute("ALTER TABLE option_eod ADD COLUMN underlying_price REAL")


def upsert_underlying(conn: sqlite3.Connection, symbol: str, provider_symbol: str, source: str) -> None:
    conn.execute(
        """
        INSERT INTO underlyings (symbol, provider_symbol, source)
        VALUES (?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            provider_symbol = excluded.provider_symbol,
            source = excluded.source
        """,
        (symbol, provider_symbol, source),
    )


def upsert_spot_prices(conn: sqlite3.Connection, rows: list[dict]) -> int:
    conn.executemany(
        """
        INSERT INTO spot_prices
            (symbol, date, open, high, low, close, adj_close, volume, source)
        VALUES
            (:symbol, :date, :open, :high, :low, :close, :adj_close, :volume, :source)
        ON CONFLICT(symbol, date) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            adj_close = excluded.adj_close,
            volume = excluded.volume,
            source = excluded.source
        """,
        rows,
    )
    return len(rows)
