# BART Live Departure Tracker

A small static website that displays BART estimated departure times.

## Publish it

1. Create an empty GitHub repository named `bart-live-tracker`.
2. Upload all files in this folder to the repository's `main` branch.
3. In GitHub, open **Settings → Pages**.
4. Set **Build and deployment → Source** to **Deploy from a branch**.
5. Choose branch `gh-pages` and folder `/(root)`, then save.
6. Open **Actions** and watch the workflow named **Build and Deploy BART Live Tracker**.
   The first push starts the workflow automatically.

The workflow calls BART's Legacy ETD API, writes `public/bart_data.json`, and publishes
the contents of `public/` to the `gh-pages` branch. The public API key is listed on
BART's developer page; use of the API is subject to BART's license agreement.

## Local run (optional)

Python 3.11+ is recommended.

```bash
python -m pip install requests
python build_site.py
```

The browser page refreshes its JSON request every minute. The GitHub Actions schedule
requests new data every five minutes, but GitHub may delay scheduled runs.
