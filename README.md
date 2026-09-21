# Rental market ML project

A personal-use pipeline: manually capture rental listing pages you're
already browsing, extract structured features (bedrooms, aircon, size,
commute time, etc.), store them, and fit a simple model that flags
listings priced above or below what their features would predict.

See [`CLAUDE.md`](CLAUDE.md) for the current listing preferences (bedroom
count, WFH requirements) driving what's worth capturing.

## Why manual capture, not a scraper

realestate.com.au's Terms of Use prohibit automated scraping, and REA
Group has sued a competitor over exactly this before. Their anti-bot
protections (TLS fingerprinting, geo-blocking, rate limiting) are also
serious. So this project never sends automated requests to the site:
you browse and save pages yourself (ordinary personal use, fine under the
ToS), and the code only reads files already sitting on your disk. Keep it
this way -- don't point `requests`/Selenium/Playwright at realestate.com.au
directly.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- `OFFICE_ADDRESS` -- your commute destination.
- `GOOGLE_MAPS_API_KEY` -- a key from your own Google Cloud project with the
  **Geocoding API** and **Distance Matrix API** enabled and billing active.
  There's a free monthly allowance; this project caches every address
  lookup in the `commute_cache` DB table so you're never billed twice for
  the same address.

## Workflow

1. **Capture.** Browse rental listings on realestate.com.au normally. For
   each one you want in the dataset: `Cmd+S` (or File > Save Page As) and
   choose "Webpage, HTML Only" (or "Webpage, Complete" -- the extra
   `_files` folder it creates alongside the `.html` is harmless, the
   parser only reads the `.html` file). Save it into `saved_webpages/`.
   (Filename doesn't matter -- the parser reads the real listing ID out of
   the page itself.)

2. **Ingest.**
   ```bash
   python -m ingest.ingest
   ```
   Parses every new file in `saved_webpages/`, looks up commute time, and
   upserts into `data/db/listings.sqlite`. Safe to re-run -- already
   -ingested files are skipped. Use `--force` to re-parse everything (e.g.
   after adjusting the parser) or `--no-commute` to skip the Google Maps
   calls (useful before you've set up an API key). If a listing looks off,
   sanity check it directly:
   ```bash
   python -m ingest.parse_listing "saved_webpages/some_file.html" --debug
   ```

3. **Export (optional).**
   ```bash
   python export_csv.py
   ```
   Writes `data/exports/listings.csv` and `.xlsx` for a quick look in
   Excel/Numbers.

4. **Manual review.** For listings with a floorplan, open the `url` column
   and check whether the smaller bedroom fits two desks. Record the
   verdict in the `fits_two_desks_3rd_bedroom` column of
   `data/db/listings.sqlite` (e.g. via the free "DB Browser for SQLite"
   app, or the `sqlite3` CLI) -- this is never auto-extracted, and
   re-running ingest never overwrites it.

5. **Train / predict.**
   ```bash
   python -m model.train
   ```
   Fits a baseline (Ridge) and a gradient-boosted model, then prints every
   listing sorted by residual (actual price minus predicted price).
   Listings at the top look overpriced relative to their features;
   listings at the bottom look like potential deals.

   With only a handful of listings this is a toy -- treat results as
   noise until the dataset has at least ~50 rows, and sanity-check against
   a simple suburb-level $/sqm comparison in the meantime.

## Feature catalogue

See `ingest/schema.py` -- it's the single source of truth for every column
in the database, used by the parser, the ingester, and the model.

## What the parser actually relies on

Verified against a real saved listing. The reliable sources on a
realestate.com.au listing page are:
- `<meta name="description">` / `<meta property="og:description">` for a
  clean summary and the full description + feature bullets.
- A few stable, non-hashed CSS classes: `property-info-address`,
  `property-info__primary-features` (bed/bath/car counts, via each
  `<li aria-label="N bedrooms">`), `property-price`.
- `application/ld+json` blocks for structured suburb/postcode.

The `window.ArgonautExchange` blob some blog posts point to turned out to
often hold a leftover cache from an unrelated earlier search query rather
than this listing's own data -- don't rely on it as a primary source.

Land size / floor size are usually just **absent** from rental listings
entirely (confirmed on the sample page) -- that's the reason phase 2
below exists.

## Phase 2 (not built yet)

Sale/buy listings at the same address often list extra detail (internal
floor size, more precise land size) than the rental listing does. A later
pass can save the matching sale listing (when one exists) into
`saved_webpages_sale/` and merge its fields into the rental record by
matching on address.
