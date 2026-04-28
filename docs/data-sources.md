# Data Sources

## Free sources for V1

### Yahoo Finance chart endpoint

Use for daily OHLC history for indices, stocks, and India VIX-like symbols where available.

Pros:
- Free.
- No API key.
- Simple historical OHLC.

Cons:
- Not an official exchange data license.
- Symbol coverage can change.
- No historical option-chain archive.

### Manual option CSV imports

Use for historical NIFTY/BANKNIFTY option EOD files from free datasets or personal downloads.

Pros:
- Keeps platform cost at zero.
- Allows historical surface construction.
- Reproducible once files are saved.

Cons:
- Data quality varies.
- Field names differ by source.
- Licensing must be checked before redistribution.

### NSE F&O UDiFF bhavcopy archive

Current archive pattern:

```text
https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip
```

Use for EOD option records, not intraday option-chain snapshots. The archive includes option OHLC, close, volume, open interest, expiry, strike, option type, and underlying price.

## Future paid/licensed providers

- TrueData
- Global Datafeeds
- Direct NSE/BSE market data products

These should be added by implementing a new provider adapter, not by changing the analytics layer.
