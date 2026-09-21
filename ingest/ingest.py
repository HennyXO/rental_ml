"""Walk saved_webpages/ for saved listing pages, parse each new one,
look up commute time, and upsert into SQLite. Safe to re-run: files whose
name is already in the DB are skipped unless --force is passed.

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
from ingest.schema import ALL_COLUMN_NAMES, MANUAL_COLUMN_NAMES, get_connection


def already_ingested(conn, source_file: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM listings WHERE source_file = ?", (source_file,)
    ).fetchone()
    return row is not None


def upsert_listing(conn, fields: dict) -> None:
    row = {col: fields.get(col) for col in ALL_COLUMN_NAMES}

    # never clobber hand-filled columns (e.g. fits_two_desks_3rd_bedroom) --
    # re-parsing a listing (--force) must preserve any manual review already done
    existing = conn.execute(
        f"SELECT {', '.join(MANUAL_COLUMN_NAMES)} FROM listings WHERE listing_id = ?",
        (row["listing_id"],),
    ).fetchone()
    if existing:
        for col, value in zip(MANUAL_COLUMN_NAMES, existing):
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
        if not force and already_ingested(conn, path.name):
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
