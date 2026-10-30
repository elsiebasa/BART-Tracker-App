name: Build and Deploy BART Live Tracker

on:
  push:
    branches:
      - main
  schedule:
    - cron: "*/5 * * * *"
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: bart-live-tracker-deploy
  cancel-in-progress: false

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: python -m pip install requests

      - name: Fetch BART data and build JSON
        run: python build_site.py

      - name: Verify generated files
        run: |
          ls -la public
          test -s public/index.html
          test -s public/bart_data.json
          python -m json.tool public/bart_data.json > /dev/null

      - name: Upload site
        uses: actions/upload-pages-artifact@v3
        with:
          path: public

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
