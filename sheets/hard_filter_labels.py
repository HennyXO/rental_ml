"""Curated, human-editable hard filters, the Sheet-facing counterpart to
sheets/feature_labels.py. Each entry names the exact preferences/<name>.yaml
hard_filters key it maps to (see score/fit_score.py's max_/min_/allowed_/
excluded_ key convention; the part after the prefix must match a real
column name exactly, e.g. "excluded_suburb" singular, since the DB column
is "suburb") plus how to read/write it as a spreadsheet cell.

A blank cell always means "not set." There's no separate way to represent
an explicit False for a boolean, since that behaves identically to unset
in score/fit_score.py's hard-filter check. So the Sheets-native checkbox
sheets/publish.py adds can freely read back an explicit False once
ticked and un-ticked, with no change in meaning.
"""
from __future__ import annotations

import pandas as pd

# key -> (plain-English description, value type: "number" | "boolean" | "list" | "date")
HARD_FILTER_SPECS: dict[str, tuple[str, str]] = {
    "max_weekly_rent_aud": ("Maximum weekly rent ($) you're willing to pay", "number"),
    "min_bedrooms": ("Minimum number of bedrooms required", "number"),
    "max_commute_transit_minutes": (
        "Maximum public transport time to the office (minutes) you'll accept", "number"),
    "max_commute_driving_minutes": (
        "Maximum driving time to the office (minutes) you'll accept", "number"),
    "min_lease_term_months": (
        "Shortest lease you'd accept (months), e.g. 12 rules out '6 month lease only'. "
        "Listings that don't state a lease term are kept", "number"),
    "excluded_suburb": (
        "Suburbs you'd never live in, a genuine dealbreaker, comma-separated (blank = none)", "list"),
    "pet_friendly_required": ("Only show pet-friendly listings (tick the checkbox, otherwise leave it unticked)", "boolean"),
}


def parse_value(raw, value_type: str):
    """Sheet cell -> python value for preferences/<name>.yaml. None means
    "leave this filter out entirely" (not the same as an explicit False)."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if value_type == "number":
        try:
            return float(text)
        except ValueError:
            return None
    if value_type == "boolean":
        return text.lower() in ("true", "yes", "1")
    if value_type == "list":
        items = [s.strip() for s in text.split(",") if s.strip()]
        return items or None
    if value_type == "date":
        # ISO as published, or however Sheets displays a date someone typed
        parsed = pd.to_datetime(text, dayfirst="-" not in text, errors="coerce")
        return None if pd.isna(parsed) else parsed.date().isoformat()
    return None


def render_value(value, value_type: str):
    """python value from an existing hard_filters dict (or a raw DB value)
    -> a Sheet cell value. Returns a real bool/float, not a stringified
    "TRUE"/"3": write_dataframe (sheets/client.py) writes values as-is
    with no parsing, so a string like "TRUE" would land as forced text (a
    leading apostrophe in the Sheet) and fail sheets/publish.py's
    validation rules, which check against a real boolean/number type."""
    if value is None:
        return ""
    if value_type == "list":
        return ", ".join(value)
    if value_type == "boolean":
        return bool(value)
    if value_type == "number":
        return float(value)
    return str(value)
