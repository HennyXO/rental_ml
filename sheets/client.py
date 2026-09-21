"""Shared gspread client setup for sheets/publish.py and sheets/sync_back.py.
See README "Shared Google Sheet" for the one-time Google Cloud setup this
depends on: a service account with the Sheets API enabled, its JSON key
saved locally (path in GOOGLE_SHEETS_KEY_PATH), and a Sheet created and
shared with that service account's email (ID in GOOGLE_SHEET_ID)."""
from __future__ import annotations

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def open_sheet():
    if not config.GOOGLE_SHEETS_KEY_PATH:
        raise RuntimeError(
            "GOOGLE_SHEETS_KEY_PATH is not set in .env -- see README 'Shared Google Sheet' setup."
        )
    if not config.GOOGLE_SHEET_ID:
        raise RuntimeError(
            "GOOGLE_SHEET_ID is not set in .env -- see README 'Shared Google Sheet' setup."
        )
    creds = Credentials.from_service_account_file(config.GOOGLE_SHEETS_KEY_PATH, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(config.GOOGLE_SHEET_ID)


def ensure_worksheet(sheet, title: str, rows: int = 300, cols: int = 40):
    try:
        return sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=title, rows=rows, cols=cols)


def write_dataframe(worksheet, df: pd.DataFrame) -> None:
    """Full overwrite of the worksheet's contents with df (header + rows)."""
    worksheet.clear()
    safe = df.astype(object).where(pd.notna(df), "")
    values = [list(df.columns)] + safe.values.tolist()
    worksheet.update(values)


def read_dataframe(worksheet) -> pd.DataFrame:
    return pd.DataFrame(worksheet.get_all_records())
