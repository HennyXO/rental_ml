"""Parse one saved realestate.com.au listing HTML file into a feature dict.

Verified against a real saved rental listing (see plan Step 0). Two things
turned out to matter:

1. The `window.ArgonautExchange` blob some articles describe as "the" data
   source is, on a page you reach by clicking through from a search list,
   often just a leftover cache of an unrelated earlier search query (we
   found totally different properties in there) -- not reliable. What IS
   reliable on every listing page:
   - `<meta name="description">` and `<meta property="og:description">` --
     clean, human-written summary text and full description/bullet
     features.
   - A handful of stable, semantic (non-hashed) CSS classes:
     `property-info-address`, `property-info__primary-features`
     (bed/bath/car via each `<li aria-label="N bedrooms">` etc.),
     `property-price`.
   - `application/ld+json` blocks for structured address components
     (suburb/postcode).
2. Rentals routinely omit land size / floor size entirely (sale listings
   for the same address often have it) -- confirmed on the sample page.
   That's the whole reason phase 2 (matching sale listings by address) is
   on the roadmap.

Run with --debug on a file to see every extracted value:

    python -m ingest.parse_listing path/to/saved_listing.html --debug
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from ingest.schema import AMENITY_KEYWORDS

_NUM_RE = re.compile(r"[-+]?\d*\.?\d+")
_ADDRESS_RE = re.compile(
    r"^(?P<street>.+?),\s*(?P<suburb>[^,]+?)(?:,)?\s+(?P<state>[A-Z]{2,3})\s+(?P<postcode>\d{4})$"
)


def _to_int(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    m = _NUM_RE.search(str(value))
    return int(float(m.group())) if m else None


def _to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = _NUM_RE.search(str(value).replace(",", ""))
    return float(m.group()) if m else None


def _parse_price(text) -> float | None:
    """'$1,150 per week' / 'Contact Agent' / 'Auction' -> 1150.0 or None."""
    if not text:
        return None
    if "contact" in text.lower() or "auction" in text.lower():
        return None
    return _to_float(text)


def _meta(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
    return tag.get("content") if tag else None


def _find_json_ld_address(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            addr = item.get("address") if isinstance(item, dict) else None
            if isinstance(addr, dict) and addr.get("addressLocality"):
                return {
                    "suburb": addr.get("addressLocality"),
                    "postcode": addr.get("postalCode"),
                    "street": addr.get("streetAddress"),
                }
    return {}


def _parse_address(full_address: str | None, json_ld_addr: dict) -> dict:
    result = {"suburb": json_ld_addr.get("suburb"), "postcode": json_ld_addr.get("postcode")}
    if full_address:
        m = _ADDRESS_RE.match(full_address.strip())
        if m:
            result.setdefault("suburb", None)
            result["suburb"] = result["suburb"] or m.group("suburb")
            result["postcode"] = result["postcode"] or m.group("postcode")
    return result


def _extract_bed_bath_car(soup: BeautifulSoup) -> dict:
    out = {"bedrooms": None, "bathrooms": None, "parking_spaces": None}
    features_ul = soup.find("ul", class_="property-info__primary-features")
    if not features_ul:
        return out
    for li in features_ul.find_all("li"):
        label = (li.get("aria-label") or "").lower()
        if "bedroom" in label:
            out["bedrooms"] = _to_int(label)
        elif "bathroom" in label:
            out["bathrooms"] = _to_int(label)
        elif "car space" in label or "carspace" in label:
            out["parking_spaces"] = _to_int(label)
    return out


def _extract_property_type(soup: BeautifulSoup) -> str | None:
    container = soup.find("div", class_="property-info__property-attributes")
    if not container:
        return None
    for token in container.get_text("|", strip=True).split("|"):
        token = token.strip()
        if token and token != "•" and not _NUM_RE.fullmatch(token):
            return token
    return None


def _extract_price(soup: BeautifulSoup) -> str | None:
    el = soup.find(class_="property-price")
    return el.get_text(strip=True) if el else None


def _extract_description_and_features(soup: BeautifulSoup) -> tuple[str | None, list[str]]:
    """og:description is the full listing body, usually with <br/>-joined
    lines and feature bullets prefixed with '- '."""
    og_desc = _meta(soup, "og:description")
    if not og_desc:
        pd = soup.find(attrs={"data-testid": "PropertyDescription"})
        og_desc = pd.get_text("\n", strip=True) if pd else None

    if not og_desc:
        return None, []

    lines = [line.strip() for line in re.split(r"<br\s*/?>|\n", og_desc) if line.strip()]
    bullets = [re.sub(r"^[-•]\s*", "", line) for line in lines if line.startswith(("-", "•"))]
    prose = " ".join(line for line in lines if not line.startswith(("-", "•")))

    if not bullets:
        # some listings run the whole description together with no bullet
        # markers at all -- fall back to a naive sentence split so we still
        # keep *something* for provenance/debugging, even if it's messier
        bullets = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prose) if len(s.strip()) > 3]

    return (prose or None), bullets


def extract_fields(html_text: str, source_file: str, debug: bool = False) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    address_el = soup.find("h1", class_="property-info-address")
    full_address = address_el.get_text(strip=True) if address_el else _meta(soup, "og:title")

    json_ld_addr = _find_json_ld_address(soup)
    addr_parts = _parse_address(full_address, json_ld_addr)
    bed_bath_car = _extract_bed_bath_car(soup)
    description, features_raw = _extract_description_and_features(soup)
    features_text_lower = " | ".join(features_raw).lower() + " " + (description or "").lower()

    price_text = _extract_price(soup)
    if not price_text:
        # fall back to the meta description, e.g. "...$1,150 per week..."
        meta_desc = _meta(soup, "description") or ""
        m = re.search(r"\$[\d,]+(?:\.\d+)?\s*per week", meta_desc)
        price_text = m.group(0) if m else None

    canonical = soup.find("link", rel="canonical")
    canonical_url = canonical.get("href") if canonical else None
    id_match = re.search(r"-(\d+)/?$", canonical_url) if canonical_url else None
    listing_id = id_match.group(1) if id_match else Path(source_file).stem

    fields = {
        "listing_id": listing_id,
        "url": canonical_url,
        "address": full_address,
        "suburb": addr_parts.get("suburb"),
        "postcode": addr_parts.get("postcode"),
        "lat": None,   # filled in later by ingest.geocode_commute
        "lon": None,
        "property_type": _extract_property_type(soup),
        "bedrooms": bed_bath_car["bedrooms"],
        "bathrooms": bed_bath_car["bathrooms"],
        "parking_spaces": bed_bath_car["parking_spaces"],
        "land_size_sqm": None,   # rarely present on rental listings -- see module docstring
        "floor_size_sqm": None,
        "features_raw": json.dumps(features_raw),
        "description": description,
        "weekly_rent_aud": _parse_price(price_text),
        "source_file": source_file,
    }

    for column, keywords in AMENITY_KEYWORDS.items():
        fields[column] = int(any(kw in features_text_lower for kw in keywords))

    if debug:
        print(f"--- {source_file} ---")
        for key in ("address", "suburb", "postcode", "property_type", "bedrooms", "bathrooms",
                    "parking_spaces", "weekly_rent_aud"):
            print(f"  {key}: {fields[key]}")
        print(f"  features_raw ({len(features_raw)}): {features_raw}")
        amenities_on = [k for k in AMENITY_KEYWORDS if fields[k]]
        print(f"  amenities detected: {amenities_on}")
        missing = [k for k in ("address", "property_type", "bedrooms", "bathrooms", "weekly_rent_aud")
                   if fields[k] is None]
        if missing:
            print(f"  WARNING: could not extract: {missing}", file=sys.stderr)

    return fields


def parse_file(path: Path, debug: bool = False) -> dict:
    html_text = path.read_text(encoding="utf-8", errors="ignore")
    return extract_fields(html_text, source_file=path.name, debug=debug)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("html_file", type=Path)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    result = parse_file(args.html_file, debug=args.debug)
    print(json.dumps(result, indent=2, ensure_ascii=False))
