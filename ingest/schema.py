"""The feature catalogue, defined once as SQLite DDL.

parse_listing.py, ingest.py, and model/features.py all read the column
lists from here rather than repeating field names.
"""
import sqlite3

# Boolean amenity columns -> keyword substrings (lowercase) used to detect
# them among a listing's free-text "Features" bullet list. Extend this as
# real listings reveal wording we haven't seen yet.
AMENITY_KEYWORDS = {
    "air_conditioning": ["air conditioning", "air con", "a/c", "ducted air", "reverse cycle"],
    "built_in_wardrobes": ["built-in wardrobe", "built in wardrobe", "builtin wardrobe", "bir"],
    "dishwasher": ["dishwasher"],
    "balcony": ["balcony", "courtyard", "terrace"],
    "pool": ["swimming pool", "pool"],
    "gym": ["gym", "fitness"],
    "secure_parking": ["secure parking", "garage", "carport", "remote garage"],
    "furnished": ["furnished"],
    "pet_friendly": ["pet friendly", "pets allowed", "pets considered"],
    "study": ["study", "sunroom", "sun room", "home office", "second living"],
    "natural_light": ["north facing", "north-facing", "north east facing", "north-east facing",
                       "sun-drenched", "sun drenched", "light-filled", "light filled", "sunny"],
    "security_features": ["intercom", "secure building", "alarm system", "security system", "video entry"],
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
    ("commute_driving_minutes", "REAL"),
    ("commute_transit_minutes", "REAL"),
    ("straight_line_km", "REAL"),
    ("date_captured", "TEXT"),
    ("source_file", "TEXT"),
    # Decision-tracking, set by hand as things progress (new/inspecting/
    # applied/rejected/...). The triage report suggests, humans decide.
    ("status", "TEXT"),
    # Manual/judgment fields -- not auto-extracted, fill in by hand after
    # reviewing the listing's floorplan (see "Listing preferences" in
    # CLAUDE.md). NULL until reviewed.
    ("fits_two_desks_3rd_bedroom", "INTEGER"),
    ("manual_notes", "TEXT"),
]

# Columns a human fills in by hand (e.g. after reviewing a floorplan, or via
# the shared Sheet) that re-ingesting/re-parsing a listing must never
# overwrite.
MANUAL_COLUMN_NAMES = ["status", "fits_two_desks_3rd_bedroom", "manual_notes"]

AMENITY_COLUMNS = [(name, "INTEGER") for name in AMENITY_KEYWORDS]

# Points of interest we compute nearest-distance/walk-time for. The three
# transit categories come from TfNSW's GTFS feed (see
# ingest/build_transit_stations.py -> data/transit_stations.csv); the rest
# come from OpenStreetMap's Overpass API (see ingest/build_poi.py ->
# data/poi.csv). Category names already include "_station" where that reads
# better, so the column-generation pattern below stays uniform for all of
# them -- see ingest/poi.py for how these get populated.
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


def get_connection(db_path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(LISTINGS_DDL)
    conn.execute(COMMUTE_CACHE_DDL)
    conn.execute(RATINGS_DDL)
    conn.commit()
    return conn
