"""One-command household refresh: parse newly saved listings, then push the
refreshed report back to the shared Sheet. Equivalent to running
ingest then publish yourself. publish.main() pulls any pending Sheet edits
first automatically (see sheets/publish.py's docstring), so there's no
separate sync_back step needed here.

Usage:
    python refresh.py
    python refresh.py --force        # re-parse every saved listing, not just new ones
    python refresh.py --no-commute   # skip Google Maps commute/POI lookups
"""
from __future__ import annotations

import argparse

from ingest import ingest
from sheets import publish


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-parse files already in the DB")
    ap.add_argument("--no-commute", action="store_true", help="skip Google Maps lookups")
    args = ap.parse_args()

    print("=== Ingesting newly saved listings ===")
    ingest.run(force=args.force, with_commute=not args.no_commute)

    print("\n=== Publishing the refreshed report back to the Sheet ===")
    publish.main()


if __name__ == "__main__":
    main()
