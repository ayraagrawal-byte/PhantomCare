from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from pipeline.normalize import (
    AddressOverride,
    address_override_key,
    load_overrides,
    normalize_address,
)

ADDRESS_COLUMNS = ("ADDRESS_LINE_1", "ADDRESS_LINE_2", "CITY", "STATE", "ZIP_CODE")


def _value(row: pd.Series, column: str) -> str:
    value = row.get(column, "")
    return "" if pd.isna(value) else str(value)


def normalize_enrollment_addresses(
    enrollments: pd.DataFrame,
    *,
    overrides: dict[str, AddressOverride] | None = None,
) -> pd.DataFrame:
    missing = sorted(set(ADDRESS_COLUMNS) - set(enrollments.columns) - {"ADDRESS_LINE_2"})
    if missing:
        raise ValueError(f"enrollment data is missing address columns: {', '.join(missing)}")

    override_map = overrides or {}
    normalized_rows: list[dict[str, object]] = []
    for _, row in enrollments.iterrows():
        components = {
            "line1": _value(row, "ADDRESS_LINE_1"),
            "line2": _value(row, "ADDRESS_LINE_2"),
            "city": _value(row, "CITY"),
            "state": _value(row, "STATE"),
            "postal_code": _value(row, "ZIP_CODE"),
        }
        key = address_override_key(**components)
        address = normalize_address(**components, override=override_map.get(key))
        normalized_rows.append(
            {
                "ADDRESS_RAW": address.raw,
                "ADDRESS_NORM": address.normalized,
                "BUILDING_KEY": address.building_key,
                "SUITE": address.suite or "",
                "NORMALIZATION_CONFIDENCE": address.confidence,
                "NORMALIZATION_WARNINGS": json.dumps(address.warnings),
            }
        )

    normalized = pd.DataFrame(normalized_rows, index=enrollments.index)
    return pd.concat([enrollments.copy(), normalized], axis=1)


def _building_id(building_key: str) -> str:
    return f"bldg_{hashlib.sha256(building_key.encode('utf-8')).hexdigest()[:16]}"


def group_by_building(enrollments: pd.DataFrame) -> pd.DataFrame:
    required = {"ENROLLMENT_ID", "BUILDING_KEY", "ADDRESS_RAW", "SUITE"}
    missing = sorted(required - set(enrollments.columns))
    if missing:
        raise ValueError(f"normalized enrollment data is missing columns: {', '.join(missing)}")

    grouped = (
        enrollments.groupby("BUILDING_KEY", sort=True, dropna=False)
        .agg(
            HOSPICE_COUNT=("ENROLLMENT_ID", "nunique"),
            SUITE_COUNT=("SUITE", lambda values: len({value for value in values if value})),
            ENROLLMENT_IDS=("ENROLLMENT_ID", lambda values: json.dumps(sorted(set(values)))),
            RAW_ADDRESSES=("ADDRESS_RAW", lambda values: json.dumps(sorted(set(values)))),
            MIN_NORMALIZATION_CONFIDENCE=("NORMALIZATION_CONFIDENCE", "min"),
        )
        .reset_index()
    )
    grouped.insert(0, "BUILDING_ID", grouped["BUILDING_KEY"].map(_building_id))
    return grouped.sort_values(
        ["HOSPICE_COUNT", "BUILDING_KEY"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize CMS addresses and group hospices by building."
    )
    parser.add_argument("--enrollments", type=Path, required=True)
    parser.add_argument("--output-enrollments", type=Path, required=True)
    parser.add_argument("--output-buildings", type=Path, required=True)
    parser.add_argument("--overrides", type=Path)
    args = parser.parse_args()

    enrollments = pd.read_csv(args.enrollments, dtype=str, keep_default_na=False)
    normalized = normalize_enrollment_addresses(
        enrollments,
        overrides=load_overrides(args.overrides),
    )
    buildings = group_by_building(normalized)
    args.output_enrollments.parent.mkdir(parents=True, exist_ok=True)
    args.output_buildings.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(args.output_enrollments, index=False)
    buildings.to_csv(args.output_buildings, index=False)


if __name__ == "__main__":
    main()

