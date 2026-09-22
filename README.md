# Rental market ML project

A household tool: manually capture rental listing pages you're already
browsing, extract structured features (bedrooms, aircon, size, commute,
nearest station/school/supermarket/park, etc.), score each listing against
each person's own preferences, and share the results so you can decide
together whether something's worth inspecting -- without either of you
reading every listing end to end.

See `CLAUDE.md` for a short orientation and `preferences/example.yaml` for
how personal preferences are structured.

## Public repo

This repo is public: the code and pipeline are meant to be shared, but
nothing personal should end up in git. Gitignored and never committed:
- `.env` -- office address, Google Maps API key, Sheets config.
- `preferences/*.yaml` (except `example.yaml`) -- what each of you is
  actually looking for and how much you weight it.
- `google_sheets_service_account.json` -- the Sheets service account key.
- `saved_webpages/` and `saved_webpages_sale/` -- the raw HTML pages
  you've captured.
- `data/db/` and `data/exports/` -- the parsed listings themselves
  (addresses, prices, your computed commute times, ratings).

If you fork or reuse this, everything above is yours to fill in locally;
none of it is needed to run the code itself. Nothing here is rent-specific
except the price-parsing regex in `ingest/parse_listing.py` -- the same
pipeline works fine for evaluating places to buy.

## Why manual capture, not a scraper

realestate.com.au's Terms of Use prohibit automated scraping, and REA
Group has sued a competitor over exactly this before. Their anti-bot
protections (TLS fingerprinting, geo-blocking, rate limiting) are also
serious. So this project never sends automated requests to the site --
not `requests`/Selenium/Playwright, and not an AI agent driving a browser
either, even a graphical one. The thing that matters isn't headless vs.
graphical, it's automated vs. human: you browse and save pages yourself
(ordinary personal use, fine under the ToS -- including opening listings
from your own saved-search email alerts, a legitimate first-party
feature), and the code only reads files already sitting on your disk.

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
  **Geocoding API** and **Routes API** enabled and billing active. There's
  a free monthly allowance; this project caches every address lookup in
  the `commute_cache` DB table so you're never billed twice for the same
  address.
- `GOOGLE_SHEETS_KEY_PATH` / `GOOGLE_SHEET_ID` -- optional, see "Shared
  Google Sheet" below. Everything else works fine without these set.

Also copy `preferences/example.yaml` to `preferences/<your-name>.yaml` for
each person and fill in your own hard filters / preferred suburbs /
weights (or do it via the Sheet's "Hard filters" and "Preferences" tabs
once that's set up -- see below).

## Workflow

1. **Capture.** Browse rental listings on realestate.com.au normally --
   including from your own saved-search email alerts, which is exactly
   what they're for. For each one you want in the dataset: `Cmd+S` (or
   File > Save Page As) and choose "Webpage, HTML Only". Save it into
   `saved_webpages/`. (Filename doesn't matter -- the parser reads the
   real listing ID out of the page itself.)

   If more than one of you is capturing listings, set `SAVED_WEBPAGES_DIR`
   in `.env` to a folder inside whatever cloud-synced drive you already
   share (Dropbox/Google Drive/iCloud). Either of you can then save a page
   from your own browser straight into it.

2. **Ingest.**
   ```bash
   python -m ingest.ingest
   ```
   Parses every new file in `saved_webpages/`, looks up commute time and
   nearest points of interest, and upserts into `data/db/listings.sqlite`.
   Safe to re-run -- already-ingested files are skipped. Use `--force` to
   re-parse everything (e.g. after adjusting the parser) or `--no-commute`
   to skip the Google Maps calls. If a listing looks off, sanity check it
   directly:
   ```bash
   python -m ingest.parse_listing "saved_webpages/some_file.html" --debug
   ```

3. **Triage report.**
   ```bash
   python -m report.triage
   ```
   The actual daily-use view: every listing with each person's hard-filter
   status, fit score (see `score/fit_score.py` -- weighted, transparent,
   useful from listing #1, no ML training needed), any manual rating,
   and a suggested next action (worth inspecting / discuss -- scores
   diverge / skip -- hard filter failed / awaiting rating).

4. **Rate, and mark progress.** Either log a rating straight into the
   `ratings` table (`listing_id, person, score, comment`) via a SQLite
   tool, or do it through the shared Sheet (next section) -- much easier
   for a non-technical second rater. Set `status` on a listing
   (`inspecting`, `applied`, `rejected`, ...) the same way, by hand, as
   things progress; the triage report reflects whatever you set there and
   won't second-guess it.

5. **Export (optional).**
   ```bash
   python export_csv.py
   ```
   Writes `data/exports/listings.csv` and `.xlsx` for a quick look in
   Excel/Numbers.

6. **Train / predict price (optional).**
   ```bash
   python -m model.train
   ```
   Fits a baseline (Ridge) and a gradient-boosted model against
   `weekly_rent_aud`, then prints every listing sorted by residual. This
   answers "is this overpriced relative to the market" -- a different,
   secondary question to the personal fit score above, and one that needs
   ~50+ listings before it says anything trustworthy.

## Shared Google Sheet

Lets a non-technical second person (no git/Python needed) browse listings
and log ratings/status from their phone, and gives both of you a place to
do the feature-ranking exercise together. One-time setup:

1. In the same Google Cloud project as your Maps API key: enable the
   **Google Sheets API**, then create a **service account**
   (IAM & Admin > Service Accounts > Create), and download its JSON key.
   Save it somewhere in the project (e.g. `google_sheets_service_account.json`
   at the repo root -- already gitignored) and set `GOOGLE_SHEETS_KEY_PATH`
   in `.env` to that path.
2. Create a new Google Sheet, and share it (the usual "Share" button) with
   the service account's email address (looks like
   `something@your-project.iam.gserviceaccount.com`, in the downloaded
   JSON's `client_email` field) as an Editor.
3. Copy the Sheet's ID from its URL
   (`docs.google.com/spreadsheets/d/<THIS PART>/edit`) into
   `GOOGLE_SHEET_ID` in `.env`.

Then:
```bash
python -m sheets.publish     # DB -> Sheet: listings, fit scores, "Preferences" + "Hard filters" tabs
python -m sheets.sync_back   # Sheet -> DB/yaml: ratings, status, comments, weights, hard filters
```
Both are run manually, on demand -- no scheduling yet. **Run `sync_back`
before `publish`** if you've made edits in the Sheet you want kept:
`publish` does a full overwrite of the computed columns and doesn't try to
merge concurrent edits.

The Sheet is the only place either person needs to set or adjust their own
preferences day to day -- no yaml editing required, which matters since
one of you may not have this repo at all. The "Preferences" tab is the
weighted-ranking exercise: one row per feature (with a plain-English
`what_this_means` column), a `<name>_weight` column each of you fills in
directly. The "Hard filters" tab is the actual dealbreakers -- budget,
minimum bedrooms, pet-friendly required, max commute -- one row per
filter, a `<name>_value` column each of you fills in; a blank cell means
that filter doesn't apply to you. `sync_back` regenerates
`preferences/<name>.yaml` (`hard_filters`, `preferred_suburbs`, and
`weights`) from whatever's currently in the Sheet -- hand-editing the
yaml directly still works, but the next `sync_back` overwrites it.

Suburbs get two options, deliberately not just one: `allowed_suburbs` in
"Hard filters" is a hard cutoff (a listing outside the list is auto-
skipped, no exceptions -- often too strict). `preferred_suburbs_list` +
the `preferred_suburbs` weight in "Preferences" is the softer version --
boosts the score for suburbs you like without ruling out anything else,
computed as a straight `suburb in preferred_suburbs` boolean rather than
a normal numeric column (see the special-case in
`score/fit_score.py:score_person`). Most people want the soft version;
`allowed_suburbs` stays available for anyone who really does want a hard
cutoff.

## Feature catalogue

See `ingest/schema.py` -- it's the single source of truth for every column
in the database, used by the parser, the ingester, the fit score, and the
price model.

## Nearest station / school / supermarket / park / beach

Two one-time setup steps, then it's free forever. Points of interest are
computed the same way regardless of source: nearest candidate found via
free local straight-line math, then one Routes API walking-time call on
just that candidate (not one per point of interest) -- see `ingest/poi.py`.

**Train/metro/light rail** -- from TfNSW's GTFS feed, which authoritatively
labels each by `route_type` (far more reliable than guessing from a
generic "nearby transit" search):
1. Create a free account at
   [opendata.transport.nsw.gov.au](https://opendata.transport.nsw.gov.au)
   and download the **"Timetables Complete GTFS"** zip.
2. `python -m ingest.build_transit_stations path/to/downloaded_gtfs.zip`
   -> `data/transit_stations.csv` (committed -- small, public data).

**School/supermarket/park/beach** -- from OpenStreetMap's Overpass API,
free and no account needed:
```bash
python -m ingest.build_poi
```
-> `data/poi.csv` (also committed). The public Overpass instance can be
slow/rate-limited for large categories (parks especially); the script
retries with backoff and merges into any existing file rather than
overwriting it, so a category that fails one run just keeps its previous
data until you re-run.

Either way, re-run `python -m ingest.ingest --force` afterward to backfill
these fields for listings already ingested. Skipping this setup just
leaves the `nearest_*` columns null -- everything else keeps working.

## What the parser actually relies on

Verified against real saved listings. The reliable sources on a
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
entirely -- that's the reason phase 2 below exists.

## Phase 2 (not built yet)

Sale/buy listings at the same address often list extra detail (internal
floor size, more precise land size) than the rental listing does. A later
pass can save the matching sale listing (when one exists) into
`saved_webpages_sale/` and merge its fields into the rental record by
matching on address.

A trained "predict this person's rating from features" model is also a
natural later step once `ratings` has ~30-50+ rows -- more directly useful
than the price model, but needs volume first; `score/fit_score.py` covers
the gap until then.

**Per-person named anchor points** (office, nightlife hub, gym, etc. --
each with its own commute time, rather than everyone sharing one
`OFFICE_ADDRESS`) was scoped and explicitly deferred (2026-09-22):
addresses would move from `.env` into personal preferences, commute to
each gets computed on the fly and cached in a new table instead of stored
per-listing (since it's no longer one shared value), and a new Sheet tab
would let each person name their own anchor points. Worth building once a
second/different anchor point is actually needed in practice -- Pagni's
WFH-only case already works today with zero new code, by just leaving
office commute unweighted in his preferences.
