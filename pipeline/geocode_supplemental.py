"""Investigate unmatched CAMS addresses using Census anchors and nearby county points."""

from __future__ import annotations

import argparse
import json
import math
import re
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from pydantic import ValidationError

from api.contracts.geocodes import (
    CENSUS_GEOCODER,
    SEARCH_RADIUS_METERS,
    ApproximateLocation,
    CamsCache,
    CamsLocation,
    SupplementalCache,
    SupplementalResult,
)
from pipeline.geocode_cams import (
    FIELDS,
    address_lookup,
    address_street,
    fetch_candidates,
    query_page,
    standardize,
)

BENCHMARK = "Public_AR_Current"
COUNTIES = {"06037": "Los Angeles", "06071": "San Bernardino", "06111": "Ventura"}
UNIT_TOKEN = re.compile(r"(?:[A-Z]?[0-9][A-Z0-9]*)(?:-[A-Z0-9]+)?")


def civic_address_matches(building_key: str, street: str, locality: str) -> bool:
    normalized = standardize(building_key)
    separated_direction = re.sub(r"^(\d+)([NSEW]) ", r"\1 \2 ", normalized)
    if separated_direction != normalized and separated_direction == f"{street} {locality}":
        return True
    # A single trailing unit token can remain in the building key without a STE prefix.
    prefix = f"{street} "
    suffix = f" {locality}"
    if separated_direction.startswith(prefix) and separated_direction.endswith(suffix):
        unit = separated_direction[len(prefix) : -len(suffix)]
        return UNIT_TOKEN.fullmatch(unit) is not None
    return False


def census_anchor(building_key: str, matches: list[dict]) -> ApproximateLocation | None:
    accepted = {}
    for match in matches:
        address = match["matchedAddress"]
        street, separator, locality = address.partition(",")
        if not separator:
            continue
        strict = standardize(address.replace(",", " ")) == standardize(building_key)
        if not strict and (
            len(matches) != 1
            or not civic_address_matches(
                building_key, standardize(street), standardize(locality.replace(",", " "))
            )
        ):
            continue
        counties = match.get("geographies", {}).get("Counties", [])
        if len(counties) != 1 or counties[0].get("GEOID") not in COUNTIES:
            continue
        geometry = match["coordinates"]
        try:
            point = ApproximateLocation(
                matched_address=address,
                address_basis="full_address" if strict else "civic_address_only",
                county=COUNTIES[counties[0]["GEOID"]],
                tiger_line_id=str(match["tigerLine"]["tigerLineId"]),
                benchmark=BENCHMARK,
                latitude=geometry["y"],
                longitude=geometry["x"],
            )
        except ValidationError:
            return None
        accepted[point.latitude, point.longitude] = point
    return next(iter(accepted.values())) if len(accepted) == 1 else None


def fetch_anchor(building_key: str) -> ApproximateLocation | None:
    params = urlencode({
        "address": building_key,
        "benchmark": BENCHMARK,
        "vintage": "Current_Current",
        "layers": "Counties",
        "format": "json",
    })
    with urlopen(f"{CENSUS_GEOCODER}?{params}", timeout=40) as response:
        matches = json.load(response)["result"]["addressMatches"]
    return census_anchor(building_key, matches)


def distance_meters(origin: ApproximateLocation, latitude: float, longitude: float) -> float:
    lat, other_lat = map(math.radians, (origin.latitude, latitude))
    dlon = math.radians(longitude - origin.longitude)
    a = math.sin((other_lat - lat) / 2) ** 2
    a += math.cos(lat) * math.cos(other_lat) * math.sin(dlon / 2) ** 2
    return 12_742_000 * math.asin(min(1, math.sqrt(a)))


def nearby_features(anchor: ApproximateLocation, lookup: tuple[str, str]) -> list[dict]:
    zip_code, number = lookup
    page = query_page({
        "f": "json",
        "where": f"ZipCode = '{zip_code}' AND Number = '{number}'",
        "outFields": ",".join(FIELDS),
        "geometry": f"{anchor.longitude},{anchor.latitude}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": SEARCH_RADIUS_METERS,
        "units": "esriSRUnit_Meter",
        "inSR": 4326,
        "outSR": 4326,
        "returnGeometry": "true",
    })
    points = page["features"]
    if page.get("exceededTransferLimit"):
        raise ValueError("CAMS radius query returned an incomplete result")
    if points and page["spatialReference"]["wkid"] != 4326:
        raise ValueError("CAMS radius query did not return WGS84")
    return points


def corroborate(
    building_key: str, anchor: ApproximateLocation, nearby: list[dict], all_candidates: list[dict]
) -> SupplementalResult:
    lookup = address_lookup(building_key)
    street = standardize(anchor.matched_address.split(",", 1)[0])
    nearby_ids = {feature["attributes"]["OBJECTID"] for feature in nearby}
    checked_ids = []
    primary_points = {}
    unit_or_conflict = False
    for feature in all_candidates:
        fields = feature["attributes"]
        if (fields.get("ZipCode"), fields.get("Number")) != lookup:
            continue
        if standardize(address_street(fields)) != street:
            continue
        feature_id = fields["OBJECTID"]
        try:
            geometry = feature.get("geometry") or {}
            location = CamsLocation(
                feature_id=feature_id,
                county_record_source=fields.get("Source") or "County source unspecified",
                matched_address=fields.get("FullAddress"),
                confidence="standardized",
                latitude=geometry.get("y"),
                longitude=geometry.get("x"),
            )
        except ValidationError:
            unit_or_conflict = True
            continue
        distance = distance_meters(anchor, location.latitude, location.longitude)
        in_radius = feature_id in nearby_ids and distance <= SEARCH_RADIUS_METERS
        if in_radius:
            checked_ids.append(feature_id)
        if any(fields.get(key) for key in ("UnitName", "UnitType", "FlrName")) or not in_radius:
            unit_or_conflict = True
            continue
        primary_points[location.latitude, location.longitude] = (location, distance)

    if anchor.address_basis == "civic_address_only" and not checked_ids:
        return SupplementalResult(building_key=building_key, reason="no_defensible_anchor")
    if (
        len(primary_points) == 1 and not unit_or_conflict
        and anchor.address_basis == "full_address" and anchor.county == "Los Angeles"
    ):
        verified, distance = next(iter(primary_points.values()))
        return SupplementalResult(
            building_key=building_key, anchor=anchor, verified=verified,
            reason="corroborated_address_point", nearby_matching_feature_ids=sorted(checked_ids),
            verified_distance_meters=distance,
        )
    return SupplementalResult(
        building_key=building_key, anchor=anchor,
        reason="unit_or_conflicting_points" if unit_or_conflict or primary_points
        else "street_interpolation_only",
        nearby_matching_feature_ids=sorted(checked_ids),
    )


def investigate(building_key: str, candidates: dict) -> SupplementalResult:
    lookup = address_lookup(building_key)
    anchor = fetch_anchor(building_key) if lookup else None
    if anchor is None:
        return SupplementalResult(building_key=building_key, reason="no_defensible_anchor")
    return corroborate(
        building_key, anchor, nearby_features(anchor, lookup), candidates.get(lookup, [])
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, default=Path("data/runtime"))
    directory = parser.parse_args().analysis_dir
    verified = CamsCache.model_validate_json((directory / "cams_geocodes.json").read_bytes())
    missing = {
        key: item.building_key for key, item in verified.results.items() if not item.location
    }
    lookups = {pair for key in missing.values() if (pair := address_lookup(key))}
    candidates = defaultdict(list)
    for feature in fetch_candidates(lookups):
        fields = feature["attributes"]
        candidates[fields["ZipCode"], fields["Number"]].append(feature)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(zip(missing, pool.map(
            lambda key: investigate(key, candidates), missing.values()
        ), strict=True))
    cache = SupplementalCache(retrieved_at=datetime.now(UTC), results=results)
    destination = directory / "supplemental_geocodes.json"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=directory, delete=False
    ) as output:
        temporary = Path(output.name)
        output.write(cache.model_dump_json(indent=2, exclude_none=True) + "\n")
    try:
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Investigated {len(results)} previously unmapped addresses")
    print(dict(sorted(Counter(item.reason for item in results.values()).items())))


if __name__ == "__main__":
    main()
