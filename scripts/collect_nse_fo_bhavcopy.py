#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import ssl
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marketdata.config import DB_PATH
from marketdata.db import connect


NSE_FO_URL = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{yyyymmdd}_F_0000.csv.zip"
DEFAULT_SYMBOLS = ("NIFTY", "BANKNIFTY")
OPTION_TYPES = {"CE", "PE"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download NSE F&O EOD bhavcopy archives.")
    parser.add_argument("--months", type=int, default=4)
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--raw-dir", default="data/raw/nse_fo")
    parser.add_argument("--symbols", nargs="*", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument(
        "--include-zero-volume",
        action="store_true",
        help="Keep contracts with zero traded volume. Default skips them for cleaner surfaces.",
    )
    return parser.parse_args()


def date_range(start: date, end: date) -> list[date]:
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def parse_date(raw: str | None, fallback: date | None = None) -> date:
    if raw:
        return date.fromisoformat(raw)
    if fallback is None:
        raise ValueError("date required")
    return fallback


def download_zip(day: date, raw_dir: Path, insecure: bool) -> Path | None:
    yyyymmdd = day.strftime("%Y%m%d")
    url = NSE_FO_URL.format(yyyymmdd=yyyymmdd)
    out = raw_dir / f"BhavCopy_NSE_FO_0_0_0_{yyyymmdd}_F_0000.csv.zip"
    if out.exists() and out.stat().st_size > 0:
        return out

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
        },
    )
    context = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(request, timeout=30, context=context) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in {403, 404}:
            return None
        raise
    out.write_bytes(data)
    return out


def number(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    return float(raw.replace(",", ""))


def integer(raw: str | None) -> int | None:
    if raw is None or raw == "":
        return None
    return int(float(raw.replace(",", "")))


def rows_from_zip(path: Path, symbols: set[str], include_zero_volume: bool) -> list[dict]:
    rows = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if not names:
            return []
        text = archive.read(names[0]).decode("utf-8-sig")
    for row in csv.DictReader(io.StringIO(text)):
        symbol = row.get("TckrSymb", "").upper()
        option_type = row.get("OptnTp", "").upper()
        volume = integer(row.get("TtlTradgVol"))
        if symbols and symbol not in symbols:
            continue
        if option_type not in OPTION_TYPES:
            continue
        if not include_zero_volume and not volume:
            continue
        close = number(row.get("ClsPric"))
        strike = number(row.get("StrkPric"))
        if close is None or close <= 0 or strike is None or strike <= 0:
            continue
        rows.append(
            {
                "symbol": symbol,
                "date": row["TradDt"],
                "expiry": row["XpryDt"],
                "strike": strike,
                "option_type": option_type,
                "open": number(row.get("OpnPric")),
                "high": number(row.get("HghPric")),
                "low": number(row.get("LwPric")),
                "close": close,
                "underlying_price": number(row.get("UndrlygPric")),
                "volume": volume,
                "open_interest": integer(row.get("OpnIntrst")),
                "source": f"nse_fo:{path.name}",
            }
        )
    return rows


def upsert_option_rows(conn, rows: list[dict]) -> int:
    conn.executemany(
        """
        INSERT INTO option_eod
            (symbol, date, expiry, strike, option_type, open, high, low, close,
             underlying_price, volume, open_interest, source)
        VALUES
            (:symbol, :date, :expiry, :strike, :option_type, :open, :high, :low, :close,
             :underlying_price, :volume, :open_interest, :source)
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
    return len(rows)


def main() -> int:
    args = parse_args()
    today = date.today()
    end = parse_date(args.end_date, today)
    start = parse_date(args.start_date, end - timedelta(days=round(args.months * 31)))
    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    symbols = {symbol.upper() for symbol in args.symbols if symbol.upper() != "ALL"}
    if any(symbol.upper() == "ALL" for symbol in args.symbols):
        symbols = set()

    conn = connect(args.db)
    downloaded = 0
    imported = 0
    skipped = 0
    for day in date_range(start, end):
        try:
            path = download_zip(day, raw_dir, args.insecure)
            if path is None:
                skipped += 1
                continue
            downloaded += 1
            rows = rows_from_zip(path, symbols, args.include_zero_volume)
            imported += upsert_option_rows(conn, rows)
            conn.commit()
            print(f"{day}: imported {len(rows)} rows")
        except Exception as exc:
            skipped += 1
            print(f"{day}: skipped ({exc})")

    conn.close()
    print(f"Done. Archives found: {downloaded}; skipped: {skipped}; imported rows: {imported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
