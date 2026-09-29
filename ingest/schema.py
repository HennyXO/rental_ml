"""The feature catalogue, defined once as SQLite DDL.

parse_listing.py, ingest.py, and model/features.py all read the column
lists from here rather than repeating field names.
"""
import sqlite3

# Boolean amenity columns -> regex patterns (matched case-insensitively,
# anchored to a word start, so "furnished" can't match "unfurnished" and
# "gym" can't match "gyms nearby") used to detect them in a listing's
# description and "Features" bullets. Extend this as real listings reveal
# wording we haven't seen yet.
_UPDATED = r"(?:modern|renovated|contemporary|updated|designer|new|stylish|refurbished)\s+(?:[\w-]+\s+){0,2}"
AMENITY_KEYWORDS = {
    "air_conditioning": [r"air[ -]?con", r"a/c", r"ducted air", r"reverse cycle", r"split[ -]system"],
    "built_in_wardrobes": [r"(?:built[ -]?in|inbuilt|walk[ -]in) (?:ward)?robe", r"birs?\b"],
    "dishwasher": [r"dishwasher"],
    # "terrace" alone would match the house style ("Victorian terrace"), so
    # only qualified forms count as outdoor space.
    "balcony": [r"balcon", r"courtyard", r"(?:private|rooftop|rear|sun|alfresco|entertainer'?s) terrace",
                r"back ?yard", r"rear yard", r"(?:rear|private|front) garden", r"garden beds", r"lawn",
                r"deck", r"alfresco", r"patio", r"outdoor (?:area|entertaining|space|dining)"],
    "pool": [r"swimming pool", r"pool\b"],
    "gym": [r"gymnasium", r"(?:on-?site|communal|residents'?|building|private|in-house) gym",
            r"fitness (?:centre|center|room)"],
    "secure_parking": [r"secure (?:parking|car ?space)", r"garage", r"carport", r"lock[ -]up"],
    "furnished": [r"furnished"],
    "pet_friendly": [r"pet[ -]friendly", r"pets (?:allowed|considered|welcome|negotiable)"],
    "study": [r"study", r"sun ?room", r"home office", r"second living", r"working from home"],
    "natural_light": [r"north(?:[ -]east)?[ -]facing", r"sun[ -]drenched", r"light[ -]filled", r"sunny",
                      r"natural light", r"north(?:erly)? aspect", r"north to (?:the )?rear"],
    "security_features": [r"intercom", r"secure building", r"alarm system", r"security system", r"video entry"],
    "fly_screens": [r"fly[ -]?screen"],
    "modern_kitchen": [_UPDATED + r"kitchen"],
    "modern_bathroom": [_UPDATED + r"(?:bathroom|ensuite)"],
    "second_storey": [r"(?:two|three|double|multi|split|tri|2|3)[ -]?(?:storey|story|level)",
                      r"(?:two|three|2|3)\s+(?:[\w-]+\s+){0,2}levels", r"upstairs", r"downstairs"],
}

# Columns beyond the amenity booleans above.
CORE_COLUMNS = [
    ("listing_id", "TEXT PRIMARY KEY"),
    ("url", "TEXT"),
    ("address", "TEXT"),
    ("suburb", "TEXT"),
    ("postcode", "TEXT"),
    ("lat", "REAL"),
    ("lon", "REAL"),
    ("property_type", "TEXT"),
    ("bedrooms", "INTEGER"),
    ("bathrooms", "INTEGER"),
    ("parking_spaces", "INTEGER"),
    ("land_size_sqm", "REAL"),
    ("floor_size_sqm", "REAL"),
    ("features_raw", "TEXT"),       # JSON list of every raw feature string found, so nothing is lost
    ("description", "TEXT"),
    ("weekly_rent_aud", "REAL"),
    ("lease_term_months", "INTEGER"),  # only when the listing states one
    ("available_from", "TEXT"),        # ISO date; "Available now" = the date it was saved
    ("commute_driving_minutes", "REAL"),
    ("commute_transit_minutes", "REAL"),
    ("straight_line_km", "REAL"),
    ("date_captured", "TEXT"),
    ("source_file", "TEXT"),
    # Decision-tracking, set by hand as things progress (new/inspecting/
    # applied/rejected/...). The triage report suggests, humans decide.
    ("status", "TEXT"),
    # Manual/judgment fields, not auto-extracted, fill in by hand after
    # reviewing the listing's floorplan (see "Listing preferences" in
    # CLAUDE.md). NULL until reviewed.
    ("fits_two_desks_3rd_bedroom", "INTEGER"),
    ("manual_notes", "TEXT"),
]

AMENITY_COLUMNS = [(name, "INTEGER") for name in AMENITY_KEYWORDS]

# Points of interest we compute nearest-distance/walk-time for. The three
# transit categories come from TfNSW's GTFS feed (see
# ingest/build_transit_stations.py -> data/transit_stations.csv); the rest
# come from OpenStreetMap's Overpass API (see ingest/build_poi.py ->
# data/poi.csv). Category names already include "_station" where that reads
# better, so the column-generation pattern below stays uniform for all of
# them; see ingest/poi.py for how these get populated.
POI_CATEGORIES = ["train_station", "metro_station", "light_rail_station", "school", "supermarket", "park", "beach"]
POI_COLUMNS = [
    (f"nearest_{cat}", "TEXT") for cat in POI_CATEGORIES
] + [
    (f"nearest_{cat}_km", "REAL") for cat in POI_CATEGORIES
] + [
    (f"nearest_{cat}_walk_minutes", "REAL") for cat in POI_CATEGORIES
]

ALL_COLUMNS = CORE_COLUMNS + AMENITY_COLUMNS + POI_COLUMNS
ALL_COLUMN_NAMES = [name for name, _ in ALL_COLUMNS]

LISTINGS_DDL = "CREATE TABLE IF NOT EXISTS listings (\n    " + ",\n    ".join(
    f"{name} {sqltype}" for name, sqltype in ALL_COLUMNS
) + "\n)"

COMMUTE_CACHE_DDL = "CREATE TABLE IF NOT EXISTS commute_cache (\n    " + ",\n    ".join(
    [
        "address TEXT PRIMARY KEY",
        "lat REAL",
        "lon REAL",
        "driving_minutes REAL",
        "transit_minutes REAL",
    ] + [f"{name} {sqltype}" for name, sqltype in POI_COLUMNS] + [
        "computed_at TEXT",
    ]
) + "\n)"

# Human corrections from the Sheet's "Listings - Detail" tab
# (sheets/sync_back.py), re-applied over every re-parse (ingest/ingest.py),
# so a correction always beats a keyword guess but an uncorrected guess
# still improves when the keywords do.
MANUAL_OVERRIDES_DDL = """
CREATE TABLE IF NOT EXISTS manual_overrides (
    listing_id TEXT NOT NULL,
    column_name TEXT NOT NULL,
    value,
    set_at TEXT,
    PRIMARY KEY (listing_id, column_name)
)
"""

# What sheets/publish.py last wrote to the "Listings - Detail" tab, so
# sync_back.py can tell a human edit (Sheet differs from this) apart from
# the DB having changed underneath an unedited cell (e.g. a re-parse).
DETAIL_PUBLISHED_DDL = """
CREATE TABLE IF NOT EXISTS detail_published (
    listing_id TEXT NOT NULL,
    column_name TEXT NOT NULL,
    value,
    PRIMARY KEY (listing_id, column_name)
)
"""

# One row per (listing, person) rating. Kept separate from `listings` so
# objective feature data stays apart from subjective judgment, and it
# generalizes if a third rater ever joins the household.
RATINGS_DDL = """
CREATE TABLE IF NOT EXISTS ratings (
    listing_id TEXT NOT NULL,
    person TEXT NOT NULL,
    score REAL,
    comment TEXT,
    rated_at TEXT,
    PRIMARY KEY (listing_id, person)
)
"""


def _migrate_columns(conn: sqlite3.Connection) -> None:
    """CREATE TABLE IF NOT EXISTS only helps a table that doesn't exist
    yet; a schema change (like adding a new amenity) needs this to reach
    a `listings` table an earlier session already created. Additive only,
    never drops or alters an existing column."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    for name, sqltype in ALL_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE listings ADD COLUMN {name} {sqltype}")


def get_connection(db_path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(LISTINGS_DDL)
    conn.execute(COMMUTE_CACHE_DDL)
    conn.execute(RATINGS_DDL)
    conn.execute(MANUAL_OVERRIDES_DDL)
    conn.execute(DETAIL_PUBLISHED_DDL)
    _migrate_columns(conn)
    conn.commit()
    return conn
