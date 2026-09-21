"""One-time: parse a downloaded TfNSW GTFS zip (or an already-extracted
folder of it) into data/transit_stations.csv (name, lat, lon, mode) for
train/metro/light-rail stations only.

The GTFS "Timetables Complete" bundle covers every operator (trains, metro,
light rail, buses, ferries...) in one large zip -- buses dominate by row
count, so we filter using the GTFS route_type field rather than loading
everything. TfNSW uses Google's *extended* route_type vocabulary, not the
basic GTFS 0-7 spec (confirmed by inspecting the real feed -- route_type
'2' = train, covering both "Sydney Trains" and "NSW Trains" agencies,
'401' = "M1 Metro North West and Bankstown Line" (agency "Sydney Metro"),
'900' = "L1"-"L4" etc (agencies "Light Rail"/"Sydney Light Rail"/"Parramatta
Light Rail"). See https://developers.google.com/transit/gtfs/reference/extended-route-types

This only needs to be run once (or occasionally, e.g. when a metro
extension opens) -- the output is a small static CSV that's checked into
git (it's public transit station locations, not personal data), and
everything else reads from that, not from the raw GTFS data.

Usage:
    python -m ingest.build_transit_stations path/to/downloaded_gtfs.zip
    python -m ingest.build_transit_stations path/to/extracted_gtfs_folder
"""
from __future__ import annotations

import argparse
import csv
import io
import zipfile
from pathlib import Path

import config

ROUTE_TYPE_TO_MODE = {"2": "train", "401": "metro", "900": "light_rail"}


def _make_row_reader(gtfs_path: Path, zf: zipfile.ZipFile | None):
    """Returns a read_rows(filename) generator that works whether gtfs_path
    is a .zip file or an already-extracted directory."""
    if zf is not None:
        def read_rows(filename: str):
            with zf.open(filename) as f:
                yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        return read_rows

    def read_rows(filename: str):
        with (gtfs_path / filename).open(encoding="utf-8-sig") as f:
            yield from csv.DictReader(f)
    return read_rows


def build(gtfs_path: Path, out_path: Path) -> None:
    is_zip = gtfs_path.is_file() and gtfs_path.suffix.lower() == ".zip"
    zf = zipfile.ZipFile(gtfs_path) if is_zip else None
    try:
        available = set(zf.namelist()) if zf else {p.name for p in gtfs_path.iterdir()}
        required = {"routes.txt", "trips.txt", "stop_times.txt", "stops.txt"}
        missing = required - available
        if missing:
            raise SystemExit(
                f"GTFS source is missing expected files: {missing}.\n"
                f"Found instead: {sorted(available)[:20]}"
            )
        read_rows = _make_row_reader(gtfs_path, zf)

        print("Reading routes.txt...")
        route_id_to_mode = {}
        for row in read_rows("routes.txt"):
            mode = ROUTE_TYPE_TO_MODE.get(row["route_type"])
            if mode:
                route_id_to_mode[row["route_id"]] = mode
        print(f"  {len(route_id_to_mode)} train/metro/light-rail routes")

        print("Reading trips.txt...")
        trip_id_to_mode = {}
        for row in read_rows("trips.txt"):
            mode = route_id_to_mode.get(row["route_id"])
            if mode:
                trip_id_to_mode[row["trip_id"]] = mode
        print(f"  {len(trip_id_to_mode)} relevant trips")

        print("Scanning stop_times.txt (the big one -- can take a minute)...")
        stop_id_modes: dict[str, set[str]] = {}
        count = 0
        for row in read_rows("stop_times.txt"):
            count += 1
            mode = trip_id_to_mode.get(row["trip_id"])
            if mode:
                stop_id_modes.setdefault(row["stop_id"], set()).add(mode)
        print(f"  scanned {count:,} stop_times rows -> {len(stop_id_modes)} distinct relevant stops")

        print("Reading stops.txt...")
        stops_by_id = {row["stop_id"]: row for row in read_rows("stops.txt")}
    finally:
        if zf:
            zf.close()

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
    ap.add_argument("gtfs_path", type=Path, help="a GTFS .zip file, or a folder of its extracted contents")
    args = ap.parse_args()
    build(args.gtfs_path, config.TRANSIT_STATIONS_CSV)
