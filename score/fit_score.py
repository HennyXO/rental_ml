"""Per-person hard-filter check + weighted fit score, computed
transparently from features already in the catalogue -- useful from
listing #1, no ML training required. See preferences/example.yaml for the
file format this reads.

fit_score is a *relative ranking within the current dataset*, scaled to
look like a 0-10 gut rating for easy comparison -- not a calibrated
absolute score. With few listings it will look more decisive than it
really is; treat it as a sort order and a "why" (via hard_filter_reasons),
not gospel.
"""
from __future__ import annotations

import pandas as pd
import yaml

import config


def people() -> list[str]:
    """Names with a preferences/<name>.yaml file (excludes the example)."""
    if not config.PREFERENCES_DIR.exists():
        return []
    return sorted(p.stem for p in config.PREFERENCES_DIR.glob("*.yaml") if p.stem != "example")


def load_preferences(name: str) -> dict:
    path = config.PREFERENCES_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"No preferences file for '{name}' at {path}. Copy preferences/example.yaml to get started."
        )
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("hard_filters", {})
    data.setdefault("weights", {})
    return data


def _check_hard_filters(row: pd.Series, hard_filters: dict) -> list[str]:
    """Returns human-readable failure reasons; empty list = passes.
    A column that's missing/null for this listing never fails a filter --
    benefit of the doubt for parser gaps, rather than hiding a possibly-
    relevant listing over a data quality issue."""
    failures = []
    for key, threshold in hard_filters.items():
        if key.startswith("max_"):
            column = key[4:]
            value = row.get(column)
            if pd.notna(value) and value > threshold:
                failures.append(f"{column} = {value} > max {threshold}")
        elif key.startswith("min_"):
            column = key[4:]
            value = row.get(column)
            if pd.notna(value) and value < threshold:
                failures.append(f"{column} = {value} < min {threshold}")
        elif key.startswith("allowed_"):
            column = key[len("allowed_"):]
            value = row.get(column)
            if pd.notna(value) and threshold and value not in threshold:
                failures.append(f"{column} = {value!r} not in allowed {threshold}")
        elif key.endswith("_required"):
            column = key[: -len("_required")]
            value = row.get(column)
            if threshold and not (pd.notna(value) and value):
                failures.append(f"{column} required but missing/false")
        else:
            raise ValueError(
                f"Unrecognised hard_filters key '{key}' -- expected a max_/min_/allowed_ "
                f"prefix or a _required suffix"
            )
    return failures


def _normalize(series: pd.Series) -> pd.Series:
    """Min-max to 0..1. Missing values and zero-variance columns (including
    the single-listing case) fall back to a neutral 0.5 rather than NaN."""
    numeric = pd.to_numeric(series, errors="coerce")
    lo, hi = numeric.min(), numeric.max()
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(0.5, index=series.index)
    return ((numeric - lo) / (hi - lo)).fillna(0.5)


def score_person(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Adds <name>_hard_filter_pass (bool), <name>_hard_filter_reasons (str),
    <name>_fit_score (0-10) to a copy of df."""
    prefs = load_preferences(name)
    df = df.copy()

    reasons = df.apply(lambda row: _check_hard_filters(row, prefs["hard_filters"]), axis=1)
    df[f"{name}_hard_filter_pass"] = reasons.apply(lambda r: len(r) == 0)
    df[f"{name}_hard_filter_reasons"] = reasons.apply(lambda r: "; ".join(r))

    raw = pd.Series(0.0, index=df.index)
    for column, weight in prefs["weights"].items():
        if not weight or column not in df.columns:
            continue
        raw = raw + weight * _normalize(df[column])
    df[f"{name}_fit_score"] = (_normalize(raw) * 10).round(1)

    return df


def score_all(df: pd.DataFrame) -> pd.DataFrame:
    """score_person for every person with a preferences file."""
    for name in people():
        df = score_person(df, name)
    return df
