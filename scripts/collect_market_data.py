#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marketdata.config import DB_PATH, DEFAULT_SYMBOLS
from marketdata.db import connect, upsert_spot_prices, upsert_underlying
from marketdata.yahoo import fetch_chart, normalize_chart, save_raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect free daily market data.")
    parser.add_argument("--months", type=int, default=4)
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--raw-dir", default="data/raw/yahoo")
    parser.add_argument("--symbols", nargs="*", default=list(DEFAULT_SYMBOLS.keys()))
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification for local collection when the Python CA store is unavailable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    end = date.today()
    start = end - timedelta(days=round(args.months * 31))
    conn = connect(args.db)
    total = 0

    for symbol in args.symbols:
        provider_symbol = DEFAULT_SYMBOLS.get(symbol, symbol)
        print(f"Fetching {symbol} ({provider_symbol}) from {start} to {end}")
        try:
            payload = fetch_chart(provider_symbol, start, end, insecure=args.insecure)
            save_raw(payload, args.raw_dir, symbol)
            rows = normalize_chart(symbol, payload)
            upsert_underlying(conn, symbol, provider_symbol, "yahoo")
            total += upsert_spot_prices(conn, rows)
            conn.commit()
            print(f"  stored {len(rows)} rows")
        except Exception as exc:
            print(f"  failed: {exc}")

    conn.close()
    print(f"Done. Stored/updated {total} spot rows in {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
