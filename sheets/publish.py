"""Push the current triage report (listings + fit scores + ratings/status)
to a shared Google Sheet -- the read/browse surface for the household on
phone or laptop, no git/Python needed to just look. Also (re)writes a
"Preferences" tab for the feature-ranking exercise.

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
from sheets.readme import README_TEXT

LISTINGS_TAB = "Listings"
PREFERENCES_TAB = "Preferences"
README_TAB = "Read me"


def _preferences_rows() -> pd.DataFrame:
    """One row per weight-able feature (see sheets/feature_labels.py for
    which ones and why), with each person's current weight (blank if they
    haven't set one) -- what you fill in/adjust in the Sheet, which
    sheets/sync_back.py then reads back into their yaml."""
    names = people()
    weights_by_person = {name: load_preferences(name)["weights"] for name in names}

    rows = []
    for feature, description in FEATURE_LABELS.items():
        row = {"feature": feature, "what_this_means": description}
        for name in names:
            row[f"{name}_weight"] = weights_by_person[name].get(feature, "")
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


if __name__ == "__main__":
    main()
