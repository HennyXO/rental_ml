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
copy `preferences/example.yaml` to start one). Two parts: `hard_filters`
(budget, bedrooms, allowed suburbs, etc. -- fail one and a listing is
auto-flagged to skip) and `weights` (soft preference strength on any
feature in the catalogue). These get regenerated from the shared Sheet's
"Preferences" tab once both people have done the feature-ranking exercise
there -- see README "Shared Google Sheet".
