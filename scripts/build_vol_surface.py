#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marketdata.config import DB_PATH
from marketdata.db import connect
from marketdata.vol import implied_volatility


def parse_date(raw: str) -> date:
    return date.fromisoformat(raw[:10])


def compute(conn: sqlite3.Connection, risk_free_rate: float) -> int:
    rows = conn.execute(
        """
        SELECT
            o.symbol, o.date, o.expiry, o.strike, o.option_type, o.close,
            COALESCE(o.underlying_price, s.close) AS spot, o.source
        FROM option_eod o
        LEFT JOIN spot_prices s
            ON s.symbol = o.symbol
           AND s.date = o.date
        WHERE o.close > 0
          AND COALESCE(o.underlying_price, s.close) IS NOT NULL
        """
    ).fetchall()
    count = 0
    for row in rows:
        trade_date = parse_date(row["date"])
        expiry = parse_date(row["expiry"])
        days = (expiry - trade_date).days
        if days <= 0:
            continue
        spot = float(row["spot"])
        strike = float(row["strike"])
        price = float(row["close"])
        iv = implied_volatility(
            option_price=price,
            spot=spot,
            strike=strike,
            years=days / 365.0,
            rate=risk_free_rate,
            option_type=row["option_type"],
        )
        if iv is None:
            continue
        conn.execute(
            """
            INSERT INTO vol_surface_points
                (symbol, date, expiry, strike, option_type, spot, moneyness, days_to_expiry,
                 option_price, implied_vol, risk_free_rate, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, date, expiry, strike, option_type) DO UPDATE SET
                spot = excluded.spot,
                moneyness = excluded.moneyness,
                days_to_expiry = excluded.days_to_expiry,
                option_price = excluded.option_price,
                implied_vol = excluded.implied_vol,
                risk_free_rate = excluded.risk_free_rate,
                source = excluded.source
            """,
            (
                row["symbol"],
                row["date"],
                row["expiry"],
                strike,
                row["option_type"],
                spot,
                strike / spot,
                days,
                price,
                iv,
                risk_free_rate,
                row["source"],
            ),
        )
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Build implied volatility surface points.")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--risk-free-rate", type=float, default=0.065)
    args = parser.parse_args()

    conn = connect(args.db)
    count = compute(conn, args.risk_free_rate)
    conn.commit()
    conn.close()
    print(f"Done. Computed {count} volatility surface points.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
