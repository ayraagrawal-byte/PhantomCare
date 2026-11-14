from __future__ import annotations

import json

import pandas as pd

from pipeline.group_buildings import group_by_building, normalize_enrollment_addresses
from pipeline.normalize import AddressOverride, address_override_key, normalize_address


def test_equivalent_street_variants_share_building_key() -> None:
    street = normalize_address(
        line1="14545 Friar Street, Suite 210",
        city="Van Nuys",
        state="CA",
        postal_code="91411-1234",
    )
    abbreviated = normalize_address(
        line1="14545 FRIAR ST",
        line2="STE 311",
        city="VAN NUYS",
        state="ca",
        postal_code="91411",
    )

    assert street.building_key == abbreviated.building_key
    assert street.suite == "210"
    assert abbreviated.suite == "311"


def test_different_street_numbers_never_group_together() -> None:
    first = normalize_address(
        line1="100 Main Street",
        city="Los Angeles",
        state="CA",
        postal_code="90012",
    )
    second = normalize_address(
        line1="102 Main St",
        city="Los Angeles",
        state="CA",
        postal_code="90012",
    )

    assert first.building_key != second.building_key


def test_missing_street_number_reduces_confidence() -> None:
    address = normalize_address(
        line1="Main Street",
        city="Los Angeles",
        state="CA",
        postal_code="90012",
    )

    assert address.confidence == 0.8
    assert "street number missing or unrecognized" in address.warnings


def test_manual_override_is_exact_and_auditable() -> None:
    key = address_override_key(
        line1="14545 Friar St",
        line2="Suite 210",
        city="Van Nuys",
        state="CA",
        postal_code="91411",
    )
    frame = pd.DataFrame(
        [
            {
                "ENROLLMENT_ID": "E-1",
                "ADDRESS_LINE_1": "14545 Friar St",
                "ADDRESS_LINE_2": "Suite 210",
                "CITY": "Van Nuys",
                "STATE": "CA",
                "ZIP_CODE": "91411",
            }
        ]
    )

    normalized = normalize_enrollment_addresses(
        frame,
        overrides={
            key: AddressOverride(
                building_key="REVIEWED:14545 FRIAR ST VAN NUYS CA 91411",
                note="top-50 manual review",
            )
        },
    )

    assert normalized.loc[0, "BUILDING_KEY"].startswith("REVIEWED:")
    assert "top-50 manual review" in normalized.loc[0, "NORMALIZATION_WARNINGS"]


def test_grouping_counts_unique_enrollments_and_suites() -> None:
    frame = pd.DataFrame(
        [
            {
                "ENROLLMENT_ID": "E-1",
                "ADDRESS_LINE_1": "14545 Friar Street",
                "ADDRESS_LINE_2": "Suite 210",
                "CITY": "Van Nuys",
                "STATE": "CA",
                "ZIP_CODE": "91411",
            },
            {
                "ENROLLMENT_ID": "E-2",
                "ADDRESS_LINE_1": "14545 Friar St Ste 311",
                "ADDRESS_LINE_2": "",
                "CITY": "Van Nuys",
                "STATE": "CA",
                "ZIP_CODE": "91411-1234",
            },
            {
                "ENROLLMENT_ID": "E-2",
                "ADDRESS_LINE_1": "14545 Friar St Ste 311",
                "ADDRESS_LINE_2": "",
                "CITY": "Van Nuys",
                "STATE": "CA",
                "ZIP_CODE": "91411",
            },
            {
                "ENROLLMENT_ID": "E-3",
                "ADDRESS_LINE_1": "102 Main St",
                "ADDRESS_LINE_2": "",
                "CITY": "Los Angeles",
                "STATE": "CA",
                "ZIP_CODE": "90012",
            },
        ]
    )

    normalized = normalize_enrollment_addresses(frame)
    buildings = group_by_building(normalized)

    assert len(buildings) == 2
    assert buildings.loc[0, "HOSPICE_COUNT"] == 2
    assert buildings.loc[0, "SUITE_COUNT"] == 2
    assert json.loads(buildings.loc[0, "ENROLLMENT_IDS"]) == ["E-1", "E-2"]
    assert buildings.loc[0, "BUILDING_ID"].startswith("bldg_")

