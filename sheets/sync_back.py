"""Pull human-edited columns back from the shared Sheet into local state:
ratings + status from the "Listings" tab into the SQLite `ratings` table /
`listings.status`, and weights + hard filters from the "Preferences" /
"Hard filters" tabs into preferences/<name>.yaml -- the Sheet is the only
place either person needs to set or adjust their own preferences day to
day, no yaml editing required.

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
from sheets.hard_filter_labels import HARD_FILTER_SPECS, parse_value

LISTINGS_TAB = "Listings"
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


def _read_tab_safely(sheet, tab_name: str) -> pd.DataFrame:
    try:
        return read_dataframe(sheet.worksheet(tab_name))
    except Exception as exc:
        print(f"Couldn't read '{tab_name}' tab ({exc}) -- skipping.")
        return pd.DataFrame()


def sync_preferences() -> None:
    """Fully regenerates each person's preferences/<name>.yaml -- both
    hard_filters and weights -- from the Sheet. The Sheet is the source of
    truth once it's set up; hand-editing the yaml directly still works,
    but the next sync_back overwrites it."""
    sheet = open_sheet()
    prefs_df = _read_tab_safely(sheet, PREFERENCES_TAB)
    filters_df = _read_tab_safely(sheet, HARD_FILTERS_TAB)

    for name in people():
        weights = {}
        weight_col = f"{name}_weight"
        if not prefs_df.empty and "feature" in prefs_df.columns and weight_col in prefs_df.columns:
            for _, row in prefs_df.iterrows():
                value = _as_float(row.get(weight_col))
                if value is not None:
                    weights[row["feature"]] = value

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
            yaml.safe_dump({"hard_filters": hard_filters, "weights": weights}, f, sort_keys=False)
        print(f"Regenerated preferences/{name}.yaml from the Sheet "
              f"({len(hard_filters)} hard filter(s), {len(weights)} weight(s)).")


def main() -> None:
    sync_ratings_and_status()
    sync_preferences()


if __name__ == "__main__":
    main()
