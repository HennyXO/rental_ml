"""Push the current triage report (listings + fit scores + ratings/status)
to a shared Google Sheet, the read/browse surface for the household on
phone or laptop, no git/Python needed to just look. Also (re)writes
"Preferences" (feature weights) and "Hard filters" (budget/bedrooms/
suburbs/etc) tabs, together the only place either person needs to set
or adjust their own preferences day to day, no yaml editing required.

Run manually whenever you want the Sheet refreshed:
    python -m sheets.publish

main() runs sync_back first automatically, since every tab here is a full
overwrite. Publishing without syncing first would silently destroy any
Sheet edits nobody's pulled in yet. That still can't catch a genuine live
collision: someone actively typing into the Sheet at the exact moment
this runs can still lose a keystroke, since there's no locking or
real-time merge. Best not to run this while anyone's actively editing.
"""
from __future__ import annotations

import pandas as pd
from gspread.utils import ValidationConditionType, rowcol_to_a1

import config
from ingest.schema import get_connection
from model.train import load_listings
from report.triage import build_report
from score.fit_score import load_preferences, people
from sheets.client import ensure_worksheet, open_sheet, write_dataframe
from sheets.detail_labels import CHECKBOX_SAFE_COLUMNS, DETAIL_COLUMN_SPECS
from sheets.feature_labels import FEATURE_LABELS
from sheets.hard_filter_labels import HARD_FILTER_SPECS, parse_value, render_value
from sheets.readme import README_TEXT

LISTINGS_TAB = "Listings"
LISTINGS_DETAIL_TAB = "Listings - Detail"
PREFERENCES_TAB = "Preferences"
HARD_FILTERS_TAB = "Hard filters"
README_TAB = "Read me"


PREFERRED_SUBURBS_LIST_ROW = "preferred_suburbs_list"

# The Sheet shows a friendlier -5..+5 whole-number scale than the -1..1
# stored in preferences/<name>.yaml (see score/fit_score.py), easier to
# type and reason about than a decimal. sheets/sync_back.py converts back.
SHEET_WEIGHT_SCALE = 5


def _weight_to_sheet_scale(weight):
    """-1..1 stored weight -> a real integer on the Sheet's -5..+5 scale
    (see render_value's docstring for why it must be a real number, not a
    stringified one)."""
    if weight == "" or weight is None:
        return ""
    return round(float(weight) * SHEET_WEIGHT_SCALE)


def _preferences_rows() -> pd.DataFrame:
    """One row per weight-able feature (see sheets/feature_labels.py for
    which ones and why), with each person's current weight (blank if they
    haven't set one): what you fill in/adjust in the Sheet, which
    sheets/sync_back.py then reads back into their yaml. One row is special:
    PREFERRED_SUBURBS_LIST_ROW holds actual suburb names (comma-separated),
    not a numeric weight. It's what the "preferred_suburbs" weight row
    scores against."""
    names = people()
    prefs_by_person = {name: load_preferences(name) for name in names}

    rows = []
    suburb_row = {"feature": PREFERRED_SUBURBS_LIST_ROW,
                  "what_this_means": "Your preferred suburbs, comma-separated (not a number; "
                                      "see the 'preferred_suburbs' row below for how much this matters)"}
    for name in names:
        suburb_row[f"{name}_weight"] = ", ".join(prefs_by_person[name]["preferred_suburbs"])
    rows.append(suburb_row)

    for feature, description in FEATURE_LABELS.items():
        row = {"feature": feature, "what_this_means": description}
        for name in names:
            row[f"{name}_weight"] = _weight_to_sheet_scale(prefs_by_person[name]["weights"].get(feature, ""))
        rows.append(row)
    return pd.DataFrame(rows)


def _hard_filter_rows() -> pd.DataFrame:
    """One row per known hard filter (see sheets/hard_filter_labels.py),
    with each person's current value (blank = not set). sync_back.py reads
    this back and replaces each person's hard_filters entirely, same
    pattern as weights."""
    names = people()
    filters_by_person = {name: load_preferences(name)["hard_filters"] for name in names}

    rows = []
    for key, (description, value_type) in HARD_FILTER_SPECS.items():
        row = {"filter": key, "what_this_means": description}
        for name in names:
            row[f"{name}_value"] = render_value(filters_by_person[name].get(key), value_type)
        rows.append(row)
    return pd.DataFrame(rows)


def _listing_detail_rows() -> pd.DataFrame:
    """One row per listing, one column per feature in
    sheets/detail_labels.py's DETAIL_COLUMN_SPECS. Lets you correct
    anything the text-keyword scan got wrong or simply couldn't tell (only
    visible in photos, or noticed at an actual inspection). sync_back.py
    saves a correction as a manual override, so a later re-parse can't
    reset it. Columns are labelled (not raw column names) for
    readability; sync_back.py maps back via LABEL_TO_COLUMN."""
    df = load_listings()
    rows = []
    for _, listing in df.iterrows():
        row = {"listing_id": listing["listing_id"], "address": listing["address"]}
        for col, (label, value_type) in DETAIL_COLUMN_SPECS.items():
            raw = listing.get(col)
            value = None if pd.isna(raw) else raw
            row[label] = render_value(value, value_type)
        rows.append(row)
    return pd.DataFrame(rows)


def _record_detail_published(detail_df: pd.DataFrame) -> None:
    """Snapshot what the Detail tab now shows, parsed the same way
    sync_back.py will read it back, so only cells a human changes after
    this count as corrections (see ingest/schema.py's DETAIL_PUBLISHED_DDL)."""
    rows = [
        (row["listing_id"], col, parse_value(row[label], value_type))
        for _, row in detail_df.iterrows()
        for col, (label, value_type) in DETAIL_COLUMN_SPECS.items()
    ]
    conn = get_connection(config.DB_PATH)
    conn.execute("DELETE FROM detail_published")
    conn.executemany("INSERT INTO detail_published VALUES (?, ?, ?)", [r for r in rows if r[2] is not None])
    conn.commit()


def _readme_rows() -> pd.DataFrame:
    return pd.DataFrame({"Read Me": README_TEXT.strip("\n").split("\n")})


def _apply_weight_validation(worksheet, prefs_df: pd.DataFrame) -> None:
    """Sheets-native number-range check on each person's weight column, so
    a mistyped value is flagged at entry time instead of only being caught
    (and silently clamped) later by sheets/sync_back.py. Skips the
    preferred_suburbs_list row, that one's free text, not a weight."""
    weight_rows = [
        i for i, feature in enumerate(prefs_df["feature"], start=2)
        if feature != PREFERRED_SUBURBS_LIST_ROW
    ]
    if not weight_rows:
        return
    first_row, last_row = min(weight_rows), max(weight_rows)
    for name in people():
        col = prefs_df.columns.get_loc(f"{name}_weight") + 1
        cell_range = f"{rowcol_to_a1(first_row, col)}:{rowcol_to_a1(last_row, col)}"
        worksheet.add_validation(
            cell_range, ValidationConditionType.number_between,
            [str(-SHEET_WEIGHT_SCALE), str(SHEET_WEIGHT_SCALE)],
            inputMessage=f"Whole number from -{SHEET_WEIGHT_SCALE} to {SHEET_WEIGHT_SCALE} "
                         f"(0 or blank = don't care).",
        )


def _apply_hard_filter_validation(worksheet, filters_df: pd.DataFrame) -> None:
    """Sheets-native checkbox on boolean hard filters (currently just
    pet_friendly_required), so it's pick-TRUE-or-leave-blank instead of a
    free-text cell that has to be typed exactly right."""
    boolean_rows = [
        i for i, key in enumerate(filters_df["filter"], start=2)
        if HARD_FILTER_SPECS.get(key, (None, None))[1] == "boolean"
    ]
    for row in boolean_rows:
        for name in people():
            col = filters_df.columns.get_loc(f"{name}_value") + 1
            worksheet.add_validation(
                rowcol_to_a1(row, col), ValidationConditionType.boolean, [],
                showCustomUi=True,
            )


def _apply_detail_validation(worksheet, detail_df: pd.DataFrame) -> None:
    """Sheets-native checkbox on every amenity column that's safe to force
    into a checkbox (see CHECKBOX_SAFE_COLUMNS). Everything else
    (fits_two_desks_3rd_bedroom, the size columns) stays plain text so an
    unreviewed listing doesn't get coerced into looking like a confirmed
    'no'."""
    if detail_df.empty:
        return
    last_row = len(detail_df) + 1
    for col, (label, value_type) in DETAIL_COLUMN_SPECS.items():
        if value_type != "boolean" or col not in CHECKBOX_SAFE_COLUMNS:
            continue
        col_idx = detail_df.columns.get_loc(label) + 1
        cell_range = f"{rowcol_to_a1(2, col_idx)}:{rowcol_to_a1(last_row, col_idx)}"
        worksheet.add_validation(
            cell_range, ValidationConditionType.boolean, [], showCustomUi=True,
        )


def main() -> None:
    # Deferred import: sync_back imports constants from this module, so a
    # top-level import here would be circular.
    from sheets import sync_back
    print("=== Pulling any edits from the Sheet first (so this publish doesn't overwrite them) ===")
    sync_back.main()
    print()

    sheet = open_sheet()

    write_dataframe(ensure_worksheet(sheet, README_TAB), _readme_rows())
    print(f"Published instructions to '{README_TAB}'.")

    report = build_report()
    write_dataframe(ensure_worksheet(sheet, LISTINGS_TAB), report)
    print(f"Published {len(report)} listings to '{LISTINGS_TAB}'.")

    detail_df = _listing_detail_rows()
    detail_ws = ensure_worksheet(sheet, LISTINGS_DETAIL_TAB)
    write_dataframe(detail_ws, detail_df)
    _record_detail_published(detail_df)
    _apply_detail_validation(detail_ws, detail_df)
    print(f"Published {len(detail_df)} listing detail rows to '{LISTINGS_DETAIL_TAB}'.")

    prefs_df = _preferences_rows()
    prefs_ws = ensure_worksheet(sheet, PREFERENCES_TAB)
    write_dataframe(prefs_ws, prefs_df)
    _apply_weight_validation(prefs_ws, prefs_df)
    print(f"Published {len(prefs_df)} feature rows to '{PREFERENCES_TAB}'.")

    filters_df = _hard_filter_rows()
    filters_ws = ensure_worksheet(sheet, HARD_FILTERS_TAB)
    write_dataframe(filters_ws, filters_df)
    _apply_hard_filter_validation(filters_ws, filters_df)
    print(f"Published {len(filters_df)} hard filter rows to '{HARD_FILTERS_TAB}'.")


if __name__ == "__main__":
    main()
