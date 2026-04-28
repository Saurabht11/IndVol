#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marketdata.config import DB_PATH
from marketdata.db import connect


ALIASES = {
    "symbol": ("symbol", "underlying", "underlying_symbol", "SYMBOL", "TckrSymb"),
    "date": ("date", "trade_date", "TIMESTAMP", "timestamp", "TradDt"),
    "expiry": ("expiry", "expiry_date", "EXPIRY_DT", "XpryDt"),
    "strike": ("strike", "strike_price", "STRIKE_PR", "StrkPric"),
    "option_type": ("option_type", "type", "OPTION_TYP", "instrument_type", "OptnTp"),
    "open": ("open", "OPEN", "OpnPric"),
    "high": ("high", "HIGH", "HghPric"),
    "low": ("low", "LOW", "LwPric"),
    "close": ("close", "settle", "SETTLE_PR", "CLOSE", "ClsPric"),
    "underlying_price": ("underlying_price", "underlying", "UndrlygPric"),
    "volume": ("volume", "contracts", "CONTRACTS", "TtlTradgVol"),
    "open_interest": ("open_interest", "oi", "OPEN_INT", "OpnIntrst"),
}


def value(row: dict, field: str) -> str | None:
    for alias in ALIASES[field]:
        if alias in row and row[alias] not in ("", None):
            return row[alias]
    return None


def number(raw: str | None) -> float | None:
    if raw is None:
        return None
    return float(str(raw).replace(",", "").strip())


def integer(raw: str | None) -> int | None:
    if raw is None:
        return None
    return int(float(str(raw).replace(",", "").strip()))


def normalize_type(raw: str | None) -> str:
    text = (raw or "").upper().strip()
    if text in {"CE", "CALL", "C"}:
        return "CE"
    if text in {"PE", "PUT", "P"}:
        return "PE"
    raise ValueError(f"Unsupported option type: {raw}")


def import_file(path: Path, db: str) -> int:
    conn = connect(db)
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                {
                    "symbol": value(row, "symbol"),
                    "date": value(row, "date"),
                    "expiry": value(row, "expiry"),
                    "strike": number(value(row, "strike")),
                    "option_type": normalize_type(value(row, "option_type")),
                    "open": number(value(row, "open")),
                    "high": number(value(row, "high")),
                    "low": number(value(row, "low")),
                    "close": number(value(row, "close")),
                    "underlying_price": number(value(row, "underlying_price")),
                    "volume": integer(value(row, "volume")),
                    "open_interest": integer(value(row, "open_interest")),
                    "source": f"csv:{path.name}",
                }
            )

    conn.executemany(
        """
        INSERT INTO option_eod
            (symbol, date, expiry, strike, option_type, open, high, low, close, underlying_price, volume, open_interest, source)
        VALUES
            (:symbol, :date, :expiry, :strike, :option_type, :open, :high, :low, :close, :underlying_price, :volume, :open_interest, :source)
        ON CONFLICT(symbol, date, expiry, strike, option_type) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            underlying_price = excluded.underlying_price,
            volume = excluded.volume,
            open_interest = excluded.open_interest,
            source = excluded.source
        """,
        rows,
    )
    conn.commit()
    conn.close()
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import historical option EOD CSV files.")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--db", default=DB_PATH)
    args = parser.parse_args()

    total = 0
    for item in args.files:
        count = import_file(Path(item), args.db)
        total += count
        print(f"{item}: imported {count} rows")
    print(f"Done. Imported {total} option rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
