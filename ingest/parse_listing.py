"""Parse one saved realestate.com.au listing HTML file into a feature dict.

Reliable sources on a listing page: `<meta name="description">` /
`<meta property="og:description">` for the summary and feature bullets; a
few stable, non-hashed CSS classes (`property-info-address`,
`property-info__primary-features` for bed/bath/car, `property-price`);
`application/ld+json` for structured suburb/postcode. The
`window.ArgonautExchange` blob some articles point to as "the" data
source is unreliable on a page reached by clicking through from a search
list; it can hold a leftover cache from an unrelated earlier search.

Rentals routinely omit land size / floor size entirely, which is the
whole reason README.md's "Phase 2" (matching sale listings by address)
is on the roadmap.

Run with --debug on a file to see every extracted value:

    python -m ingest.parse_listing path/to/saved_listing.html --debug
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from ingest.schema import AMENITY_KEYWORDS

_NUM_RE = re.compile(r"[-+]?\d*\.?\d+")
_AMENITY_RES = {
    column: re.compile(r"\b(?:" + "|".join(patterns) + ")")
    for column, patterns in AMENITY_KEYWORDS.items()
}
_NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "six": "6", "nine": "9", "twelve": "12", "eighteen": "18"}
_LEASE_MONTHS_RES = [
    re.compile(r"(\d{1,2})[\s-]*months?\s+(?:fixed\s+)?(?:lease|tenancy|term)"),
    re.compile(r"(?:lease|tenancy)\s+(?:term\s+)?(?:of\s+)?(\d{1,2})[\s-]*months?"),
]
_LEASE_YEARS_RE = re.compile(r"(\d)[\s-]*years?\s+(?:fixed\s+)?(?:lease|tenancy)")
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


def _extract_primary_features(soup: BeautifulSoup) -> dict:
    """Bed/bath/car icons plus land/building size when the page shows
    them. The site omits the car icon entirely when there's no parking, so
    a found feature list with no car entry means 0, not unknown."""
    out = {"bedrooms": None, "bathrooms": None, "parking_spaces": None,
           "land_size_sqm": None, "floor_size_sqm": None}
    features_ul = soup.find("ul", class_="property-info__primary-features")
    if not features_ul:
        return out
    out["parking_spaces"] = 0
    for li in features_ul.find_all("li"):
        label = (li.get("aria-label") or "").lower()
        if "bedroom" in label:
            out["bedrooms"] = _to_int(label)
        elif "bathroom" in label:
            out["bathrooms"] = _to_int(label)
        elif "car space" in label or "carspace" in label:
            out["parking_spaces"] = _to_int(label)
        elif "land size" in label:
            out["land_size_sqm"] = _to_float(label)
        elif "building size" in label:
            out["floor_size_sqm"] = _to_float(label)
    return out


def _extract_property_type(soup: BeautifulSoup) -> str | None:
    """The type ("House", "Townhouse", ...) is the token after the "•"
    separator; everything before it is numbers (beds/baths/cars/size)."""
    container = soup.find("div", class_="property-info__property-attributes")
    if not container:
        return None
    tokens = [t.strip() for t in container.get_text("|", strip=True).split("|")]
    if "•" in tokens and tokens.index("•") + 1 < len(tokens):
        return tokens[tokens.index("•") + 1]
    return None


def _extract_available_from(soup: BeautifulSoup, captured_on: date) -> str | None:
    """'Available 30 Sep 2026' / 'Available now' -> ISO date. "now" means
    the day the page was saved."""
    footer = soup.find(class_="property-info__footer-content")
    m = re.search(r"Available\s+(now|\d{1,2} \w{3} \d{4})", footer.get_text(" ", strip=True)) if footer else None
    if not m:
        return None
    if m.group(1) == "now":
        return captured_on.isoformat()
    try:
        return datetime.strptime(m.group(1), "%d %b %Y").date().isoformat()
    except ValueError:
        return None


def _extract_lease_term_months(text_lower: str) -> int | None:
    """'6 months lease only' / '12 month lease term' / 'lease of 12 months'
    -> months. If several terms are offered, the longest (what a
    min_lease_term_months hard filter cares about)."""
    text = re.sub(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b", lambda m: _NUMBER_WORDS[m.group(1)], text_lower)
    months = [int(m.group(1)) for r in _LEASE_MONTHS_RES for m in r.finditer(text)]
    months += [int(m.group(1)) * 12 for m in _LEASE_YEARS_RE.finditer(text)]
    return max(months) if months else None


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
        # markers at all; fall back to a naive sentence split so we still
        # keep *something* for provenance/debugging, even if it's messier
        bullets = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prose) if len(s.strip()) > 3]

    return (prose or None), bullets


def extract_fields(html_text: str, source_file: str, captured_on: date | None = None,
                   debug: bool = False) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    address_el = soup.find("h1", class_="property-info-address")
    full_address = address_el.get_text(strip=True) if address_el else _meta(soup, "og:title")

    json_ld_addr = _find_json_ld_address(soup)
    addr_parts = _parse_address(full_address, json_ld_addr)
    primary = _extract_primary_features(soup)
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
        **primary,  # bed/bath/car, and land/floor size when shown (rarely, for rentals)
        "features_raw": json.dumps(features_raw),
        "description": description,
        "weekly_rent_aud": _parse_price(price_text),
        "lease_term_months": _extract_lease_term_months(features_text_lower),
        "available_from": _extract_available_from(soup, captured_on or date.today()),
        "source_file": source_file,
    }

    for column, pattern in _AMENITY_RES.items():
        fields[column] = int(bool(pattern.search(features_text_lower)))

    if debug:
        print(f"--- {source_file} ---")
        for key in ("address", "suburb", "postcode", "property_type", "bedrooms", "bathrooms",
                    "parking_spaces", "land_size_sqm", "floor_size_sqm", "weekly_rent_aud",
                    "lease_term_months", "available_from"):
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
    # The file's modified time stands in for when it was saved, for "Available now".
    captured_on = date.fromtimestamp(path.stat().st_mtime)
    return extract_fields(html_text, source_file=path.name, captured_on=captured_on, debug=debug)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("html_file", type=Path)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    result = parse_file(args.html_file, debug=args.debug)
    print(json.dumps(result, indent=2, ensure_ascii=False))
