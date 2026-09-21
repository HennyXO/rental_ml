"""Turn the raw listings DataFrame into a model-ready feature matrix."""
from __future__ import annotations

import pandas as pd

from ingest.schema import AMENITY_KEYWORDS, STATION_MODES

NUMERIC_COLUMNS = [
    "bedrooms", "bathrooms", "parking_spaces",
    "land_size_sqm", "floor_size_sqm",
    "commute_driving_minutes", "commute_transit_minutes", "straight_line_km",
] + [f"nearest_{mode}_station_km" for mode in STATION_MODES] \
  + [f"nearest_{mode}_station_walk_minutes" for mode in STATION_MODES]
AMENITY_COLUMNS = list(AMENITY_KEYWORDS)
CATEGORICAL_COLUMNS = ["property_type", "suburb"]
TARGET_COLUMN = "weekly_rent_aud"

# Suburbs seen fewer than this many times get bucketed into "other" so a
# one-hot column isn't created for a suburb with a single listing.
MIN_SUBURB_COUNT = 3


def build_feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Returns (X, y, listing_ids) with rows lacking a target price dropped."""
    df = df.copy()
    df = df.dropna(subset=[TARGET_COLUMN])

    suburb_counts = df["suburb"].value_counts()
    common_suburbs = set(suburb_counts[suburb_counts >= MIN_SUBURB_COUNT].index)
    df["suburb_bucketed"] = df["suburb"].where(df["suburb"].isin(common_suburbs), "other")

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # missing-ness itself is informative for the size columns (rentals
    # frequently omit floor size), so flag it before imputing
    X_missing_flags = pd.DataFrame({
        f"{col}_missing": df[col].isna().astype(int)
        for col in ("land_size_sqm", "floor_size_sqm")
    })

    # median-impute, then fall back to 0 for any column that is NaN in
    # every remaining row (e.g. floor_size_sqm is often missing from every
    # rental listing, so its median is itself NaN)
    X_numeric = df[NUMERIC_COLUMNS].fillna(df[NUMERIC_COLUMNS].median()).fillna(0)
    X_amenities = df[AMENITY_COLUMNS].fillna(0).astype(int)
    X_categorical = pd.get_dummies(
        df[["property_type", "suburb_bucketed"]].fillna("unknown"),
        prefix=["type", "suburb"],
    )

    X = pd.concat([X_numeric, X_missing_flags, X_amenities, X_categorical], axis=1)
    y = df[TARGET_COLUMN]
    listing_ids = df["listing_id"]
    return X, y, listing_ids
