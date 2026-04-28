# Deployment

## Free Web/iOS PWA Deployment

IndVol is designed to run on free static hosting. The production bundle is the `public/` directory:

- `index.html`
- `app.js`
- `styles.css`
- `manifest.webmanifest`
- `service-worker.js`
- `icons/`
- `data/`

The app first tries API endpoints during local development. If those endpoints are not available, it falls back to static JSON files under `public/data/`, which makes it compatible with GitHub Pages.

## Refresh Static Data

```bash
python3 scripts/collect_market_data.py --months 4 --insecure
python3 scripts/collect_nse_fo_bhavcopy.py --months 4 --insecure
python3 scripts/build_realized_vol.py
python3 scripts/build_vol_surface.py
python3 scripts/export_static_data.py
```

Commit the changed files under `public/data/` after refreshing.

## GitHub Pages

Use a `gh-pages` branch for free static hosting. This avoids needing GitHub token `workflow` scope.

```bash
git push -u origin main
git subtree push --prefix public origin gh-pages
```

Then enable Pages from the `gh-pages` branch in repository settings, or configure it with GitHub CLI/API if available.

Open the generated Pages URL on iPhone Safari, then use Share -> Add to Home Screen -> Open as Web App.
