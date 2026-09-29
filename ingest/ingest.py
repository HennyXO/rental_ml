"""Walk saved_webpages/ for saved listing pages, parse each new one,
look up commute time, and upsert into SQLite. Safe to re-run: files whose
name is already in the DB are skipped unless --force is passed (or they
still lack a commute lookup, e.g. from an earlier --no-commute run).

Usage:
    python -m ingest.ingest
    python -m ingest.ingest --force        # re-parse everything
    python -m ingest.ingest --no-commute   # skip Google Maps calls (faster, free)
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

import config
from ingest.geocode_commute import get_commute
from ingest.parse_listing import parse_file
from ingest.schema import ALL_COLUMN_NAMES, get_connection


def already_ingested(conn, source_file: str, with_commute: bool) -> bool:
    row = conn.execute(
        "SELECT lat FROM listings WHERE source_file = ?", (source_file,)
    ).fetchone()
    return row is not None and (row[0] is not None or not with_commute)


def upsert_listing(conn, fields: dict) -> None:
    row = {col: fields.get(col) for col in ALL_COLUMN_NAMES}

    # An existing DB value wins when this parse didn't compute the column
    # at all (e.g. --no-commute leaves commute/lat/lon absent, and status/
    # notes are never parsed), so absence never erases data. A fresh value
    # for anything else (a real price change, better keywords) updates,
    # except where a human corrected it via the Sheet (manual_overrides).
    existing = conn.execute(
        f"SELECT {', '.join(ALL_COLUMN_NAMES)} FROM listings WHERE listing_id = ?",
        (row["listing_id"],),
    ).fetchone()
    if existing:
        for col, existing_value in zip(ALL_COLUMN_NAMES, existing):
            if row[col] is None:
                row[col] = existing_value
    overrides = conn.execute(
        "SELECT column_name, value FROM manual_overrides WHERE listing_id = ?", (row["listing_id"],)
    ).fetchall()
    for col, value in overrides:
        row[col] = value

    placeholders = ", ".join("?" for _ in ALL_COLUMN_NAMES)
    columns = ", ".join(ALL_COLUMN_NAMES)
    conn.execute(
        f"INSERT OR REPLACE INTO listings ({columns}) VALUES ({placeholders})",
        [row[col] for col in ALL_COLUMN_NAMES],
    )
    conn.commit()


def run(force: bool = False, with_commute: bool = True) -> None:
    conn = get_connection(config.DB_PATH)
    html_files = sorted(config.RAW_HTML_RENT_DIR.glob("*.html")) + \
        sorted(config.RAW_HTML_RENT_DIR.glob("*.htm"))

    if not html_files:
        print(f"No .html files found in {config.RAW_HTML_RENT_DIR}. "
              "Save some listing pages there first (see README).")
        return

    processed, skipped = 0, 0
    for path in html_files:
        if not force and already_ingested(conn, path.name, with_commute):
            skipped += 1
            continue

        fields = parse_file(path)
        fields["date_captured"] = datetime.now(timezone.utc).isoformat()

        if with_commute and fields.get("address"):
            try:
                commute = get_commute(conn, fields["address"])
                fields.update(commute)
            except Exception as exc:  # geocoding/API errors shouldn't kill the whole batch
                print(f"WARNING: commute lookup failed for {path.name}: {exc}")

        upsert_listing(conn, fields)
        processed += 1
        print(f"Ingested {path.name} -> {fields.get('address') or 'address unknown'} "
              f"(${fields.get('weekly_rent_aud')}/wk)")

    print(f"\nDone. Processed {processed}, skipped {skipped} already-ingested file(s).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-parse files already in the DB")
    ap.add_argument("--no-commute", action="store_true", help="skip Google Maps lookups")
    args = ap.parse_args()
    run(force=args.force, with_commute=not args.no_commute)
