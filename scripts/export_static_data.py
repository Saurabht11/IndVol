#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marketdata.config import DB_PATH
from marketdata.db import connect


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def surface_rows(conn: sqlite3.Connection, symbol: str, day: str) -> list[dict]:
    return rows_to_dicts(
        conn.execute(
            """
            SELECT v.date, v.expiry, v.strike, v.option_type, v.spot, v.moneyness,
                   v.days_to_expiry, v.option_price, v.implied_vol,
                   COALESCE(o.volume, 0) AS volume,
                   COALESCE(o.open_interest, 0) AS open_interest
            FROM vol_surface_points v
            LEFT JOIN option_eod o
              USING (symbol, date, expiry, strike, option_type)
            WHERE v.symbol = ? AND v.date = ?
            ORDER BY v.days_to_expiry, v.strike, v.option_type
            """,
            (symbol, day),
        ).fetchall()
    )


def surface_history(conn: sqlite3.Connection, symbol: str) -> list[dict]:
    rows = rows_to_dicts(
        conn.execute(
            """
            SELECT date, days_to_expiry, spot, moneyness, implied_vol
            FROM vol_surface_points
            WHERE symbol = ?
            ORDER BY date, days_to_expiry, ABS(moneyness - 1)
            """,
            (symbol,),
        ).fetchall()
    )
    realized = {
        row["date"]: row["realized_vol"]
        for row in conn.execute(
            """
            SELECT date, realized_vol
            FROM realized_vol
            WHERE symbol = ? AND window_days = 30
            """,
            (symbol,),
        ).fetchall()
    }
    by_date: dict[str, list[dict]] = {}
    for row in rows:
        by_date.setdefault(row["date"], []).append(row)

    history = []
    for day, items in by_date.items():
        atm = min(items, key=lambda row: abs(row["moneyness"] - 1))
        tenors: dict[int, list[dict]] = {}
        for row in items:
            tenors.setdefault(row["days_to_expiry"], []).append(row)
        tenor_atm = [min(group, key=lambda row: abs(row["moneyness"] - 1)) for _, group in sorted(tenors.items())]
        short = tenor_atm[0] if tenor_atm else None
        long = tenor_atm[-1] if tenor_atm else None
        history.append(
            {
                "date": day,
                "points": len(items),
                "spot": atm["spot"],
                "atm_iv": atm["implied_vol"],
                "short_dte": short["days_to_expiry"] if short else None,
                "short_iv": short["implied_vol"] if short else None,
                "long_dte": long["days_to_expiry"] if long else None,
                "long_iv": long["implied_vol"] if long else None,
                "term_slope": long["implied_vol"] - short["implied_vol"] if short and long and short is not long else None,
                "realized_vol_30d": realized.get(day),
            }
        )
    return sorted(history, key=lambda row: row["date"])


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export SQLite surface data for static hosting.")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--out-dir", default="public/data")
    parser.add_argument("--symbols", nargs="*", default=["NIFTY", "BANKNIFTY"])
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    conn = connect(args.db)
    manifest = {"symbols": [], "generated_from": args.db}

    for symbol in args.symbols:
      symbol = symbol.upper()
      dates = rows_to_dicts(
          conn.execute(
              """
              SELECT date, COUNT(*) AS points
              FROM vol_surface_points
              WHERE symbol = ?
              GROUP BY date
              ORDER BY date
              """,
              (symbol,),
          ).fetchall()
      )
      manifest["symbols"].append({"symbol": symbol, "dates": dates})
      write_json(out_dir / symbol / "dates.json", {"symbol": symbol, "dates": dates})
      write_json(out_dir / symbol / "history.json", {"symbol": symbol, "option_type": "ALL", "history": surface_history(conn, symbol)})
      for row in dates:
          payload = {"symbol": symbol, "date": row["date"], "points": surface_rows(conn, symbol, row["date"])}
          write_json(out_dir / symbol / f"{row['date']}.json", payload)
      print(f"{symbol}: exported {len(dates)} dates")

    write_json(out_dir / "manifest.json", manifest)
    conn.close()
    print(f"Done. Static data exported to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

