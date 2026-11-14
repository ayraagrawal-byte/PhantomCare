from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from pipeline.analysis import run_analysis, write_analysis


def _write(path: Path, rows: list[dict[str, str]], columns: list[str] | None = None) -> Path:
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
    return path


def test_end_to_end_analysis_produces_explainable_outputs(tmp_path: Path) -> None:
    enrollments = []
    owners = []
    for number in range(1, 8):
        enrollment_id = f"E-{number}"
        enrollments.append(
            {
                "ENROLLMENT ID": enrollment_id,
                "NPI": f"12345678{number:02d}",
                "ORGANIZATION NAME": f"Hospice {number}",
                "ADDRESS LINE 1": "100 Review St" if number <= 5 else f"{number} Solo St",
                "ADDRESS LINE 2": f"Suite {number}" if number <= 5 else "",
                "CITY": "Los Angeles",
                "STATE": "CA",
                "ZIP CODE": "90012",
                "COUNTY": "Los Angeles",
            }
        )
        owners.append(
            {
                "ENROLLMENT ID": enrollment_id,
                "ASSOCIATE ID - OWNER": "SHARED-PERSON" if number <= 5 else f"ORG-{number}",
                "TYPE - OWNER": "I" if number <= 5 else "O",
                "FIRST NAME - OWNER": "Never Expose" if number <= 5 else "",
                "ORGANIZATION NAME - OWNER": "" if number <= 5 else f"Group {number}",
            }
        )

    enrollment_path = _write(tmp_path / "enrollments.csv", enrollments)
    owner_path = _write(tmp_path / "owners.csv", owners)
    additional_path = _write(
        tmp_path / "additional.csv",
        [],
        ["ENROLLMENT ID", "ADDRESS LINE 1", "CITY", "STATE", "ZIP CODE"],
    )
    timestamp = datetime(2026, 11, 14, tzinfo=UTC)

    run = run_analysis(
        enrollments_source=enrollment_path,
        owners_source=owner_path,
        additional_addresses_source=additional_path,
        run_at=timestamp,
    )

    assert len(run.buildings) == 3
    top = next(item for item in run.buildings if item.hospice_count == 5)
    assert top.costar_match_status == "not_configured"
    assert top.latitude is None
    assert top.longitude is None
    assert top.priority["score"]["level"] == "worth_a_look"
    assert set(top.priority["missing_indicators"]) == {
        "building_type_fit",
        "space_per_hospice",
    }
    assert "address_clustering" in top.priority["strong_indicators"]
    assert "ownership_network" in top.priority["strong_indicators"]
    assert "Never Expose" not in json.dumps(run.ownership.to_dict())
    assert "SHARED-PERSON" not in json.dumps(run.ownership.to_dict())

    output = tmp_path / "output"
    write_analysis(run, output)
    expected_files = {
        "analysis_summary.json",
        "building_analysis.json",
        "buildings_ranked.csv",
        "hospice_additional_addresses.csv",
        "hospice_enrollments.csv",
        "hospice_enrollments_normalized.csv",
        "hospice_owners.csv",
        "import_summary.json",
        "ownership_network.json",
    }
    assert expected_files <= {path.name for path in output.iterdir()}
    summary = json.loads((output / "analysis_summary.json").read_text())
    assert summary["enrollment_count"] == 7
    assert summary["building_count"] == 3
    assert summary["generated_at"] == timestamp.isoformat()
    assert "not findings of fraud" in summary["disclaimer"]
