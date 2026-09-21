"""Nearest-point-of-interest lookups (train/metro/light-rail stations,
school, supermarket, park, beach), generalizing the pattern first built for
transit stations alone.

Point locations come from two static, committed CSVs (small, non-personal
public data -- built once, not fetched live):
- data/transit_stations.csv: name, lat, lon, mode -- from TfNSW's GTFS feed,
  see ingest/build_transit_stations.py. "mode" values are the bare GTFS-ish
  names (train/metro/light_rail); mapped to the "_station"-suffixed category
  names below on load.
- data/poi.csv: name, lat, lon, category -- from OpenStreetMap's Overpass
  API, see ingest/build_poi.py. category values already match the names
  below (school/supermarket/park/beach).

For each category, the nearest candidate is found via free local haversine
math first; only that single nearest candidate gets a Routes API walking-time
call, so this costs at most len(POI_CATEGORIES) API calls per listing, not
one per point of interest.
"""
from __future__ import annotations

import csv

import config
from ingest import maps
from ingest.schema import POI_CATEGORIES

_GTFS_MODE_TO_CATEGORY = {
    "train": "train_station",
    "metro": "metro_station",
    "light_rail": "light_rail_station",
}

_poi_by_category_cache: dict[str, list[tuple[str, float, float]]] | None = None


def _load_poi_data() -> dict[str, list[tuple[str, float, float]]]:
    global _poi_by_category_cache
    if _poi_by_category_cache is not None:
        return _poi_by_category_cache

    by_category: dict[str, list[tuple[str, float, float]]] = {cat: [] for cat in POI_CATEGORIES}

    if config.TRANSIT_STATIONS_CSV.exists():
        with config.TRANSIT_STATIONS_CSV.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                category = _GTFS_MODE_TO_CATEGORY.get(row["mode"])
                if category:
                    by_category[category].append((row["name"], float(row["lat"]), float(row["lon"])))

    if config.POI_CSV.exists():
        with config.POI_CSV.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["category"] in by_category:
                    by_category[row["category"]].append((row["name"], float(row["lat"]), float(row["lon"])))

    _poi_by_category_cache = by_category
    return by_category


def nearest_poi(lat, lon, category: str) -> tuple[str, float, float, float] | tuple[None, None, None, None]:
    """Returns (name, lat, lon, km) for the nearest point in `category`."""
    if lat is None or lon is None:
        return None, None, None, None
    best = None
    for name, p_lat, p_lon in _load_poi_data().get(category, []):
        km = maps.haversine_km(lat, lon, p_lat, p_lon)
        if best is None or km < best[3]:
            best = (name, p_lat, p_lon, km)
    return best if best else (None, None, None, None)


def get_nearest_pois(lat, lon) -> dict:
    """nearest_<category> / _km / _walk_minutes for every category in
    POI_CATEGORIES. Categories with no data yet (CSV not built) just come
    back null -- nothing else breaks."""
    result = {}
    for category in POI_CATEGORIES:
        name, p_lat, p_lon, km = nearest_poi(lat, lon, category)
        walk_minutes = maps.route_matrix_minutes((lat, lon), (p_lat, p_lon), "WALK") \
            if name is not None else None
        result[f"nearest_{category}"] = name
        result[f"nearest_{category}_km"] = km
        result[f"nearest_{category}_walk_minutes"] = walk_minutes
    return result


POI_CACHE_COLUMNS = [
    col for cat in POI_CATEGORIES
    for col in (f"nearest_{cat}", f"nearest_{cat}_km", f"nearest_{cat}_walk_minutes")
]
