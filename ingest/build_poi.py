"""One-time: pull school/supermarket/park/beach locations for Greater Sydney
from OpenStreetMap's Overpass API into data/poi.csv (name, lat, lon,
category). Free, no API key or account needed -- unlike TfNSW's GTFS feed,
this is a live query, not a bulk download, so it's a genuine "run it once
and you're done" step (re-run occasionally if you want fresher data, but
don't hammer the public Overpass instance -- it's a shared community
resource).

Train/metro/light-rail stations are handled separately by
ingest/build_transit_stations.py (GTFS is the authoritative source for
those); this script is for everything else in ingest/schema.py's
POI_CATEGORIES.

Usage:
    python -m ingest.build_poi
"""
from __future__ import annotations

import csv
import time

import requests

import config

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Greater Sydney bounding box (south, west, north, east) -- wide enough to
# cover the metro area without pulling all of NSW.
BBOX = (-34.3, 150.4, -33.4, 151.5)

# category -> list of (osm_key, osm_value) tag pairs that count as that category
CATEGORY_TAGS = {
    "school": [("amenity", "school")],
    "supermarket": [("shop", "supermarket")],
    "park": [("leisure", "park")],
    "beach": [("natural", "beach")],
}


def _build_query(tags: list[tuple[str, str]]) -> str:
    south, west, north, east = BBOX
    bbox_str = f"{south},{west},{north},{east}"
    clauses = []
    for key, value in tags:
        clauses.append(f'  node["{key}"="{value}"]({bbox_str});')
        clauses.append(f'  way["{key}"="{value}"]({bbox_str});')
    return "[out:json][timeout:150];\n(\n" + "\n".join(clauses) + "\n);\nout center tags;"


def fetch_category(category: str, tags: list[tuple[str, str]], retries: int = 2) -> list[dict]:
    """One Overpass request per category -- the combined query for all four
    timed out server-side (504) on the shared public instance; splitting
    keeps each request small enough to actually complete, and means one
    slow/failing category doesn't lose the others. 'park' in particular has
    thousands of large polygon geometries in OSM and needs the full 150s.
    Retries with backoff on 429 (rate limited) / 504 (transient timeout),
    since both are common on the shared public instance."""
    query = _build_query(tags)
    for attempt in range(retries + 1):
        print(f"  querying Overpass for '{category}'{' (retry)' if attempt else ''}...")
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers={"User-Agent": "rental-market-ml-project/1.0 (personal, non-commercial research tool)"},
            timeout=180,
        )
        if resp.status_code in (429, 504) and attempt < retries:
            wait = 30 * (attempt + 1)
            print(f"    got {resp.status_code}, waiting {wait}s before retry...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()["elements"]
    return []


def _load_existing(out_path) -> dict[str, list[tuple[str, float, float, str]]]:
    by_category: dict[str, list] = {}
    if out_path.exists():
        with out_path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                by_category.setdefault(row["category"], []).append(
                    (row["name"], float(row["lat"]), float(row["lon"]), row["category"])
                )
    return by_category


def build(out_path) -> None:
    """Merges into any existing out_path rather than overwriting wholesale,
    so a category that fails this run (rate limits, timeouts) keeps
    whatever data it had from a previous run instead of being wiped."""
    by_category = _load_existing(out_path)

    for i, (category, tags) in enumerate(CATEGORY_TAGS.items()):
        if i > 0:
            time.sleep(5)  # be polite to the shared public instance between categories
        try:
            elements = fetch_category(category, tags)
        except requests.exceptions.RequestException as exc:
            kept = len(by_category.get(category, []))
            print(f"  WARNING: '{category}' query failed ({exc}) -- "
                  f"keeping {kept} existing row(s) for it, re-run later to refresh")
            continue
        print(f"    {len(elements)} raw elements")

        rows = []
        for el in elements:
            el_tags = el.get("tags", {})
            if el["type"] == "node":
                lat, lon = el.get("lat"), el.get("lon")
            else:  # way -- use the computed centroid ("out center" in the query)
                center = el.get("center") or {}
                lat, lon = center.get("lat"), center.get("lon")
            if lat is None or lon is None:
                continue
            name = el_tags.get("name") or f"Unnamed {category} ({el['type']}/{el['id']})"
            rows.append((name, lat, lon, category))
        by_category[category] = rows

    all_rows = [row for rows in by_category.values() for row in rows]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "lat", "lon", "category"])
        for row in sorted(all_rows):
            writer.writerow(row)

    counts = {cat: len(rows) for cat, rows in by_category.items()}
    print(f"\nWrote {len(all_rows)} points of interest to {out_path}: {counts}")


if __name__ == "__main__":
    build(config.POI_CSV)
