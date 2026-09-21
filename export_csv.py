"""Dump the listings table to CSV and Excel for a quick eyeball.

Usage: python export_csv.py
"""
import sqlite3

import pandas as pd

import config


def main() -> None:
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    df = pd.read_sql_query("SELECT * FROM listings ORDER BY date_captured DESC", conn)
    conn.close()

    csv_path = config.EXPORT_DIR / "listings.csv"
    xlsx_path = config.EXPORT_DIR / "listings.xlsx"
    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)

    print(f"Exported {len(df)} listings to:\n  {csv_path}\n  {xlsx_path}")


if __name__ == "__main__":
    main()
