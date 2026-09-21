"""Office-commute lookups, cached in the commute_cache table so repeat
ingests never re-bill the Google Maps API for an address we've already
looked up. Low-level Google Maps calls live in ingest/maps.py; nearest-POI
lookups (which this also folds in, since they're keyed by the same listing
address/coordinates) live in ingest/poi.py."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import config
from ingest import maps
from ingest import poi as poi_module

_office_coords_cache: tuple[float, float] | None | object = "unset"


def _office_coords() -> tuple[float, float] | None:
    global _office_coords_cache
    if _office_coords_cache == "unset":
        _office_coords_cache = maps.geocode(config.OFFICE_ADDRESS) if config.OFFICE_ADDRESS else None
    return _office_coords_cache


def get_commute(conn: sqlite3.Connection, listing_address: str) -> dict:
    """Returns {lat, lon, driving_minutes, transit_minutes, straight_line_km,
    nearest_<category> / _km / _walk_minutes for every POI category}, using
    the cache table when available."""
    select_cols = ["lat", "lon", "driving_minutes", "transit_minutes"] + poi_module.POI_CACHE_COLUMNS
    row = conn.execute(
        f"SELECT {', '.join(select_cols)} FROM commute_cache WHERE address = ?",
        (listing_address,),
    ).fetchone()

    if row:
        cached = dict(zip(select_cols, row))
        lat, lon = cached["lat"], cached["lon"]
        driving_minutes, transit_minutes = cached["driving_minutes"], cached["transit_minutes"]
        poi_fields = {col: cached[col] for col in poi_module.POI_CACHE_COLUMNS}
    else:
        coords = maps.geocode(listing_address)
        lat, lon = coords if coords else (None, None)
        office_coords = _office_coords()
        driving_minutes = maps.route_matrix_minutes(office_coords, (lat, lon), "DRIVE") \
            if office_coords and lat else None
        transit_minutes = maps.route_matrix_minutes(office_coords, (lat, lon), "TRANSIT") \
            if office_coords and lat else None
        poi_fields = poi_module.get_nearest_pois(lat, lon)

        insert_cols = ["address", "lat", "lon", "driving_minutes", "transit_minutes"] \
            + poi_module.POI_CACHE_COLUMNS + ["computed_at"]
        values = [listing_address, lat, lon, driving_minutes, transit_minutes] \
            + [poi_fields[col] for col in poi_module.POI_CACHE_COLUMNS] \
            + [datetime.now(timezone.utc).isoformat()]
        conn.execute(
            f"INSERT OR REPLACE INTO commute_cache ({', '.join(insert_cols)}) "
            f"VALUES ({', '.join('?' for _ in insert_cols)})",
            values,
        )
        conn.commit()

    office_coords = _office_coords()
    straight_line_km = maps.haversine_km(lat, lon, *office_coords) if office_coords and lat else None

    return {
        "lat": lat,
        "lon": lon,
        "commute_driving_minutes": driving_minutes,
        "commute_transit_minutes": transit_minutes,
        "straight_line_km": straight_line_km,
        **poi_fields,
    }
