"""Low-level Google Maps Platform helpers shared by office-commute lookups
(ingest/geocode_commute.py) and nearest-point-of-interest lookups
(ingest/poi.py). Neither of those modules should call requests.get/post on
these URLs directly -- go through here so there's one place that knows the
current API shapes."""
from __future__ import annotations

import math

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


def route_matrix_minutes(origin_latlng: tuple[float, float],
                          dest_latlng: tuple[float, float], travel_mode: str) -> float | None:
    """travel_mode: 'DRIVE', 'TRANSIT', or 'WALK'."""
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
