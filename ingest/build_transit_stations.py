"""One-time: parse a downloaded TfNSW GTFS zip into data/transit_stations.csv
(name, lat, lon, mode) for train/metro/light-rail stations only.

The GTFS "Timetables Complete" bundle covers every operator (trains, metro,
light rail, buses, ferries...) in one large zip -- buses dominate by row
count, so we filter using the GTFS route_type field rather than loading
everything: 2 = train (Sydney Trains/NSW TrainLink), 1 = metro (subway),
0 = light rail/tram. See https://gtfs.org/schedule/reference/#routestxt

This only needs to be run once (or occasionally, e.g. when a metro
extension opens) -- the output is a small static CSV that's checked into
git (it's public transit station locations, not personal data), and
everything else reads from that, not from the GTFS zip.

Usage:
    python -m ingest.build_transit_stations path/to/downloaded_gtfs.zip
"""
from __future__ import annotations

import argparse
import csv
import io
import zipfile
from pathlib import Path

import config

ROUTE_TYPE_TO_MODE = {"0": "light_rail", "1": "metro", "2": "train"}


def _read_csv_rows(zf: zipfile.ZipFile, filename: str):
    with zf.open(filename) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig")
        yield from csv.DictReader(text)


def build(gtfs_zip_path: Path, out_path: Path) -> None:
    with zipfile.ZipFile(gtfs_zip_path) as zf:
        names = set(zf.namelist())
        required = {"routes.txt", "trips.txt", "stop_times.txt", "stops.txt"}
        missing = required - names
        if missing:
            raise SystemExit(
                f"GTFS zip is missing expected files: {missing}.\n"
                f"Found instead: {sorted(names)[:20]}"
            )

        print("Reading routes.txt...")
        route_id_to_mode = {}
        for row in _read_csv_rows(zf, "routes.txt"):
            mode = ROUTE_TYPE_TO_MODE.get(row["route_type"])
            if mode:
                route_id_to_mode[row["route_id"]] = mode
        print(f"  {len(route_id_to_mode)} train/metro/light-rail routes")

        print("Reading trips.txt...")
        trip_id_to_mode = {}
        for row in _read_csv_rows(zf, "trips.txt"):
            mode = route_id_to_mode.get(row["route_id"])
            if mode:
                trip_id_to_mode[row["trip_id"]] = mode
        print(f"  {len(trip_id_to_mode)} relevant trips")

        print("Scanning stop_times.txt (the big one -- can take a minute)...")
        stop_id_modes: dict[str, set[str]] = {}
        count = 0
        for row in _read_csv_rows(zf, "stop_times.txt"):
            count += 1
            mode = trip_id_to_mode.get(row["trip_id"])
            if mode:
                stop_id_modes.setdefault(row["stop_id"], set()).add(mode)
        print(f"  scanned {count:,} stop_times rows -> {len(stop_id_modes)} distinct relevant stops")

        print("Reading stops.txt...")
        stops_by_id = {row["stop_id"]: row for row in _read_csv_rows(zf, "stops.txt")}

    # Collapse platform-level stops to their parent station where GTFS
    # provides one, so e.g. each platform at Central doesn't become its
    # own separate "station" point.
    stations: dict[tuple[str, str], tuple[str, float, float, str]] = {}
    for stop_id, modes in stop_id_modes.items():
        stop = stops_by_id.get(stop_id)
        if not stop:
            continue
        parent_id = stop.get("parent_station") or ""
        resolved = stops_by_id.get(parent_id, stop) if parent_id else stop
        try:
            lat, lon = float(resolved["stop_lat"]), float(resolved["stop_lon"])
        except (KeyError, ValueError):
            continue
        name = resolved.get("stop_name") or stop.get("stop_name") or stop_id
        resolved_id = resolved.get("stop_id", stop_id)
        for mode in modes:
            stations[(resolved_id, mode)] = (name, lat, lon, mode)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "lat", "lon", "mode"])
        for name, lat, lon, mode in sorted(stations.values()):
            writer.writerow([name, lat, lon, mode])

    by_mode: dict[str, int] = {}
    for *_unused, mode in stations.values():
        by_mode[mode] = by_mode.get(mode, 0) + 1
    print(f"\nWrote {len(stations)} stations to {out_path}: {by_mode}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gtfs_zip", type=Path)
    args = ap.parse_args()
    build(args.gtfs_zip, config.TRANSIT_STATIONS_CSV)
