"""Fit a price model and report predicted vs. actual rent per listing.

A positive residual (actual - predicted) suggests a listing is priced
*above* what its features would predict -- possibly overvalued. A negative
residual suggests it may be underpriced.

With very few listings this is closer to a toy than a real valuation tool
-- treat anything under ~50 listings as indicative at best, and cross-check
against simple suburb-level $/sqm comparisons rather than trusting the
model alone.

Usage: python -m model.train
"""
from __future__ import annotations

import sqlite3

import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict

import config
from model.features import build_feature_matrix

MIN_ROWS_FOR_CV = 10


def load_listings() -> pd.DataFrame:
    conn = sqlite3.connect(config.DB_PATH)
    df = pd.read_sql_query("SELECT * FROM listings", conn)
    conn.close()
    return df


def evaluate(model, X, y, listing_ids) -> pd.DataFrame:
    n = len(X)
    if n < MIN_ROWS_FOR_CV:
        print(f"WARNING: only {n} listings with a price -- fitting on all data "
              f"with no held-out set. Residuals below are in-sample and optimistic; "
              f"treat them as a rough sanity check, not real predictions.")
        model.fit(X, y)
        predicted = model.predict(X)
    else:
        n_splits = min(5, n)
        cv = KFold(n_splits=n_splits, shuffle=True, random_state=0)
        predicted = cross_val_predict(model, X, y, cv=cv)

    result = pd.DataFrame({
        "listing_id": listing_ids.values,
        "actual_weekly_rent": y.values,
        "predicted_weekly_rent": predicted,
    })
    result["residual"] = result["actual_weekly_rent"] - result["predicted_weekly_rent"]
    result["pct_over_or_under"] = (result["residual"] / result["predicted_weekly_rent"] * 100).round(1)
    return result.sort_values("residual", ascending=False)


def main() -> None:
    df = load_listings()
    X, y, listing_ids = build_feature_matrix(df)

    if len(X) == 0:
        print("No listings with a parsed weekly_rent_aud yet -- ingest some listings first.")
        return

    print(f"{len(X)} listings with a price, {X.shape[1]} features.\n")

    for name, model in [("Ridge (baseline)", Ridge(alpha=1.0)),
                         ("HistGradientBoostingRegressor", HistGradientBoostingRegressor(random_state=0))]:
        print(f"=== {name} ===")
        result = evaluate(model, X, y, listing_ids)
        if len(X) >= MIN_ROWS_FOR_CV:
            mae = mean_absolute_error(result["actual_weekly_rent"], result["predicted_weekly_rent"])
            r2 = r2_score(result["actual_weekly_rent"], result["predicted_weekly_rent"])
            print(f"MAE: ${mae:.0f}/wk   R2: {r2:.2f}")
        print(result.to_string(index=False))
        print()


if __name__ == "__main__":
    main()
