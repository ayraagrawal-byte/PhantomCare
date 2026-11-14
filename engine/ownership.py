from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from engine.indicators import OwnershipMetrics


class OwnershipDataError(ValueError):
    """Raised when ownership inputs cannot support a defensible network."""


@dataclass(frozen=True)
class OwnerNode:
    owner_key: str
    display_name: str
    owner_type: str
    is_masked: bool
    hospice_count: int


@dataclass(frozen=True)
class OwnershipEdge:
    owner_key: str
    enrollment_id: str
    ownership_percent: float | None
    source_row_hash: str | None


@dataclass(frozen=True)
class BuildingOwnership:
    building_id: str
    metrics: OwnershipMetrics
    owner_keys: tuple[str, ...]


@dataclass(frozen=True)
class OwnershipNetwork:
    owners: tuple[OwnerNode, ...]
    edges: tuple[OwnershipEdge, ...]
    buildings: tuple[BuildingOwnership, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


OWNER_ADDRESS_COLUMNS = (
    "OWNER_ADDRESS_LINE_1",
    "OWNER_ADDRESS_LINE_2",
    "OWNER_CITY",
    "OWNER_STATE",
    "OWNER_ZIP_CODE",
)


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _digest(prefix: str, value: str, *, length: int = 16) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _is_individual(value: object) -> bool:
    normalized = _text(value).upper().replace("_", " ")
    return normalized in {"I", "INDIVIDUAL", "PERSON"}


def _organization_name(row: pd.Series, owner_key: str) -> str:
    name = _text(row.get("OWNER_ORGANIZATION_NAME"))
    return name or f"Organization {owner_key[-8:]}"


def _address_fingerprint(row: pd.Series) -> str | None:
    parts = [" ".join(_text(row.get(column)).upper().split()) for column in OWNER_ADDRESS_COLUMNS]
    normalized = "|".join(parts)
    if not normalized.replace("|", ""):
        return None
    return _digest("addr", normalized)


def _percentage(value: object) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        percentage = float(text.rstrip("%"))
    except ValueError as error:
        raise OwnershipDataError(f"invalid ownership percentage: {text}") from error
    if not 0 <= percentage <= 100:
        raise OwnershipDataError(f"ownership percentage outside 0-100: {text}")
    return percentage


def _enrollment_buildings(
    enrollments: pd.DataFrame, buildings: pd.DataFrame
) -> dict[str, str]:
    if "BUILDING_KEY" in enrollments.columns and "BUILDING_ID" in buildings.columns:
        key_to_id = dict(zip(buildings["BUILDING_KEY"], buildings["BUILDING_ID"], strict=False))
        return {
            _text(row["ENROLLMENT_ID"]): _text(key_to_id.get(row["BUILDING_KEY"]))
            for _, row in enrollments.iterrows()
            if _text(key_to_id.get(row["BUILDING_KEY"]))
        }

    if {"BUILDING_ID", "ENROLLMENT_IDS"} <= set(buildings.columns):
        result: dict[str, str] = {}
        for _, row in buildings.iterrows():
            try:
                enrollment_ids = json.loads(_text(row["ENROLLMENT_IDS"]))
            except json.JSONDecodeError as error:
                raise OwnershipDataError("invalid ENROLLMENT_IDS JSON in buildings") from error
            for enrollment_id in enrollment_ids:
                result[str(enrollment_id)] = _text(row["BUILDING_ID"])
        return result

    raise OwnershipDataError(
        "inputs need BUILDING_KEY linkage or BUILDING_ID plus ENROLLMENT_IDS"
    )


def build_ownership_network(
    owners: pd.DataFrame,
    enrollments: pd.DataFrame,
    buildings: pd.DataFrame,
) -> OwnershipNetwork:
    required_owner = {"ENROLLMENT_ID", "OWNER_ASSOCIATE_ID", "OWNER_TYPE"}
    missing_owner = sorted(required_owner - set(owners.columns))
    if missing_owner:
        raise OwnershipDataError(f"owners missing columns: {', '.join(missing_owner)}")
    if "ENROLLMENT_ID" not in enrollments.columns:
        raise OwnershipDataError("enrollments missing column: ENROLLMENT_ID")

    enrollment_to_building = _enrollment_buildings(enrollments, buildings)
    allowed_enrollments = set(enrollment_to_building)
    filtered = owners.loc[owners["ENROLLMENT_ID"].astype(str).isin(allowed_enrollments)].copy()
    filtered = filtered.drop_duplicates(subset=["ENROLLMENT_ID", "OWNER_ASSOCIATE_ID"])

    owner_hospices: dict[str, set[str]] = {}
    owner_addresses: dict[str, set[str]] = {}
    owner_rows: dict[str, pd.Series] = {}
    edges: list[OwnershipEdge] = []
    enrollment_owners: dict[str, set[str]] = {}

    for _, row in filtered.iterrows():
        raw_owner_id = _text(row["OWNER_ASSOCIATE_ID"])
        enrollment_id = _text(row["ENROLLMENT_ID"])
        if not raw_owner_id or not enrollment_id:
            continue
        owner_key = _digest("owner", raw_owner_id)
        owner_rows.setdefault(owner_key, row)
        owner_hospices.setdefault(owner_key, set()).add(enrollment_id)
        enrollment_owners.setdefault(enrollment_id, set()).add(owner_key)
        address = _address_fingerprint(row)
        if address:
            owner_addresses.setdefault(owner_key, set()).add(address)
        edges.append(
            OwnershipEdge(
                owner_key=owner_key,
                enrollment_id=enrollment_id,
                ownership_percent=_percentage(row.get("PERCENTAGE_OWNERSHIP")),
                source_row_hash=_text(row.get("_ROW_HASH")) or None,
            )
        )

    nodes = []
    for owner_key in sorted(owner_rows):
        row = owner_rows[owner_key]
        individual = _is_individual(row["OWNER_TYPE"])
        nodes.append(
            OwnerNode(
                owner_key=owner_key,
                display_name=(
                    f"Individual owner {owner_key[-8:]}"
                    if individual
                    else _organization_name(row, owner_key)
                ),
                owner_type="individual" if individual else "organization",
                is_masked=individual,
                hospice_count=len(owner_hospices[owner_key]),
            )
        )

    address_to_owners: dict[str, set[str]] = {}
    for owner_key, addresses in owner_addresses.items():
        for address in addresses:
            address_to_owners.setdefault(address, set()).add(owner_key)

    building_results = []
    for building_id in sorted(set(enrollment_to_building.values())):
        enrollment_ids = {
            enrollment_id
            for enrollment_id, linked_building in enrollment_to_building.items()
            if linked_building == building_id
        }
        linked_owners = set().union(
            *(enrollment_owners.get(enrollment_id, set()) for enrollment_id in enrollment_ids)
        )
        shared_owners = {
            owner_key for owner_key in linked_owners if len(owner_hospices[owner_key]) > 1
        }
        linked_addresses = {
            address
            for owner_key in linked_owners
            for address in owner_addresses.get(owner_key, set())
        }
        shared_address_count = sum(
            1
            for address in linked_addresses
            if len(address_to_owners.get(address, set())) > 1
        )
        building_results.append(
            BuildingOwnership(
                building_id=building_id,
                metrics=OwnershipMetrics(
                    max_hospices_per_owner=max(
                        (len(owner_hospices[key]) for key in linked_owners), default=0
                    ),
                    owners_shared_across_hospices=len(shared_owners),
                    shared_owner_address_count=shared_address_count,
                ),
                owner_keys=tuple(sorted(linked_owners)),
            )
        )

    return OwnershipNetwork(
        owners=tuple(nodes),
        edges=tuple(sorted(edges, key=lambda edge: (edge.owner_key, edge.enrollment_id))),
        buildings=tuple(building_results),
        limitations=(
            "Shared ownership can be normal for legitimate multi-entity healthcare groups.",
            "The network is a review aid and does not establish fraud or improper conduct.",
            "Individual names and all source owner identifiers are excluded from output.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a masked CMS hospice ownership network.")
    parser.add_argument("--owners", type=Path, required=True)
    parser.add_argument("--enrollments", type=Path, required=True)
    parser.add_argument("--buildings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    network = build_ownership_network(
        pd.read_csv(args.owners, dtype=str, keep_default_na=False),
        pd.read_csv(args.enrollments, dtype=str, keep_default_na=False),
        pd.read_csv(args.buildings, dtype=str, keep_default_na=False),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(network.to_dict(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
