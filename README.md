# Indian Market Volatility Platform

Zero-cost research platform for Indian market dashboards, historical price analytics, and volatility surface construction.

## Current scope

- Collect last 4 months of free daily market data from Yahoo Finance chart endpoints.
- Store normalized data in local SQLite.
- Import historical options CSV files when available.
- Compute realized volatility from spot history.
- Compute implied volatility and volatility-surface points from option EOD data.

## Important data note

A true historical implied volatility surface requires historical option-chain data by trade date, expiry, strike, call/put, option price, and underlying spot. Free sources are inconsistent, and NSE/BSE redistribution has licensing restrictions. This project is structured to remain cost-free for personal research while keeping provider adapters separate so a licensed feed can be added later.

## Quick start

```bash
python3 scripts/collect_market_data.py --months 4
python3 scripts/collect_nse_fo_bhavcopy.py --months 4 --insecure
python3 scripts/build_realized_vol.py
python3 scripts/build_vol_surface.py
python3 scripts/export_static_data.py
python3 scripts/run_api.py
```

The local database is written to `data/market.sqlite`.

API examples:

```bash
curl http://127.0.0.1:8000/api/coverage
curl "http://127.0.0.1:8000/api/prices?symbol=NIFTY"
curl "http://127.0.0.1:8000/api/realized-vol?symbol=NIFTY&window=30"
```

## iOS app path

IndVol is configured as a Progressive Web App in `public/`. For zero-cost iOS launch, export static data with `scripts/export_static_data.py`, host `public/` on GitHub Pages, then add the HTTPS URL to the iPhone Home Screen from Safari.

See `docs/deployment.md` for the `gh-pages` deployment flow.

## Layout

```text
docs/                  Architecture and data-source notes
scripts/               Data collection and processing scripts
src/marketdata/        Reusable Python package
data/raw/              Raw downloaded or manually supplied data
data/processed/        Derived CSV exports
data/market.sqlite     Local SQLite database
```
