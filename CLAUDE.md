# Rental market ML project

Personal tool to find over/under-valued Sydney rentals. Workflow: manually
save listing pages you browse into `saved_webpages/` (never automate
requests to realestate.com.au — see README.md for why), parse them into
`data/db/listings.sqlite`, then fit a model that flags listings priced
above/below what their features predict. Full workflow in README.md;
feature list in `ingest/schema.py`.

## Listing preferences

Moving in with a mate; both WFH a lot.

- **Primary target: 3-bedroom places.**
- **Also consider 2-bedroom + study/sunroom/home office** as a substitute
  for the third bedroom.
- The "third bedroom" just needs to fit two desks as a WFH office — it's
  fine if it's the smallest bedroom. If a floorplan is available, check
  it and use the `fits_two_desks_3rd_bedroom` column (manual, in the DB)
  to record the verdict; the parser can't judge this from a floorplan
  image, so it's always filled in by hand.
