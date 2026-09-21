"""Central config: paths and secrets, loaded once from .env."""
from pathlib import Path

from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

OFFICE_ADDRESS = os.environ.get("OFFICE_ADDRESS", "")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# Sheets publish/sync -- see README "Shared Google Sheet" section for setup.
GOOGLE_SHEETS_KEY_PATH = os.environ.get("GOOGLE_SHEETS_KEY_PATH", "")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")

DATA_DIR = ROOT_DIR / "data"
# Override to point at a shared cloud-synced folder (Dropbox/Drive/iCloud)
# if more than one person is capturing listings -- see README "Workflow".
RAW_HTML_RENT_DIR = Path(os.environ["SAVED_WEBPAGES_DIR"]) if os.environ.get("SAVED_WEBPAGES_DIR") \
    else ROOT_DIR / "saved_webpages"
RAW_HTML_SALE_DIR = ROOT_DIR / "saved_webpages_sale"  # phase 2, not used yet
DB_PATH = DATA_DIR / "db" / "listings.sqlite"
EXPORT_DIR = DATA_DIR / "exports"
# Small, derived, non-personal -- committed to git. Built once by
# ingest/build_transit_stations.py from a downloaded GTFS zip, and
# ingest/build_poi.py from OpenStreetMap's Overpass API.
TRANSIT_STATIONS_CSV = DATA_DIR / "transit_stations.csv"
POI_CSV = DATA_DIR / "poi.csv"

PREFERENCES_DIR = ROOT_DIR / "preferences"
