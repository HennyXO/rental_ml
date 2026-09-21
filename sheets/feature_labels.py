"""Plain-English labels for the features people actually weight, shared by
the Preferences tab (sheets/publish.py) and the Read Me tab
(sheets/readme.py) so the two never drift apart. Deliberately a curated
subset of the full feature catalogue in ingest/schema.py -- e.g. only one
of nearest_X_km / nearest_X_walk_minutes is shown, since a non-technical
rater doesn't need both, even though fit_score.py itself can weight
either. If you want to weight something not listed here, you can still
add it directly to your preferences/<name>.yaml by hand -- this list only
controls what appears in the Sheet.
"""
from __future__ import annotations

FEATURE_LABELS: dict[str, str] = {
    "weekly_rent_aud": "Weekly rent ($)",
    "bedrooms": "Number of bedrooms",
    "bathrooms": "Number of bathrooms",
    "parking_spaces": "Number of car spaces",
    "land_size_sqm": "Land size (sqm) -- often blank for rentals",
    "floor_size_sqm": "Internal floor size (sqm) -- often blank for rentals",
    "fits_two_desks_3rd_bedroom": "Smallest bedroom fits two desks as a WFH office (filled in by hand, not every listing reviewed yet)",
    "commute_driving_minutes": "Driving time to the office (minutes)",
    "commute_transit_minutes": "Public transport time to the office (minutes)",
    "nearest_train_station_walk_minutes": "Walk to the nearest train station (minutes)",
    "nearest_metro_station_walk_minutes": "Walk to the nearest metro station (minutes)",
    "nearest_light_rail_station_walk_minutes": "Walk to the nearest light rail stop (minutes)",
    "nearest_school_walk_minutes": "Walk to the nearest school (minutes)",
    "nearest_supermarket_walk_minutes": "Walk to the nearest supermarket (minutes)",
    "nearest_park_walk_minutes": "Walk to the nearest park (minutes)",
    "nearest_beach_walk_minutes": "Walk to the nearest beach (minutes) -- not really relevant inner-west, fine to leave blank",
    "air_conditioning": "Has air conditioning",
    "built_in_wardrobes": "Has built-in wardrobes",
    "dishwasher": "Has a dishwasher",
    "balcony": "Has a balcony, courtyard or terrace",
    "pool": "Has a swimming pool",
    "gym": "Building has a gym",
    "secure_parking": "Has secure parking (garage/carport)",
    "furnished": "Comes furnished",
    "pet_friendly": "Pet friendly",
    "study": "Has a study, sunroom or other home-office-able space",
    "natural_light": "Listing describes it as light-filled / north-facing / sun-drenched",
    "security_features": "Has security features (intercom, secure building, alarm)",
}
