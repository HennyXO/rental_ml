"""Pull human-edited columns back from the shared Sheet into local state:
ratings + status from the "Listings" tab into the SQLite `ratings` table /
`listings.status`; per-listing feature corrections from the "Listings -
Detail" tab into their DB columns; and weights + hard filters from the
"Preferences" / "Hard filters" tabs into preferences/<name>.yaml. The
Sheet is the only place either person needs to set or adjust any of this
day to day, no yaml editing or direct DB access required.

Run manually whenever you want to pull in edits made in the Sheet, e.g.
before `python -m sheets.publish` so nothing gets clobbered:
    python -m sheets.sync_back
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import yaml

import config
from ingest.schema import get_connection
from score.fit_score import people
from sheets.client import open_sheet, read_dataframe
from sheets.detail_labels import DETAIL_COLUMN_SPECS, LABEL_TO_COLUMN
from sheets.hard_filter_labels import HARD_FILTER_SPECS, parse_value
from sheets.publish import PREFERRED_SUBURBS_LIST_ROW, SHEET_WEIGHT_SCALE

LISTINGS_TAB = "Listings"
LISTINGS_DETAIL_TAB = "Listings - Detail"
PREFERENCES_TAB = "Preferences"
HARD_FILTERS_TAB = "Hard filters"


def _as_float(value) -> float | None:
    if value in ("", None):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def sync_ratings_and_status() -> None:
    sheet = open_sheet()
    df = read_dataframe(sheet.worksheet(LISTINGS_TAB))
    if df.empty:
        print(f"'{LISTINGS_TAB}' tab is empty or missing -- nothing to sync.")
        return

    conn = get_connection(config.DB_PATH)
    names = people()
    now = datetime.now(timezone.utc).isoformat()
    rating_updates, status_updates = 0, 0

    for _, row in df.iterrows():
        listing_id = str(row.get("listing_id", "")).strip()
        if not listing_id:
            continue

        status = str(row.get("status", "")).strip()
        if status:
            conn.execute("UPDATE listings SET status = ? WHERE listing_id = ?", (status, listing_id))
            status_updates += 1

        for name in names:
            score = _as_float(row.get(f"{name}_rating"))
            if score is None:
                continue
            comment = str(row.get(f"{name}_comment", "")).strip() or None
            conn.execute(
                "INSERT OR REPLACE INTO ratings (listing_id, person, score, comment, rated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (listing_id, name, score, comment, now),
            )
            rating_updates += 1

    conn.commit()
    print(f"Synced {status_updates} status update(s) and {rating_updates} rating(s) from the Sheet.")


def sync_listing_details() -> None:
    """Pulls per-listing feature corrections from the "Listings - Detail"
    tab into their DB columns and into manual_overrides, which protects
    them from a later re-parse. A cell only counts as a correction if it
    differs from what publish.py last wrote there (detail_published), so
    an untouched cell never pins a stale keyword guess. Blank cell = leave
    the DB alone."""
    sheet = open_sheet()
    df = _read_tab_safely(sheet, LISTINGS_DETAIL_TAB)
    if df.empty:
        print(f"'{LISTINGS_DETAIL_TAB}' tab is empty or missing -- nothing to sync.")
        return

    conn = get_connection(config.DB_PATH)
    published = {
        (listing_id, col): value
        for listing_id, col, value in conn.execute("SELECT * FROM detail_published")
    }
    now = datetime.now(timezone.utc).isoformat()
    updates = 0
    issues: list[str] = []

    for _, row in df.iterrows():
        listing_id = str(row.get("listing_id", "")).strip()
        if not listing_id:
            continue
        for label, column in LABEL_TO_COLUMN.items():
            if label not in df.columns:
                continue
            raw = row.get(label)
            if raw in ("", None) or pd.isna(raw):
                continue
            _, value_type = DETAIL_COLUMN_SPECS[column]
            value = parse_value(raw, value_type)
            if value is None:
                issues.append(f"{listing_id}: couldn't read '{raw}' for '{label}' -- skipped")
                continue
            if value == published.get((listing_id, column)):
                continue
            conn.execute(f"UPDATE listings SET {column} = ? WHERE listing_id = ?", (value, listing_id))
            conn.execute(
                "INSERT OR REPLACE INTO manual_overrides VALUES (?, ?, ?, ?)", (listing_id, column, value, now)
            )
            updates += 1

    conn.commit()
    print(f"Synced {updates} listing detail correction(s) from the Sheet.")
    if issues:
        print(f"{len(issues)} detail value(s) needed attention:")
        for issue in issues:
            print(f"  - {issue}")


def _parse_sheet_weight(raw, feature: str, person: str, issues: list[str]) -> float | None:
    """Sheet's -5..+5 whole-number scale -> stored -1..1 weight (see
    SHEET_WEIGHT_SCALE in sheets/publish.py). Unparseable or out-of-range
    entries are clamped/skipped rather than silently dropped, noted in
    `issues` so sync_preferences() can report them instead."""
    value = _as_float(raw)
    if value is None:
        text = str(raw).strip()
        if text:
            issues.append(
                f"{person}: couldn't read '{text}' for '{feature}' (expected a whole number "
                f"from -{SHEET_WEIGHT_SCALE} to {SHEET_WEIGHT_SCALE}) -- skipped"
            )
        return None
    if abs(value) > SHEET_WEIGHT_SCALE:
        clamped = max(-SHEET_WEIGHT_SCALE, min(SHEET_WEIGHT_SCALE, value))
        issues.append(
            f"{person}: '{feature}' = {value:g} is outside -{SHEET_WEIGHT_SCALE}..{SHEET_WEIGHT_SCALE} "
            f"-- clamped to {clamped:g}"
        )
        value = clamped
    return value / SHEET_WEIGHT_SCALE


def _read_tab_safely(sheet, tab_name: str) -> pd.DataFrame:
    try:
        return read_dataframe(sheet.worksheet(tab_name))
    except Exception as exc:
        print(f"Couldn't read '{tab_name}' tab ({exc}) -- skipping.")
        return pd.DataFrame()


def sync_preferences() -> None:
    """Fully regenerates each person's preferences/<name>.yaml, both
    hard_filters and weights, from the Sheet. The Sheet is the source of
    truth once it's set up; hand-editing the yaml directly still works,
    but the next sync_back overwrites it."""
    sheet = open_sheet()
    prefs_df = _read_tab_safely(sheet, PREFERENCES_TAB)
    filters_df = _read_tab_safely(sheet, HARD_FILTERS_TAB)
    issues: list[str] = []

    for name in people():
        weights = {}
        preferred_suburbs = []
        weight_col = f"{name}_weight"
        if not prefs_df.empty and "feature" in prefs_df.columns and weight_col in prefs_df.columns:
            for _, row in prefs_df.iterrows():
                feature = row["feature"]
                if feature == PREFERRED_SUBURBS_LIST_ROW:
                    raw = str(row.get(weight_col, "")).strip()
                    preferred_suburbs = [s.strip() for s in raw.split(",") if s.strip()]
                    continue
                value = _parse_sheet_weight(row.get(weight_col), feature, name, issues)
                if value is not None:
                    weights[feature] = value

        hard_filters = {}
        value_col = f"{name}_value"
        if not filters_df.empty and "filter" in filters_df.columns and value_col in filters_df.columns:
            for _, row in filters_df.iterrows():
                spec = HARD_FILTER_SPECS.get(row["filter"])
                if not spec:
                    continue
                _, value_type = spec
                value = parse_value(row.get(value_col), value_type)
                if value is not None:
                    hard_filters[row["filter"]] = value

        path = config.PREFERENCES_DIR / f"{name}.yaml"
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                {"hard_filters": hard_filters, "preferred_suburbs": preferred_suburbs, "weights": weights},
                f, sort_keys=False,
            )
        print(f"Regenerated preferences/{name}.yaml from the Sheet "
              f"({len(hard_filters)} hard filter(s), {len(preferred_suburbs)} preferred suburb(s), "
              f"{len(weights)} weight(s)).")

    if issues:
        print(f"\n{len(issues)} preference weight(s) needed attention:")
        for issue in issues:
            print(f"  - {issue}")


def main() -> None:
    sync_ratings_and_status()
    sync_listing_details()
    sync_preferences()


if __name__ == "__main__":
    main()
