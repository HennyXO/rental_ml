"""Push the current triage report (listings + fit scores + ratings/status)
to a shared Google Sheet -- the read/browse surface for the household on
phone or laptop, no git/Python needed to just look. Also (re)writes
"Preferences" (feature weights) and "Hard filters" (budget/bedrooms/
suburbs/etc) tabs -- together, the only place either person needs to set
or adjust their own preferences day to day, no yaml editing required.

Run manually whenever you want the Sheet refreshed:
    python -m sheets.publish

If you've made edits directly in the Sheet (ratings, status, comments,
preference weights) that haven't been synced back yet, run
`python -m sheets.sync_back` FIRST -- this does a full overwrite of the
computed columns and doesn't try to merge concurrent edits against it.
"""
from __future__ import annotations

import pandas as pd

from report.triage import build_report
from score.fit_score import load_preferences, people
from sheets.client import ensure_worksheet, open_sheet, write_dataframe
from sheets.feature_labels import FEATURE_LABELS
from sheets.hard_filter_labels import HARD_FILTER_SPECS, render_value
from sheets.readme import README_TEXT

LISTINGS_TAB = "Listings"
PREFERENCES_TAB = "Preferences"
HARD_FILTERS_TAB = "Hard filters"
README_TAB = "Read me"


PREFERRED_SUBURBS_LIST_ROW = "preferred_suburbs_list"


def _preferences_rows() -> pd.DataFrame:
    """One row per weight-able feature (see sheets/feature_labels.py for
    which ones and why), with each person's current weight (blank if they
    haven't set one) -- what you fill in/adjust in the Sheet, which
    sheets/sync_back.py then reads back into their yaml. One row is special:
    PREFERRED_SUBURBS_LIST_ROW holds actual suburb names (comma-separated),
    not a numeric weight -- it's what the "preferred_suburbs" weight row
    scores against."""
    names = people()
    prefs_by_person = {name: load_preferences(name) for name in names}

    rows = []
    suburb_row = {"feature": PREFERRED_SUBURBS_LIST_ROW,
                  "what_this_means": "Your preferred suburbs, comma-separated (not a number -- "
                                      "see the 'preferred_suburbs' row below for how much this matters)"}
    for name in names:
        suburb_row[f"{name}_weight"] = ", ".join(prefs_by_person[name]["preferred_suburbs"])
    rows.append(suburb_row)

    for feature, description in FEATURE_LABELS.items():
        row = {"feature": feature, "what_this_means": description}
        for name in names:
            row[f"{name}_weight"] = prefs_by_person[name]["weights"].get(feature, "")
        rows.append(row)
    return pd.DataFrame(rows)


def _hard_filter_rows() -> pd.DataFrame:
    """One row per known hard filter (see sheets/hard_filter_labels.py),
    with each person's current value (blank = not set). sync_back.py reads
    this back and replaces each person's hard_filters entirely -- same
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


def _readme_rows() -> pd.DataFrame:
    return pd.DataFrame({"Read Me": README_TEXT.strip("\n").split("\n")})


def main() -> None:
    sheet = open_sheet()

    write_dataframe(ensure_worksheet(sheet, README_TAB), _readme_rows())
    print(f"Published instructions to '{README_TAB}'.")

    report = build_report()
    write_dataframe(ensure_worksheet(sheet, LISTINGS_TAB), report)
    print(f"Published {len(report)} listings to '{LISTINGS_TAB}'.")

    prefs_df = _preferences_rows()
    write_dataframe(ensure_worksheet(sheet, PREFERENCES_TAB), prefs_df)
    print(f"Published {len(prefs_df)} feature rows to '{PREFERENCES_TAB}'.")

    filters_df = _hard_filter_rows()
    write_dataframe(ensure_worksheet(sheet, HARD_FILTERS_TAB), filters_df)
    print(f"Published {len(filters_df)} hard filter rows to '{HARD_FILTERS_TAB}'.")


if __name__ == "__main__":
    main()
