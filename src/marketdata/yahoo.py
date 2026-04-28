from __future__ import annotations

import json
import ssl
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path


def unix_day(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def fetch_chart(provider_symbol: str, start: date, end: date, insecure: bool = False) -> dict:
    params = urllib.parse.urlencode(
        {
            "period1": unix_day(start),
            "period2": unix_day(end) + 86400,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    encoded_symbol = urllib.parse.quote(provider_symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    context = ssl._create_unverified_context() if insecure else None
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def save_raw(payload: dict, raw_dir: str, symbol: str) -> Path:
    path = Path(raw_dir)
    path.mkdir(parents=True, exist_ok=True)
    out = path / f"{symbol}_{int(time.time())}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def normalize_chart(symbol: str, payload: dict) -> list[dict]:
    result = payload["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    quote = result["indicators"]["quote"][0]
    adjclose = result["indicators"].get("adjclose", [{}])[0].get("adjclose", [])
    rows = []
    for idx, ts in enumerate(timestamps):
        close = quote["close"][idx]
        if close is None:
            continue
        rows.append(
            {
                "symbol": symbol,
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
                "open": quote["open"][idx],
                "high": quote["high"][idx],
                "low": quote["low"][idx],
                "close": close,
                "adj_close": adjclose[idx] if idx < len(adjclose) else close,
                "volume": quote["volume"][idx],
                "source": "yahoo",
            }
        )
    return rows
