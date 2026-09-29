# Rental market ML project

Household tool to find rentals worth inspecting. Manually save listing
pages you browse into `saved_webpages/` (never automate requests to
realestate.com.au, including with an AI agent's own browser; see
README.md for why), parse them into `data/db/listings.sqlite`, then score
each listing against each person's own preferences (`score/fit_score.py`).
The useful output is "would we both like this," not just "is it
underpriced." `report/triage.py` is the daily-use view. A shared Google
Sheet (`sheets/publish.py` / `sheets/sync_back.py`) is how a non-technical
second person participates without touching git or Python. Full workflow
in README.md; feature list in `ingest/schema.py`.

This repo is public. Code and pipeline structure are meant to be shared;
personal data (what anyone's actually looking for, captured listings,
office address, API keys) is not. See "Public repo" in README.md.

## Listing preferences

Each person's criteria live in `preferences/<name>.yaml` (gitignored;
copy `preferences/example.yaml` to start one). Three parts: `hard_filters`
(budget, bedrooms, pet-friendly, max commute, etc.; fail one and a
listing is auto-flagged to skip), `preferred_suburbs` (a list, soft
rather than a hard cutoff), and `weights` (soft preference strength on
any feature in the catalogue, including a `preferred_suburbs` weight that
scores against that list). These get fully regenerated from the shared
Sheet, the "Hard filters" tab for `hard_filters` and the "Preferences"
tab for `preferred_suburbs`/`weights`, once it's set up (it already is;
see below). Hand-editing the yaml directly still works, but the next
`sheets.sync_back` overwrites it. See README "Shared Google Sheet".

## Where things stand

The Sheet is live and configured (`GOOGLE_SHEET_ID` / `GOOGLE_SHEETS_KEY_PATH`
are set in `.env`) and is the actual day-to-day interface for both Leo
and Pagni. `python refresh.py` runs sync_back, then ingest, then publish
in one go; `sheets.sync_back` / `sheets.publish` still work standalone if
you only want one step. The triage report and Sheet carry a
value-for-money signal (`predicted_weekly_rent` / `pct_over_or_under`,
from `model/train.py:predict_value`) alongside each person's fit score,
plus the raw `commute_transit_minutes` and `nearest_train_station_walk_minutes`
behind two of the weighted features. The Preferences tab uses a -5..5
whole-number scale, converted to and from the stored -1..1 weight by
`sheets/publish.py` and `sheets/sync_back.py`. `SAVED_WEBPAGES_DIR`
points at a shared Google Drive folder both Leo and Pagni can save
listing pages into directly.

A "Listings - Detail" Sheet tab (`sheets/detail_labels.py`) lets either
person correct or fill in any feature the text-keyword scan got wrong or
couldn't tell, such as fly screens, whether a kitchen reads as modern, or
`fits_two_desks_3rd_bedroom`, since a lot of that is only visible in
photos or at an inspection. Only cells changed since the last publish
count as corrections; they're stored in the `manual_overrides` table and
re-applied over any re-parse, so `ingest --force` after a keyword
improvement updates everything a human hasn't corrected. Lease term and
availability date are parsed too, with a `min_lease_term_months` hard
filter.

Deliberately not yet built (see README "Phase 2"): a "predict this
person's rating" ML model (needs more rated listings first), per-person
named anchor points beyond the one shared `OFFICE_ADDRESS` (Pagni's
WFH-only case already works today with zero new code, by leaving office
commute unweighted), and sale-listing cross-referencing for missing
floor/land size.
