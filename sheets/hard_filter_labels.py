"""Curated, human-editable hard filters -- the Sheet-facing counterpart to
sheets/feature_labels.py. Each entry names the exact preferences/<name>.yaml
hard_filters key it maps to (see score/fit_score.py's max_/min_/allowed_/
*_required key convention) plus how to read/write it as a spreadsheet
cell. A blank cell always means "not set" (this filter doesn't apply) --
there's no separate way to represent an explicit False for a boolean,
since that behaves identically to unset.
"""
from __future__ import annotations

# key -> (plain-English description, value type: "number" | "boolean" | "list")
HARD_FILTER_SPECS: dict[str, tuple[str, str]] = {
    "max_weekly_rent_aud": ("Maximum weekly rent ($) you're willing to pay", "number"),
    "min_bedrooms": ("Minimum number of bedrooms required", "number"),
    "max_commute_transit_minutes": (
        "Maximum public transport time to the office (minutes) you'll accept", "number"),
    "max_commute_driving_minutes": (
        "Maximum driving time to the office (minutes) you'll accept", "number"),
    "allowed_suburbs": (
        "Suburbs you're willing to live in, comma-separated (blank = any suburb)", "list"),
    "pet_friendly_required": ("Only show pet-friendly listings (write TRUE, or leave blank)", "boolean"),
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
    return None


def render_value(value, value_type: str) -> str:
    """python value from an existing hard_filters dict -> sheet cell text."""
    if value is None:
        return ""
    if value_type == "list":
        return ", ".join(value)
    if value_type == "boolean":
        return "TRUE" if value else ""
    return str(value)
