"""Curated, human-editable per-listing feature detail. Backs the "Listings
- Detail" tab: one row per listing, one column per feature a keyword scan
can get wrong or simply can't tell (fly screens, a genuinely "modern"
kitchen, whether the 3rd bedroom fits two desks), so it can be corrected
from photos or an inspection. Corrections land in ingest/schema.py's
manual_overrides table, which outlives any re-parse. Unlike sheets/feature_labels.py (how much
you WEIGHT a feature), this is about what's actually TRUE for a listing.

Reuses sheets/hard_filter_labels.py's parse_value/render_value, same
cell format, just a different set of columns and a different write target
(an UPDATE on `listings` in sheets/sync_back.py, not a preferences yaml).
"""
from __future__ import annotations

from ingest.schema import AMENITY_KEYWORDS

# column -> (plain-English label, value type: "boolean" | "number" | "date")
_AMENITY_DETAIL_LABELS: dict[str, str] = {
    "air_conditioning": "Air conditioning",
    "built_in_wardrobes": "Built-in wardrobes",
    "dishwasher": "Dishwasher",
    "balcony": "Outdoor space (balcony, courtyard, deck, garden or backyard)",
    "pool": "Swimming pool",
    "gym": "Building gym",
    "secure_parking": "Secure parking (garage/carport)",
    "furnished": "Furnished",
    "pet_friendly": "Pet friendly",
    "study": "Study, sunroom or other home-office space",
    "natural_light": "Light-filled / north-facing",
    "security_features": "Security features (intercom/alarm/etc)",
    "fly_screens": "Fly screens",
    "modern_kitchen": "Modern / renovated kitchen",
    "modern_bathroom": "Modern / renovated bathroom",
    "second_storey": "Two-storey / multi-level",
}

DETAIL_COLUMN_SPECS: dict[str, tuple[str, str]] = {
    **{col: (label, "boolean") for col, label in _AMENITY_DETAIL_LABELS.items()},
    "fits_two_desks_3rd_bedroom": ("Smallest bedroom fits two desks (WFH)", "boolean"),
    "lease_term_months": ("Lease term (months)", "number"),
    "available_from": ("Available from", "date"),
    "land_size_sqm": ("Land size (sqm)", "number"),
    "floor_size_sqm": ("Internal floor size (sqm)", "number"),
}

# Columns safe to render as a forced Sheets checkbox (sheets/publish.py):
# every listing gets a concrete 0/1 for these on first parse, so a blank
# cell becoming an unticked box loses nothing. Not true for
# fits_two_desks_3rd_bedroom, which starts genuinely unreviewed. A
# checkbox there would show every listing as a confirmed "no" before
# anyone's looked, so it stays plain text instead.
CHECKBOX_SAFE_COLUMNS = set(AMENITY_KEYWORDS)

# Sheet column header (the friendly label) -> underlying DB column name,
# for sheets/sync_back.py to map a "Listings - Detail" column back to
# where it's written. Labels must stay unique for this to round-trip.
LABEL_TO_COLUMN: dict[str, str] = {label: col for col, (label, _) in DETAIL_COLUMN_SPECS.items()}

assert set(_AMENITY_DETAIL_LABELS) == set(AMENITY_KEYWORDS), (
    "detail_labels.py's amenity labels have drifted from ingest/schema.py's AMENITY_KEYWORDS"
)
assert len(LABEL_TO_COLUMN) == len(DETAIL_COLUMN_SPECS), "detail_labels.py has duplicate labels"
