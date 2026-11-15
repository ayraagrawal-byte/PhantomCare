"""Build an offline address-point cache from LA County's public CAMS layer."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from pydantic import ValidationError

from api.contracts.geocodes import CAMS_LAYER, CamsCache, CamsLocation, CamsResult
from pipeline.normalize import DIRECTIONALS, STREET_SUFFIXES

ADDRESS = re.compile(r"(?P<number>[0-9]+)(?=[A-Z ]).+ CA (?P<zip>[0-9]{5})")
COMMUNITIES = ("LegalComm", "PostComm1", "PostComm2", "PostComm3", "OtherComm1", "OtherComm2")
# Additional equivalent spellings from USPS Publication 28, appendix C1.
SUFFIXES = {**STREET_SUFFIXES, "AV": "AVE", "WY": "WAY", "CANYON": "CYN", "TRAIL": "TRL"}
FIELDS = (
    "OBJECTID", "Number", "NumPrefix", "NumberSuffix", "NumSuffix", "FullName", "FullAddress",
    "ZipCode", "UnitType", "UnitName", "FlrName", "Source", *COMMUNITIES,
)
BATCH_SIZE = 30
PAGE_SIZE = 1000


def clean(value: str) -> str:
    return " ".join(value.upper().split())


def standardize(value: str) -> str:
    tokens = clean(value.replace(".", "")).split()
    return " ".join(DIRECTIONALS.get(token, SUFFIXES.get(token, token)) for token in tokens)


def address_lookup(building_key: str) -> tuple[str, str] | None:
    match = ADDRESS.fullmatch(clean(building_key))
    return (match["zip"], match["number"]) if match else None


def address_street(attributes: dict) -> str:
    number = attributes.get("NumberSuffix")
    if not number:
        number = " ".join(filter(None, (attributes.get("Number"), attributes.get("NumSuffix"))))
    return " ".join(filter(None, (attributes.get("NumPrefix"), number, attributes.get("FullName"))))


def query_page(params: dict) -> dict:
    url = f"{CAMS_LAYER}/query?{urlencode(params)}"
    for attempt in range(3):
        try:
            with urlopen(url, timeout=40) as response:
                page = json.load(response)
            if "error" in page:
                raise RuntimeError(f"CAMS query failed: {page['error'].get('message')}")
            return page
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError("CAMS query retry limit reached")


def fetch_candidates(lookups: set[tuple[str, str]]) -> Iterator[dict]:
    ordered = sorted(lookups)
    for start in range(0, len(ordered), BATCH_SIZE):
        batch = ordered[start : start + BATCH_SIZE]
        numbers_by_zip: dict[str, list[str]] = defaultdict(list)
        for zip_code, number in batch:
            numbers_by_zip[zip_code].append(f"'{number}'")
        where = " OR ".join(
            f"(ZipCode = '{zip_code}' AND Number IN ({','.join(numbers)}))"
            for zip_code, numbers in numbers_by_zip.items()
        )
        offset = 0
        seen: set[int] = set()
        while True:
            page = query_page({
                "f": "json", "where": where, "outFields": ",".join(FIELDS), "outSR": 4326,
                "returnGeometry": "true", "orderByFields": "OBJECTID ASC",
                "resultOffset": offset, "resultRecordCount": PAGE_SIZE,
            })
            features = page["features"]
            if features and page.get("spatialReference", {}).get("wkid") != 4326:
                raise ValueError("CAMS did not return WGS84 geometry")
            ids = {item["attributes"]["OBJECTID"] for item in features}
            if len(ids) != len(features) or seen.intersection(ids):
                raise ValueError("CAMS returned duplicate records while paging")
            seen.update(ids)
            yield from features
            if not page.get("exceededTransferLimit"):
                break
            if not features:
                raise ValueError("CAMS returned an incomplete empty page")
            offset += len(features)


def match_address(building_key: str, features: Iterable[dict]) -> CamsResult:
    lookup = address_lookup(building_key)
    if lookup is None:
        return CamsResult(building_key=building_key, reason="unsupported_address")
    zip_code, number = lookup
    # The input key has no street/city separator. Compare the complete address with
    # every community alias explicitly supplied on the candidate CAMS record.
    address = clean(building_key).removesuffix(f" CA {zip_code}")
    normalized = standardize(address)
    exact: list[dict] = []
    standardized: list[dict] = []
    street_matched = unit_matched = False
    for feature in features:
        fields = feature["attributes"]
        if (fields.get("ZipCode"), fields.get("Number")) != (zip_code, number):
            continue
        street = standardize(address_street(fields))
        if not street or not normalized.startswith(f"{street} "):
            continue
        street_matched = True
        communities = {standardize(fields[key]) for key in COMMUNITIES if fields.get(key)}
        if normalized.removeprefix(f"{street} ") not in communities:
            continue
        if any(fields.get(key) for key in ("UnitType", "UnitName", "FlrName")):
            unit_matched = True
            continue
        official_address = clean(fields.get("FullAddress") or "")
        if official_address == f"{address} {zip_code}":
            exact.append(feature)
        else:
            standardized.append(feature)

    if not (exact or standardized):
        reason = (
            "unit_records_only" if unit_matched else
            "community_mismatch" if street_matched else "no_address_match"
        )
        return CamsResult(building_key=building_key, reason=reason)

    accepted: list[CamsLocation] = []
    try:
        for confidence, candidates in (("exact", exact), ("standardized", standardized)):
            for feature in candidates:
                fields = feature["attributes"]
                point = feature.get("geometry") or {}
                accepted.append(CamsLocation(
                    feature_id=fields["OBJECTID"],
                    county_record_source=fields.get("Source") or "County source unspecified",
                    matched_address=fields.get("FullAddress"),
                    confidence=confidence,
                    latitude=point.get("y"),
                    longitude=point.get("x"),
                ))
    except ValidationError:
        return CamsResult(building_key=building_key, reason="invalid_geometry")
    if len({(point.latitude, point.longitude) for point in accepted}) != 1:
        return CamsResult(building_key=building_key, reason="ambiguous_points")
    # Coincident duplicate records have the same location. Prefer a literal
    # match and use the feature ID as a reproducible tie-breaker.
    location = min(accepted, key=lambda point: (point.confidence != "exact", point.feature_id))
    return CamsResult(building_key=building_key, location=location)


def build_cache(buildings: list[dict]) -> CamsCache:
    lookups = {
        lookup for building in buildings if (lookup := address_lookup(building["building_key"]))
    }
    candidates: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for feature in fetch_candidates(lookups):
        fields = feature["attributes"]
        candidates[fields["ZipCode"], fields["Number"]].append(feature)
    results = {
        building["building_id"]: match_address(
            building["building_key"], candidates.get(address_lookup(building["building_key"]), ())
        )
        for building in buildings
    }
    if len(results) != len(buildings):
        raise ValueError("Analysis artifact contains duplicate building IDs")
    return CamsCache(source_url=CAMS_LAYER, retrieved_at=datetime.now(UTC), results=results)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, default=Path("data/runtime"))
    args = parser.parse_args()
    source = args.analysis_dir / "building_analysis.json"
    buildings = json.loads(source.read_text(encoding="utf-8"))
    cache = build_cache(buildings)
    destination = args.analysis_dir / "cams_geocodes.json"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, delete=False
    ) as output:
        temporary = Path(output.name)
        output.write(cache.model_dump_json(indent=2, exclude_none=True) + "\n")
    try:
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    totals = Counter(
        result.location.confidence if result.location else result.reason
        for result in cache.results.values()
    )
    print(f"CAMS matched {totals['exact'] + totals['standardized']} of {len(buildings)} buildings")
    for name, count in sorted(totals.items()):
        print(f"{name}: {count}")


if __name__ == "__main__":
    main()
