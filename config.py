"""Central config: paths and secrets, loaded once from .env."""
from pathlib import Path

from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

OFFICE_ADDRESS = os.environ.get("OFFICE_ADDRESS", "")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

DATA_DIR = ROOT_DIR / "data"
RAW_HTML_RENT_DIR = ROOT_DIR / "saved_webpages"
RAW_HTML_SALE_DIR = ROOT_DIR / "saved_webpages_sale"  # phase 2, not used yet
DB_PATH = DATA_DIR / "db" / "listings.sqlite"
EXPORT_DIR = DATA_DIR / "exports"
# Small, derived, non-personal -- committed to git. Built once by
# ingest/build_transit_stations.py from a downloaded GTFS zip.
TRANSIT_STATIONS_CSV = DATA_DIR / "transit_stations.csv"
