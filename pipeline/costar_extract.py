from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline.normalize import normalize_address


class CostarExtractError(ValueError):
    """Raised when the CoStar data extract is missing or malformed."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CostarExtractError(f"Unable to read {path}: {error}") from error
    if not isinstance(payload, dict):
        raise CostarExtractError(f"Expected a JSON object in {path}")
    return payload


def _line_records(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    yield line_number, line, json.loads(line)
                except json.JSONDecodeError as error:
                    raise CostarExtractError(
                        f"Invalid JSON in {path} at line {line_number}: {error}"
                    ) from error


def _address_key(address: dict[str, Any]) -> str:
    street = " ".join(
        str(value)
        for value in (
            address.get("streetNumber"),
            address.get("streetName"),
            address.get("streetType"),
        )
        if value not in (None, "")
    )
    return normalize_address(
        line1=street,
        city=str(address.get("city") or ""),
        state=str(address.get("state") or ""),
        postal_code=str(address.get("postcode") or ""),
    ).building_key


class CostarExtract:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.properties_path = self.root / "data" / "commercial-property.jsonl"
        self.occupancies_path = self.root / "data" / "location-occupancy.jsonl"
        self.models_path = self.root / "commercial-properties.csv"
        self.enums_path = self.root / "schemas" / "enums.json"
        for path in (
            self.properties_path,
            self.occupancies_path,
            self.models_path,
            self.enums_path,
        ):
            if not path.exists():
                raise CostarExtractError(f"Required CoStar extract file is missing: {path}")

        self.enums = _read_json(self.enums_path)
        self.occupancy_counts = self._load_occupancy_counts()
        self.matterport_models = self._load_matterport_models()
        self.properties = self._load_properties()

    def _load_occupancy_counts(self) -> dict[int, dict[str, int]]:
        records: dict[int, int] = defaultdict(int)
        tenants: dict[int, set[int]] = defaultdict(set)
        for _, _, row in _line_records(self.occupancies_path):
            property_id = row.get("propertyId")
            if property_id is None:
                continue
            records[int(property_id)] += 1
            tenant_id = row.get("tenantLocationId")
            if tenant_id is not None:
                tenants[int(property_id)].add(int(tenant_id))
        return {
            property_id: {
                "occupancy_record_count": count,
                "unique_tenant_location_count": len(tenants[property_id]),
            }
            for property_id, count in records.items()
        }

    def _load_matterport_models(self) -> dict[int, list[str]]:
        frame = pd.read_csv(self.models_path, dtype=str, keep_default_na=False)
        required = {"PropertyId", "MatterportModelId"}
        if missing := required - set(frame.columns):
            raise CostarExtractError(
                f"commercial-properties.csv is missing: {', '.join(sorted(missing))}"
            )
        models: dict[int, list[str]] = {}
        for property_id, group in frame.groupby("PropertyId"):
            models[int(property_id)] = sorted(
                {value for value in group["MatterportModelId"] if value}
            )
        return models

    def _decode(self, enum_name: str, value: Any) -> str | None:
        if value is None:
            return None
        return self.enums.get(enum_name, {}).get(str(value), f"Unknown({value})")

    def _load_properties(self) -> dict[str, list[dict[str, Any]]]:
        by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for line_number, raw_line, row in _line_records(self.properties_path):
            address = row.get("primaryAddress")
            if not isinstance(address, dict):
                continue
            property_id = int(row["id"])
            record = {
                "property_id": property_id,
                "building_key": _address_key(address),
                "address": address,
                "latitude": address.get("latitude"),
                "longitude": address.get("longitude"),
                "property_type": self._decode("PropertyType", row.get("propertyType")),
                "property_subtype": self._decode(
                    "PropertySubtype", row.get("propertySubtype")
                ),
                "building_class": self._decode(
                    "BuildingClass", row.get("buildingClass")
                ),
                "building_rating": row.get("buildingRating"),
                "gross_building_area_sqft": row.get("grossBuildingAreaSquareFeet"),
                "rentable_building_area_sqft": row.get(
                    "rentableBuildingAreaSquareFeet"
                ),
                "stories_above_grade": row.get("numStoriesAboveGrade"),
                "floor_count": len(row.get("floors") or []),
                "matterport_model_ids": self.matterport_models.get(property_id, []),
                **self.occupancy_counts.get(
                    property_id,
                    {"occupancy_record_count": 0, "unique_tenant_location_count": 0},
                ),
                "occupancy_scope": "current_or_past_records; not a current tenant count",
                "source": {
                    "dataset": "commercial-property",
                    "line_number": line_number,
                    "row_sha256": hashlib.sha256(raw_line.encode()).hexdigest(),
                },
            }
            by_address[record["building_key"]].append(record)
        return dict(by_address)

    def lookup(self, building_key: str) -> list[dict[str, Any]]:
        return self.properties.get(building_key, [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Match buildings to the CoStar data extract.")
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--buildings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    extract = CostarExtract(args.kit)
    buildings = pd.read_csv(args.buildings, dtype=str, keep_default_na=False)
    matches = [
        {
            "building_id": row.get("BUILDING_ID"),
            "building_key": row["BUILDING_KEY"],
            "matches": extract.lookup(row["BUILDING_KEY"]),
        }
        for _, row in buildings.iterrows()
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(matches, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

