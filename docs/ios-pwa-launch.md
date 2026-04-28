# Launch IndVol Free on iOS

The zero-cost iOS launch path is a Progressive Web App hosted over HTTPS.

## Why PWA

- App Store distribution requires Apple Developer Program membership.
- A PWA can be installed from Safari using Add to Home Screen.
- GitHub Pages can host the static app for free.

Apple's user flow is Safari -> Share -> Add to Home Screen -> Open as Web App -> Add.

## Build static data

```bash
python3 scripts/export_static_data.py
```

This writes static JSON files to `public/data/`. The iOS app can load these files directly from GitHub Pages without a backend server.

## Free hosting

1. Push the repository to GitHub.
2. Enable GitHub Pages.
3. Set the Pages source to the repository folder that contains `public/`.
4. Open the HTTPS Pages URL on iPhone Safari.
5. Add it to the Home Screen as `IndVol`.

## Native iOS later

A native App Store release is possible later, but it is not zero-cost because Apple Developer Program membership is paid.

