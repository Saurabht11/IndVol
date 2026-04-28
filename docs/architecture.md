# Architecture

## Goals

Build an Indian stock market research website with:

- Market dashboard for indices, equities, and volatility.
- Historical price database.
- Realized volatility analytics.
- Historical implied volatility surfaces where option EOD data is available.
- A provider-adapter boundary so free prototype data can later be replaced by licensed feeds.

## Constraints

- Keep current operating cost at zero.
- Do not depend on NSE/BSE website scraping for a public product.
- Use local storage first.
- Prefer reproducible CSV/SQLite artifacts.

## System design

```text
Data sources
  |
  |-- Yahoo chart endpoint: index/equity/VIX daily OHLC
  |-- Manual CSV imports: historical option EOD data
  |-- Future licensed providers: TrueData, Global Datafeeds, NSE/BSE feeds
  v
Provider adapters
  |
  |-- normalize symbols
  |-- normalize dates
  |-- normalize OHLC/options fields
  v
SQLite research warehouse
  |
  |-- underlyings
  |-- spot_prices
  |-- option_eod
  |-- realized_vol
  |-- vol_surface_points
  v
API layer
  |
  |-- dashboard endpoints
  |-- stock detail endpoints
  |-- volatility endpoints
  |-- surface endpoints
  v
Web UI
```

## Data pipeline

1. `collect_market_data.py` downloads daily OHLC for configured symbols.
2. Raw responses are saved under `data/raw/yahoo/`.
3. Normalized prices are upserted into SQLite.
4. `build_realized_vol.py` computes rolling realized volatility.
5. Option CSVs can be placed under `data/raw/options/`.
6. `import_options_csv.py` normalizes option EOD records.
7. `build_vol_surface.py` computes Black-Scholes implied volatility points.

## Website modules

- Dashboard: market indices, top movers, VIX, realized volatility snapshot.
- Instrument page: OHLC history, realized vol, returns, drawdown.
- Volatility page: IV surface, smile/skew, term structure, realized-vs-implied.
- Data admin: import CSVs, inspect coverage, refresh data.

## Provider adapter contract

Each data provider should expose normalized records:

```python
{
    "symbol": "NIFTY",
    "date": "2026-04-28",
    "open": 24300.0,
    "high": 24410.0,
    "low": 24180.0,
    "close": 24365.0,
    "volume": 0,
    "source": "yahoo"
}
```

Options records:

```python
{
    "symbol": "NIFTY",
    "date": "2026-04-28",
    "expiry": "2026-05-28",
    "strike": 24500.0,
    "option_type": "CE",
    "close": 150.0,
    "volume": 10000,
    "open_interest": 500000,
    "source": "csv"
}
```

