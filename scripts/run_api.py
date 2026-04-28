#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import sqlite3
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marketdata.config import DB_PATH
from marketdata.db import connect


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


class MarketApi(BaseHTTPRequestHandler):
    db_path = DB_PATH
    static_dir = str(Path(__file__).resolve().parents[1] / "public")

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/health":
                self.send_json({"status": "ok"})
            elif parsed.path == "/api/coverage":
                self.coverage()
            elif parsed.path == "/api/prices":
                self.prices(params)
            elif parsed.path == "/api/realized-vol":
                self.realized_vol(params)
            elif parsed.path == "/api/surface":
                self.surface(params)
            elif parsed.path == "/api/surface-dates":
                self.surface_dates(params)
            elif parsed.path == "/api/surface-history":
                self.surface_history(params)
            else:
                self.serve_static(parsed.path)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def coverage(self) -> None:
        with connect(self.db_path) as conn:
            spot = rows_to_dicts(
                conn.execute(
                    """
                    SELECT symbol, COUNT(*) AS rows, MIN(date) AS start_date, MAX(date) AS end_date
                    FROM spot_prices
                    GROUP BY symbol
                    ORDER BY symbol
                    """
                ).fetchall()
            )
            realized = conn.execute("SELECT COUNT(*) AS rows FROM realized_vol").fetchone()["rows"]
            options = conn.execute("SELECT COUNT(*) AS rows FROM option_eod").fetchone()["rows"]
            surfaces = conn.execute("SELECT COUNT(*) AS rows FROM vol_surface_points").fetchone()["rows"]
        self.send_json(
            {
                "spot_prices": spot,
                "realized_vol_rows": realized,
                "option_rows": options,
                "surface_rows": surfaces,
            }
        )

    def prices(self, params: dict[str, list[str]]) -> None:
        symbol = params.get("symbol", ["NIFTY"])[0].upper()
        limit = int(params.get("limit", ["250"])[0])
        with connect(self.db_path) as conn:
            rows = rows_to_dicts(
                conn.execute(
                    """
                    SELECT date, open, high, low, close, adj_close, volume
                    FROM spot_prices
                    WHERE symbol = ?
                    ORDER BY date DESC
                    LIMIT ?
                    """,
                    (symbol, limit),
                ).fetchall()
            )
        self.send_json({"symbol": symbol, "prices": list(reversed(rows))})

    def realized_vol(self, params: dict[str, list[str]]) -> None:
        symbol = params.get("symbol", ["NIFTY"])[0].upper()
        window = int(params.get("window", ["30"])[0])
        with connect(self.db_path) as conn:
            rows = rows_to_dicts(
                conn.execute(
                    """
                    SELECT date, window_days, realized_vol
                    FROM realized_vol
                    WHERE symbol = ? AND window_days = ?
                    ORDER BY date
                    """,
                    (symbol, window),
                ).fetchall()
            )
        self.send_json({"symbol": symbol, "window_days": window, "series": rows})

    def surface(self, params: dict[str, list[str]]) -> None:
        symbol = params.get("symbol", ["NIFTY"])[0].upper()
        as_of = params.get("date", [None])[0]
        option_type = params.get("option_type", ["ALL"])[0].upper()
        with connect(self.db_path) as conn:
            if as_of is None:
                row = conn.execute(
                    "SELECT MAX(date) AS date FROM vol_surface_points WHERE symbol = ?",
                    (symbol,),
                ).fetchone()
                as_of = row["date"]
            filters = ["symbol = ?", "date = ?"]
            args: list[object] = [symbol, as_of]
            if option_type in {"CE", "PE"}:
                filters.append("option_type = ?")
                args.append(option_type)
            rows = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT date, expiry, strike, option_type, spot, moneyness,
                           days_to_expiry, option_price, implied_vol,
                           COALESCE(o.volume, 0) AS volume,
                           COALESCE(o.open_interest, 0) AS open_interest
                    FROM vol_surface_points
                    LEFT JOIN option_eod o
                      USING (symbol, date, expiry, strike, option_type)
                    WHERE {' AND '.join(filters)}
                    ORDER BY days_to_expiry, strike, option_type
                    """,
                    args,
                ).fetchall()
            )
        self.send_json({"symbol": symbol, "date": as_of, "points": rows})

    def surface_dates(self, params: dict[str, list[str]]) -> None:
        symbol = params.get("symbol", ["NIFTY"])[0].upper()
        with connect(self.db_path) as conn:
            rows = rows_to_dicts(
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
        self.send_json({"symbol": symbol, "dates": rows})

    def surface_history(self, params: dict[str, list[str]]) -> None:
        symbol = params.get("symbol", ["NIFTY"])[0].upper()
        option_type = params.get("option_type", ["ALL"])[0].upper()
        with connect(self.db_path) as conn:
            filters = ["symbol = ?"]
            args: list[object] = [symbol]
            if option_type in {"CE", "PE"}:
                filters.append("option_type = ?")
                args.append(option_type)
            surface_rows = rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT date, days_to_expiry, spot, moneyness, implied_vol
                    FROM vol_surface_points
                    WHERE {' AND '.join(filters)}
                    ORDER BY date, days_to_expiry, ABS(moneyness - 1)
                    """,
                    args,
                ).fetchall()
            )
            realized_rows = {
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
        for row in surface_rows:
            by_date.setdefault(row["date"], []).append(row)

        history = []
        for day, rows in by_date.items():
            atm = min(rows, key=lambda row: abs(row["moneyness"] - 1))
            tenors: dict[int, list[dict]] = {}
            for row in rows:
                tenors.setdefault(row["days_to_expiry"], []).append(row)
            tenor_atm = [
                min(items, key=lambda row: abs(row["moneyness"] - 1))
                for _, items in sorted(tenors.items())
            ]
            short = tenor_atm[0] if tenor_atm else None
            long = tenor_atm[-1] if tenor_atm else None
            term_slope = None
            if short and long and short is not long:
                term_slope = long["implied_vol"] - short["implied_vol"]
            history.append(
                {
                    "date": day,
                    "points": len(rows),
                    "spot": atm["spot"],
                    "atm_iv": atm["implied_vol"],
                    "short_dte": short["days_to_expiry"] if short else None,
                    "short_iv": short["implied_vol"] if short else None,
                    "long_dte": long["days_to_expiry"] if long else None,
                    "long_iv": long["implied_vol"] if long else None,
                    "term_slope": term_slope,
                    "realized_vol_30d": realized_rows.get(day),
                }
            )
        history.sort(key=lambda row: row["date"])
        self.send_json({"symbol": symbol, "option_type": option_type, "history": history})

    def serve_static(self, request_path: str) -> None:
        safe_path = request_path.strip("/") or "index.html"
        if ".." in safe_path:
            self.send_json({"error": "invalid_path"}, HTTPStatus.BAD_REQUEST)
            return
        path = Path(self.static_dir) / safe_path
        if path.is_dir():
            path = path / "index.html"
        if not path.exists() or not path.is_file():
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local market data API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--static-dir", default=str(Path(__file__).resolve().parents[1] / "public"))
    args = parser.parse_args()

    MarketApi.db_path = args.db
    MarketApi.static_dir = args.static_dir
    server = ThreadingHTTPServer((args.host, args.port), MarketApi)
    print(f"Serving API at http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
