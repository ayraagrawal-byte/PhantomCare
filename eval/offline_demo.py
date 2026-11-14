from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from agent.investigation import investigate_building
from api.schemas import BuildingAnalysisResponse
from pipeline.analysis import run_analysis, write_analysis

DEMO_TIME = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
HOTSPOT_ADDRESS = "100 REVIEW ST LOS ANGELES CA 90012"
PRIVATE_FIXTURE_NAME = "Synthetic Private Person"
PRIVATE_FIXTURE_ID = "SYNTHETIC-PRIVATE-OWNER-ID"


@dataclass(frozen=True)
class DemoReport:
    status: str
    generated_at: str
    building_count: int
    high_priority_count: int
    completed_case_count: int
    early_stop_count: int
    expected_hotspot_found: bool
    expected_hotspot_high_priority: bool
    expected_hotspot_has_case: bool
    private_owner_data_absent: bool
    disclaimer_present: bool

    @property
    def passed(self) -> bool:
        return all(
            (
                self.expected_hotspot_found,
                self.expected_hotspot_high_priority,
                self.expected_hotspot_has_case,
                self.private_owner_data_absent,
                self.disclaimer_present,
            )
        )


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def create_synthetic_fixture(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    enrollments: list[dict[str, str]] = []
    owners: list[dict[str, str]] = []
    for number in range(1, 18):
        enrollment_id = f"DEMO-{number:03d}"
        if number <= 12:
            address = "100 Review Street"
            line2 = f"Suite {number}"
        elif number <= 16:
            address = "200 Health Avenue"
            line2 = f"Suite {number}"
        else:
            address = "300 Solo Road"
            line2 = ""
        enrollments.append(
            {
                "ENROLLMENT ID": enrollment_id,
                "NPI": f"9000000{number:03d}",
                "CCN": f"05{number:04d}",
                "ORGANIZATION NAME": f"Synthetic Hospice {number}",
                "ADDRESS LINE 1": address,
                "ADDRESS LINE 2": line2,
                "CITY": "Los Angeles",
                "STATE": "CA",
                "ZIP CODE": "90012",
                "COUNTY": "Los Angeles",
            }
        )
        owners.append(
            {
                "ENROLLMENT ID": enrollment_id,
                "ASSOCIATE ID - OWNER": (
                    PRIVATE_FIXTURE_ID if number <= 12 else f"DEMO-ORG-{number}"
                ),
                "TYPE - OWNER": "I" if number <= 12 else "O",
                "FIRST NAME - OWNER": PRIVATE_FIXTURE_NAME if number <= 12 else "",
                "ORGANIZATION NAME - OWNER": (
                    "" if number <= 12 else f"Synthetic Care Group {number}"
                ),
                "PERCENTAGE OWNERSHIP": "100",
            }
        )

    enrollment_path = root / "hospice_enrollments.csv"
    owner_path = root / "hospice_owners.csv"
    additional_path = root / "hospice_additional_addresses.csv"
    _write_csv(enrollment_path, enrollments, list(enrollments[0]))
    _write_csv(owner_path, owners, list(owners[0]))
    _write_csv(
        additional_path,
        [],
        ["ENROLLMENT ID", "ADDRESS LINE 1", "CITY", "STATE", "ZIP CODE"],
    )
    kit = root / "synthetic_costar_kit"
    _create_synthetic_costar_kit(kit)
    return {
        "enrollments": enrollment_path,
        "owners": owner_path,
        "additional": additional_path,
        "costar_kit": kit,
    }


def _create_synthetic_costar_kit(root: Path) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "schemas").mkdir(parents=True, exist_ok=True)
    property_record = {
        "id": 1001,
        "propertyType": 1,
        "propertySubtype": 10,
        "buildingClass": 2,
        "buildingName": "Synthetic Review Business Center",
        "grossBuildingAreaSquareFeet": 2600,
        "rentableBuildingAreaSquareFeet": 2400,
        "numStoriesAboveGrade": 1,
        "floors": [{"id": 1}],
        "primaryAddress": {
            "streetNumber": "100",
            "streetName": "Review",
            "streetType": "Street",
            "city": "Los Angeles",
            "state": "CA",
            "postcode": "90012",
            "latitude": 34.0522,
            "longitude": -118.2437,
        },
    }
    (root / "data" / "commercial-property.jsonl").write_text(
        json.dumps(property_record) + "\n", encoding="utf-8"
    )
    (root / "data" / "location-occupancy.jsonl").write_text("", encoding="utf-8")
    pd.DataFrame(
        [{"PropertyId": "1001", "MatterportModelId": "synthetic-model"}]
    ).to_csv(root / "commercial-properties.csv", index=False)
    (root / "schemas" / "enums.json").write_text(
        json.dumps(
            {
                "PropertyType": {"1": "Office"},
                "PropertySubtype": {"10": "Executive Suite"},
                "BuildingClass": {"2": "B"},
            }
        ),
        encoding="utf-8",
    )


def run_offline_demo(output: str | Path) -> DemoReport:
    destination = Path(output)
    fixture = create_synthetic_fixture(destination / "fixtures")
    run = run_analysis(
        enrollments_source=fixture["enrollments"],
        owners_source=fixture["owners"],
        additional_addresses_source=fixture["additional"],
        costar_kit=fixture["costar_kit"],
        run_at=DEMO_TIME,
    )
    write_analysis(run, destination)
    investigations = [
        investigate_building(
            BuildingAnalysisResponse.model_validate(asdict(building)),
            run_at=DEMO_TIME,
        )
        for building in run.buildings
    ]
    (destination / "investigation_cases.json").write_text(
        json.dumps([result.to_dict() for result in investigations], indent=2) + "\n",
        encoding="utf-8",
    )
    hotspot = next(
        (building for building in run.buildings if building.building_key == HOTSPOT_ADDRESS),
        None,
    )
    hotspot_case = next(
        (
            result
            for result in investigations
            if result.target_id == getattr(hotspot, "building_id", None)
        ),
        None,
    )
    serialized = json.dumps(
        {
            "ownership": run.ownership.to_dict(),
            "investigations": [result.to_dict() for result in investigations],
        }
    )
    report = DemoReport(
        status="passed",
        generated_at=DEMO_TIME.isoformat(),
        building_count=len(run.buildings),
        high_priority_count=sum(
            building.priority["score"]["level"] == "high_priority"
            for building in run.buildings
        ),
        completed_case_count=sum(result.case_file is not None for result in investigations),
        early_stop_count=sum(result.case_file is None for result in investigations),
        expected_hotspot_found=hotspot is not None,
        expected_hotspot_high_priority=(
            hotspot is not None
            and hotspot.priority["score"]["level"] == "high_priority"
        ),
        expected_hotspot_has_case=(
            hotspot_case is not None and hotspot_case.case_file is not None
        ),
        private_owner_data_absent=(
            PRIVATE_FIXTURE_NAME not in serialized and PRIVATE_FIXTURE_ID not in serialized
        ),
        disclaimer_present=all(
            result.case_file is None
            or "not conclusions of fraud" in result.case_file.disclaimer
            for result in investigations
        ),
    )
    report = DemoReport(**{**asdict(report), "status": "passed" if report.passed else "failed"})
    (destination / "evaluation_results.json").write_text(
        json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and evaluate the offline demo.")
    parser.add_argument("--output", type=Path, default=Path("data/demo"))
    args = parser.parse_args()
    report = run_offline_demo(args.output)
    print(json.dumps(asdict(report), indent=2))
    if not report.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
