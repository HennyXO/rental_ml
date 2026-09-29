"""The daily-use report: one row per listing, each person's hard-filter
status and fit score, a market-value signal (predicted rent vs. actual,
see model/train.py), manual ratings if logged, and a suggested next
action. This is what the household looks at together, not the raw DB.

Usage: python -m report.triage
"""
from __future__ import annotations

import sqlite3

import pandas as pd

import config
from model.train import predict_value
from score.fit_score import people, score_all

RATING_THRESHOLD_GOOD = 7
RATING_THRESHOLD_LOW = 4
RATING_DIVERGE = 3


def load_listings_with_ratings() -> pd.DataFrame:
    conn = sqlite3.connect(config.DB_PATH)
    listings = pd.read_sql_query("SELECT * FROM listings", conn)
    ratings = pd.read_sql_query("SELECT * FROM ratings", conn)
    conn.close()

    for name in people():
        person_ratings = ratings[ratings["person"] == name][["listing_id", "score", "comment"]]
        person_ratings = person_ratings.rename(
            columns={"score": f"{name}_rating", "comment": f"{name}_comment"}
        )
        listings = listings.merge(person_ratings, on="listing_id", how="left")

    return listings


def suggest_action(row: pd.Series, names: list[str]) -> str:
    if pd.notna(row.get("status")) and str(row.get("status")).strip():
        return str(row["status"])  # a human already decided, report it, don't override

    hard_fail = [n for n in names if not row.get(f"{n}_hard_filter_pass", True)]
    if hard_fail:
        return f"skip -- hard filter failed ({', '.join(hard_fail)})"

    ratings = [row.get(f"{n}_rating") for n in names]
    if any(pd.isna(r) for r in ratings) or not ratings:
        return "awaiting rating"

    if max(ratings) - min(ratings) >= RATING_DIVERGE:
        return "discuss -- scores diverge"
    if all(r >= RATING_THRESHOLD_GOOD for r in ratings):
        return "worth inspecting"
    if all(r < RATING_THRESHOLD_LOW for r in ratings):
        return "skip -- low rating"
    return "maybe"


def build_report() -> pd.DataFrame:
    df = load_listings_with_ratings()
    names = people()
    df = score_all(df)
    df = df.merge(predict_value(df), on="listing_id", how="left")
    df["suggested_action"] = df.apply(lambda row: suggest_action(row, names), axis=1)
    # Whichever of train/metro/light rail is closest; skipna so one missing
    # mode doesn't blank the whole thing.
    df["nearest_rail_walk_minutes"] = df[
        [f"nearest_{cat}_walk_minutes" for cat in ("train_station", "metro_station", "light_rail_station")]
    ].min(axis=1)
    # Harmonic mean of everyone's 0-10 fit scores: a "would we both like it"
    # sort key that drags down a listing one person loves and the other
    # doesn't (9 and 3 -> 4.5, not 6). Any 0 gives 0 (1/0 = inf).
    fit = df[[f"{n}_fit_score" for n in names]]
    df["combined_fit_score"] = (len(names) / (1 / fit).sum(axis=1)).round(1)

    # predicted_weekly_rent/pct_over_or_under deliberately go last, past
    # every person's own rating/comment: a gut-reaction rating shouldn't
    # be anchored by the price model's opinion before you've even formed
    # one, so it's off the initial view, not hidden, just a scroll away.
    columns = ["listing_id", "address", "suburb", "url", "weekly_rent_aud", "bedrooms",
               "lease_term_months", "available_from",
               "commute_transit_minutes", "nearest_train_station_walk_minutes",
               "nearest_rail_walk_minutes", "status", "suggested_action", "combined_fit_score"]
    for name in names:
        columns += [f"{name}_hard_filter_pass", f"{name}_fit_score", f"{name}_rating", f"{name}_comment"]
    columns += ["predicted_weekly_rent", "pct_over_or_under"]
    rounded = ["commute_transit_minutes", "nearest_train_station_walk_minutes",
               "nearest_rail_walk_minutes", "predicted_weekly_rent"]
    df[rounded] = df[rounded].round(2)
    return df[columns]


def main() -> None:
    report = build_report()
    action_priority = {
        "discuss -- scores diverge": 0,
        "worth inspecting": 1,
        "maybe": 2,
        "awaiting rating": 3,
    }
    report = report.assign(_sort=report["suggested_action"].map(action_priority).fillna(4))
    report = report.sort_values(["_sort"]).drop(columns="_sort")

    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(report.to_string(index=False))


if __name__ == "__main__":
    main()
