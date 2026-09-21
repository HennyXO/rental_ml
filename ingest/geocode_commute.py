"""Geocoding + commute-time lookups, cached in the commute_cache table so
repeat ingests never re-bill the Google Maps API for an address we've
already looked up."""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone

import requests

import config

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
# The legacy Distance Matrix API (maps.googleapis.com/maps/api/distancematrix)
# is disabled by default on new Google Cloud projects -- Google now points
# new projects at the Routes API instead. See:
# https://developers.google.com/maps/documentation/routes/compute_route_matrix
ROUTE_MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"


def haversine_km(lat1, lon1, lat2, lon2) -> float | None:
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def geocode(address: str) -> tuple[float, float] | None:
    if not config.GOOGLE_MAPS_API_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not set in .env")
    resp = requests.get(
        GEOCODE_URL,
        params={"address": address, "key": config.GOOGLE_MAPS_API_KEY, "region": "au"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        return None
    loc = data["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def _duration_seconds_to_minutes(duration_str) -> float | None:
    """Routes API returns duration as a protobuf Duration string like '1234s'."""
    if not duration_str:
        return None
    try:
        return float(duration_str.rstrip("s")) / 60.0
    except ValueError:
        return None


def _route_matrix_minutes(origin_latlng: tuple[float, float],
                           dest_latlng: tuple[float, float], travel_mode: str) -> float | None:
    """travel_mode: 'DRIVE' or 'TRANSIT'."""
    body = {
        "origins": [{"waypoint": {"location": {"latLng": {
            "latitude": origin_latlng[0], "longitude": origin_latlng[1]}}}}],
        "destinations": [{"waypoint": {"location": {"latLng": {
            "latitude": dest_latlng[0], "longitude": dest_latlng[1]}}}}],
        "travelMode": travel_mode,
    }
    if travel_mode == "DRIVE":
        body["routingPreference"] = "TRAFFIC_AWARE"

    resp = requests.post(
        ROUTE_MATRIX_URL,
        json=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": config.GOOGLE_MAPS_API_KEY,
            "X-Goog-FieldMask": "originIndex,destinationIndex,duration,distanceMeters,condition",
        },
        timeout=10,
    )
    resp.raise_for_status()
    elements = resp.json()  # response body is a JSON array of RouteMatrixElement
    if not elements:
        return None
    element = elements[0]
    if element.get("condition") not in (None, "ROUTE_EXISTS"):
        return None
    return _duration_seconds_to_minutes(element.get("duration"))


_office_coords_cache: tuple[float, float] | None | object = "unset"


def _office_coords() -> tuple[float, float] | None:
    global _office_coords_cache
    if _office_coords_cache == "unset":
        _office_coords_cache = geocode(config.OFFICE_ADDRESS) if config.OFFICE_ADDRESS else None
    return _office_coords_cache


def get_commute(conn: sqlite3.Connection, listing_address: str) -> dict:
    """Returns {lat, lon, driving_minutes, transit_minutes, straight_line_km},
    using the cache table when available."""
    row = conn.execute(
        "SELECT lat, lon, driving_minutes, transit_minutes FROM commute_cache WHERE address = ?",
        (listing_address,),
    ).fetchone()

    if row:
        lat, lon, driving_minutes, transit_minutes = row
    else:
        coords = geocode(listing_address)
        lat, lon = coords if coords else (None, None)
        office_coords = _office_coords()
        driving_minutes = _route_matrix_minutes(office_coords, (lat, lon), "DRIVE") \
            if office_coords and lat else None
        transit_minutes = _route_matrix_minutes(office_coords, (lat, lon), "TRANSIT") \
            if office_coords and lat else None
        conn.execute(
            "INSERT OR REPLACE INTO commute_cache "
            "(address, lat, lon, driving_minutes, transit_minutes, computed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (listing_address, lat, lon, driving_minutes, transit_minutes,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()

    office_coords = _office_coords()
    straight_line_km = haversine_km(lat, lon, *office_coords) if office_coords and lat else None

    return {
        "lat": lat,
        "lon": lon,
        "commute_driving_minutes": driving_minutes,
        "commute_transit_minutes": transit_minutes,
        "straight_line_km": straight_line_km,
    }
