"""Plain-English labels for the features people actually weight, shared by
the Preferences tab (sheets/publish.py) and the Read Me tab
(sheets/readme.py) so the two never drift apart. Deliberately a curated
subset of the full feature catalogue in ingest/schema.py: only one of
nearest_X_km / nearest_X_walk_minutes is shown, for example, since a
non-technical rater doesn't need both, even though fit_score.py itself
can weight either. If you want to weight something not listed here, you
can still add it directly to your preferences/<name>.yaml by hand; this
list only controls what appears in the Sheet.

Every numeric feature is tagged [lower = better] or [higher = better],
since score/fit_score.py rewards a HIGHER column value for a positive
weight: intuitive for bedrooms, backwards for rent or commute time,
where a positive weight would reward more of it. sheets/readme.py's
Preferences section explains this in full.
"""
from __future__ import annotations

FEATURE_LABELS: dict[str, str] = {
    "weekly_rent_aud": "[lower = better] Weekly rent ($). Weight this NEGATIVE if rent matters to you; "
                       "a positive number would reward HIGHER rent, which is probably not what you want",
    "preferred_suburbs": "How much it matters that the suburb is one of your preferred suburbs "
                          "(see the 'preferred_suburbs_list' row for which ones)",
    "bedrooms": "[higher = better] Number of bedrooms",
    "bathrooms": "[higher = better] Number of bathrooms",
    "parking_spaces": "[higher = better] Number of car spaces",
    "land_size_sqm": "[higher = better] Land size (sqm), often blank for rentals",
    "floor_size_sqm": "[higher = better] Internal floor size (sqm), often blank for rentals",
    "fits_two_desks_3rd_bedroom": "Smallest bedroom fits two desks as a WFH office (set per-listing in the "
                                   "'Listings - Detail' tab, not every listing reviewed yet)",
    "commute_driving_minutes": "[lower = better] Driving time to the office (minutes). Weight this NEGATIVE "
                                "if a short drive matters; positive would reward a LONGER drive",
    "commute_transit_minutes": "[lower = better] Public transport time to the office (minutes). Weight this "
                                "NEGATIVE if a short commute matters; positive would reward a LONGER commute",
    "nearest_train_station_walk_minutes": "[lower = better] Walk to the nearest train station (minutes). "
                                           "Weight this NEGATIVE if being close matters; positive would reward being FURTHER away",
    "nearest_metro_station_walk_minutes": "[lower = better] Walk to the nearest metro station (minutes). "
                                           "Weight this NEGATIVE if being close matters; positive would reward being FURTHER away",
    "nearest_light_rail_station_walk_minutes": "[lower = better] Walk to the nearest light rail stop (minutes). "
                                                "Weight this NEGATIVE if being close matters; positive would reward being FURTHER away",
    "nearest_school_walk_minutes": "[lower = better] Walk to the nearest school (minutes). Weight this "
                                    "NEGATIVE if being close matters; positive would reward being FURTHER away",
    "nearest_supermarket_walk_minutes": "[lower = better] Walk to the nearest supermarket (minutes). Weight "
                                         "this NEGATIVE if being close matters; positive would reward being FURTHER away",
    "nearest_park_walk_minutes": "[lower = better] Walk to the nearest park (minutes). Weight this NEGATIVE "
                                  "if being close matters; positive would reward being FURTHER away",
    "nearest_beach_walk_minutes": "[lower = better] Walk to the nearest beach (minutes), not really relevant "
                                   "inner-west, fine to leave blank. If you do weight it: NEGATIVE, since positive "
                                   "would reward being FURTHER away",
    "air_conditioning": "Has air conditioning",
    "built_in_wardrobes": "Has built-in wardrobes",
    "dishwasher": "Has a dishwasher",
    "balcony": "Has outdoor space: a balcony, courtyard, deck, garden or backyard",
    "pool": "Has a swimming pool",
    "gym": "Building has a gym",
    "secure_parking": "Has secure parking (garage/carport)",
    "furnished": "Comes furnished. Some people want the OPPOSITE of this if they own their own furniture; "
                 "weight it negative in that case",
    "pet_friendly": "Pet friendly, a soft preference boost. If this is a genuine dealbreaker, use "
                     "'pet_friendly_required' in the Hard filters tab instead",
    "study": "Has a study, sunroom or other home-office-able space",
    "natural_light": "Listing describes it as light-filled / north-facing / sun-drenched",
    "security_features": "Has security features (intercom, secure building, alarm)",
    "fly_screens": "Has fly screens",
    "modern_kitchen": "Kitchen reads as modern/renovated",
    "modern_bathroom": "Bathroom reads as modern/renovated",
    "second_storey": "Home is two-storey / multi-level (has an upstairs)",
}
