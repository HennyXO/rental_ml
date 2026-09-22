# Rental market ML project

Household tool to find rentals worth inspecting: manually save listing
pages you browse into `saved_webpages/` (never automate requests to
realestate.com.au -- see README.md for why, including with an AI agent's
own browser), parse them into `data/db/listings.sqlite`, then score each
listing against each person's own preferences (`score/fit_score.py`) --
the useful output is "would we both like this," not just "is it
underpriced." `report/triage.py` is the daily-use view; a shared Google
Sheet (`sheets/publish.py` / `sheets/sync_back.py`) is how a non-technical
second person participates without touching git or Python. Full workflow
in README.md; feature list in `ingest/schema.py`.

This repo is public. Code and pipeline structure are meant to be shared;
personal data (what anyone's actually looking for, captured listings,
office address, API keys) is not. See "Public repo" in README.md.

## Listing preferences

Each person's criteria live in `preferences/<name>.yaml` (gitignored --
copy `preferences/example.yaml` to start one). Three parts: `hard_filters`
(budget, bedrooms, pet-friendly, max commute, etc. -- fail one and a
listing is auto-flagged to skip), `preferred_suburbs` (a list -- soft, not
a hard cutoff), and `weights` (soft preference strength on any feature in
the catalogue, including a `preferred_suburbs` weight that scores against
that list). These get fully regenerated from the shared Sheet -- the
"Hard filters" tab for `hard_filters`, the "Preferences" tab for
`preferred_suburbs`/`weights` -- once it's set up (it already is; see
below). Hand-editing the yaml directly still works, but the next
`sheets.sync_back` overwrites it. See README "Shared Google Sheet".

## Where things stand

The Sheet is live and configured (`GOOGLE_SHEET_ID` / `GOOGLE_SHEETS_KEY_PATH`
already set in `.env`) -- it's the actual day-to-day interface for both
Leo and Pagni now, not just a plan. `python -m sheets.publish` /
`sheets.sync_back` are the two commands that move data between it and the
local DB/yaml. Deliberately not yet built (see README "Phase 2" for
details): a "predict this person's rating" ML model (needs more rated
listings first), per-person named anchor points beyond the one shared
`OFFICE_ADDRESS` (e.g. a nightlife-proximity preference -- Pagni's
WFH-only case already works today by just leaving office commute
unweighted, no code needed), and sale-listing cross-referencing for
missing floor/land size.
