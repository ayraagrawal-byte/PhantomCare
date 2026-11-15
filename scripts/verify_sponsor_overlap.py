"""Read-only check for a genuine same-building CMS + CoStar + Vexcel overlap.

Reads only the published runtime artifacts; makes no network calls and writes nothing
unless --output is given. A building counts as a genuine overlap only if it has an exact
CoStar match AND Vexcel evidence keyed to the same building ID, the Vexcel address equals
the normalized building address, and the independent LA County CAMS address point falls
inside the Vexcel image footprint.

    python -m scripts.verify_sponsor_overlap --analysis-dir data/runtime
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

# pipeline.vexcel_imagery.square_wkt requests an 80 m square (40 m half-width).
VEXCEL_HALF_WIDTH_METERS = 40.0
COSTAR_CAMS_TOLERANCE_METERS = 75.0


def _distance_meters(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


Point = tuple[float, float]


def _axis_offsets_meters(center: Point, point: Point) -> Point:
    north = (point[0] - center[0]) * 111_320
    east = (point[1] - center[1]) * 111_320 * math.cos(math.radians(center[0]))
    return north, east


def _read(root: Path, name: str) -> Any:
    path = root / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def verify(root: Path) -> dict[str, Any]:
    buildings = {item["building_id"]: item for item in _read(root, "building_analysis.json")}
    vexcel = {item["target_id"]: item for item in (_read(root, "vexcel_evidence.json") or [])}
    cams = (_read(root, "cams_geocodes.json") or {}).get("results", {})

    def cams_point(building_id: str) -> tuple[float, float] | None:
        location = (cams.get(building_id) or {}).get("location")
        return (location["latitude"], location["longitude"]) if location else None

    costar_matches = []
    for building_id, building in sorted(buildings.items()):
        if building["costar_match_status"] != "exact_match":
            continue
        context = building.get("building_context") or {}
        record: dict[str, Any] = {
            "building_id": building_id,
            "normalized_address": building["building_key"],
            "costar_property_id": context.get("property_id"),
            "match_status": building["costar_match_status"],
            "hospice_count": building["hospice_count"],
            "review_level": building["priority"]["score"]["level"],
            "matterport_model_ids": context.get("matterport_model_ids", []),
        }
        point = cams_point(building_id)
        if point and building.get("latitude") is not None:
            record["costar_to_cams_meters"] = round(
                _distance_meters((building["latitude"], building["longitude"]), point), 1
            )
            record["costar_coordinates_consistent"] = (
                record["costar_to_cams_meters"] <= COSTAR_CAMS_TOLERANCE_METERS
            )
        costar_matches.append(record)

    vexcel_records = []
    for building_id, evidence in sorted(vexcel.items()):
        building = buildings.get(building_id)
        center = (evidence["latitude"], evidence["longitude"])
        record = {
            "building_id": building_id,
            "vexcel_address": evidence["address"],
            "address_matches_building": bool(building)
            and evidence["address"] == building["building_key"],
            "image_sha256": evidence["image_sha256"],
            "retrieved_at": evidence["retrieved_at"],
            "image_file_present": (image := root / "vexcel" / evidence["image_filename"]).is_file(),
            "image_sha256_verified": image.is_file()
            and hashlib.sha256(image.read_bytes()).hexdigest() == evidence["image_sha256"],
            "costar_match_status": building["costar_match_status"] if building else None,
        }
        point = cams_point(building_id)
        if point:
            north, east = _axis_offsets_meters(center, point)
            record["cams_offset_from_image_center_meters"] = {
                "north": round(north, 1), "east": round(east, 1),
                "distance": round(_distance_meters(center, point), 1),
            }
            record["cams_point_inside_image"] = (
                abs(north) <= VEXCEL_HALF_WIDTH_METERS and abs(east) <= VEXCEL_HALF_WIDTH_METERS
            )
        vexcel_records.append(record)

    vexcel_by_id = {item["building_id"]: item for item in vexcel_records}
    overlaps = [
        {**match, "vexcel": vexcel_by_id[match["building_id"]]}
        for match in costar_matches
        if match["building_id"] in vexcel_by_id
        and vexcel_by_id[match["building_id"]]["address_matches_building"]
        and vexcel_by_id[match["building_id"]]["image_sha256_verified"]
        and vexcel_by_id[match["building_id"]].get("cams_point_inside_image", False)
        and match.get("costar_coordinates_consistent", False)
    ]

    next_actions = []
    if not overlaps:
        for match in costar_matches:
            point = cams_point(match["building_id"])
            if match["building_id"] in vexcel_by_id or not point:
                continue
            next_actions.append(
                {
                    "building_id": match["building_id"],
                    "reason": "Exact CoStar match without Vexcel evidence.",
                    "coordinate_source": "LA County CAMS address point",
                    "command": (
                        "python -m pipeline.vexcel_imagery "
                        f"--target-id {match['building_id']} "
                        f"--address \"{match['normalized_address']}\" "
                        f"--latitude {point[0]} --longitude {point[1]} "
                        "--output-dir data/runtime"
                    ),
                    "required_environment": ["VEXCEL_API_KEY"],
                }
            )

    return {
        "analysis_dir": str(root),
        "building_count": len(buildings),
        "costar_exact_matches": costar_matches,
        "vexcel_evidence": vexcel_records,
        "genuine_overlaps": overlaps,
        "overlap_found": bool(overlaps),
        "next_actions": next_actions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--analysis-dir", type=Path, default=Path("data/runtime"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.analysis_dir)
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
