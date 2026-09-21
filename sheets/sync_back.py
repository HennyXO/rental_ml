"""Pull human-edited columns back from the shared Sheet into local state:
ratings + status from the "Listings" tab into the SQLite `ratings` table /
`listings.status`, and weights from the "Preferences" tab into
preferences/<name>.yaml (hard_filters are left alone -- only the weights
section gets regenerated from the Sheet).

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

LISTINGS_TAB = "Listings"
PREFERENCES_TAB = "Preferences"


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


def sync_preferences() -> None:
    sheet = open_sheet()
    try:
        df = read_dataframe(sheet.worksheet(PREFERENCES_TAB))
    except Exception as exc:
        print(f"Couldn't read '{PREFERENCES_TAB}' tab ({exc}) -- skipping preference sync.")
        return
    if df.empty or "feature" not in df.columns:
        print(f"'{PREFERENCES_TAB}' tab is empty -- skipping preference sync.")
        return

    for name in people():
        weight_col = f"{name}_weight"
        if weight_col not in df.columns:
            continue

        weights = {}
        for _, row in df.iterrows():
            value = _as_float(row.get(weight_col))
            if value is not None:
                weights[row["feature"]] = value

        path = config.PREFERENCES_DIR / f"{name}.yaml"
        existing = {}
        if path.exists():
            with path.open(encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        existing["hard_filters"] = existing.get("hard_filters", {})
        existing["weights"] = weights
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(existing, f, sort_keys=False)
        print(f"Regenerated preferences/{name}.yaml weights from the Sheet ({len(weights)} weight(s)).")


def main() -> None:
    sync_ratings_and_status()
    sync_preferences()


if __name__ == "__main__":
    main()
