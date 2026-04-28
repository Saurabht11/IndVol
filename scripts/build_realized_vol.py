#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marketdata.config import DB_PATH
from marketdata.db import connect


WINDOWS = (7, 14, 30, 60)


def realized_vol(closes: list[float]) -> float | None:
    if len(closes) < 2:
        return None
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252)


def compute(conn: sqlite3.Connection, symbol: str) -> int:
    rows = conn.execute(
        "SELECT date, close FROM spot_prices WHERE symbol = ? ORDER BY date",
        (symbol,),
    ).fetchall()
    inserted = 0
    for idx, row in enumerate(rows):
        for window in WINDOWS:
            window_rows = rows[max(0, idx - window + 1) : idx + 1]
            if len(window_rows) < window:
                continue
            vol = realized_vol([float(r["close"]) for r in window_rows])
            if vol is None:
                continue
            conn.execute(
                """
                INSERT INTO realized_vol (symbol, date, window_days, realized_vol, source)
                VALUES (?, ?, ?, ?, 'computed')
                ON CONFLICT(symbol, date, window_days) DO UPDATE SET
                    realized_vol = excluded.realized_vol,
                    source = excluded.source
                """,
                (symbol, row["date"], window, vol),
            )
            inserted += 1
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Build realized volatility series.")
    parser.add_argument("--db", default=DB_PATH)
    args = parser.parse_args()

    conn = connect(args.db)
    symbols = [r["symbol"] for r in conn.execute("SELECT DISTINCT symbol FROM spot_prices ORDER BY symbol")]
    total = 0
    for symbol in symbols:
        count = compute(conn, symbol)
        total += count
        print(f"{symbol}: computed {count} realized-vol rows")
    conn.commit()
    conn.close()
    print(f"Done. Computed {total} realized-vol rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

