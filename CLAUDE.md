# Rental market ML project

Personal tool to find over/under-valued Sydney rentals. Workflow: manually
save listing pages you browse into `saved_webpages/` (never automate
requests to realestate.com.au — see README.md for why), parse them into
`data/db/listings.sqlite`, then fit a model that flags listings priced
above/below what their features predict. Full workflow in README.md;
feature list in `ingest/schema.py`.

This repo is public. Code and pipeline structure are meant to be shared;
personal data (what you're actually looking for, the listings you've
captured, your office address, API keys) is not. See "Public repo" in
README.md for what that means in practice.

## Listing preferences

Current criteria live in `LISTING_PREFERENCES.local.md` (gitignored --
copy it from `LISTING_PREFERENCES.example.md` if it doesn't exist yet).
Read that file for what's actually being looked for right now.
