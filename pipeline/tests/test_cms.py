from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from pipeline.cms import (
    CmsFileType,
    CmsSchemaError,
    import_cms_bundle,
    import_cms_file,
    write_bundle,
)


def write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def enrollment_row(enrollment_id: str, *, county: str = "Los Angeles") -> dict[str, str]:
    return {
        "ENROLLMENT ID": enrollment_id,
        "NPI": "1234567890",
        "CCN": "051234",
        "ORGANIZATION NAME": f"Hospice {enrollment_id}",
        "ADDRESS LINE 1": "14545 Friar St",
        "ADDRESS LINE 2": "Suite 210",
        "CITY": "Van Nuys",
        "STATE": "CA",
        "ZIP CODE": "91411",
        "COUNTY": county,
    }


def owner_row(enrollment_id: str, owner_id: str = "PAC-1") -> dict[str, str]:
    return {
        "ENROLLMENT ID": enrollment_id,
        "ASSOCIATE ID - OWNER": owner_id,
        "TYPE - OWNER": "O",
        "ORGANIZATION NAME - OWNER": "Example Holdings",
    }


def additional_address_row(enrollment_id: str) -> dict[str, str]:
    return {
        "ENROLLMENT ID": enrollment_id,
        "ADDRESS LINE 1": "100 Main St",
        "ADDRESS LINE 2": "",
        "CITY": "Los Angeles",
        "STATE": "CA",
        "ZIP CODE": "90012",
    }


def test_bundle_filters_la_and_related_rows_and_writes_summary(tmp_path: Path) -> None:
    enrollments = write_csv(
        tmp_path / "enrollments.csv",
        [
            enrollment_row("E-2"),
            enrollment_row("E-1"),
            enrollment_row("E-1"),
            enrollment_row("E-3", county="Orange"),
        ],
    )
    owners = write_csv(
        tmp_path / "owners.csv",
        [owner_row("E-1"), owner_row("E-2", "PAC-2"), owner_row("E-3", "PAC-3")],
    )
    additional = write_csv(
        tmp_path / "additional.csv",
        [additional_address_row("E-1"), additional_address_row("E-3")],
    )

    result = import_cms_bundle(enrollments, owners, additional)

    assert result.enrollments["ENROLLMENT_ID"].tolist() == ["E-1", "E-2"]
    assert set(result.owners["ENROLLMENT_ID"]) == {"E-1", "E-2"}
    assert result.additional_addresses["ENROLLMENT_ID"].tolist() == ["E-1"]
    assert result.summaries[0].duplicate_rows_removed == 1
    assert result.enrollments.loc[0, "_SOURCE_ROW_NUMBER"] == 3
    assert len(result.enrollments.loc[0, "_ROW_HASH"]) == 64

    output = tmp_path / "output"
    write_bundle(result, output)
    summary = json.loads((output / "import_summary.json").read_text(encoding="utf-8"))
    assert summary[0]["retained_rows"] == 2


def test_missing_required_columns_fail_loudly(tmp_path: Path) -> None:
    source = write_csv(tmp_path / "bad.csv", [{"ENROLLMENT ID": "E-1"}])

    with pytest.raises(CmsSchemaError, match="missing required columns"):
        import_cms_file(source, CmsFileType.ENROLLMENTS)


def test_missing_county_requires_authoritative_zip_allowlist(tmp_path: Path) -> None:
    row = enrollment_row("E-1")
    row.pop("COUNTY")
    source = write_csv(tmp_path / "no-county.csv", [row])

    with pytest.raises(CmsSchemaError, match="authoritative LA County ZIP-code"):
        import_cms_file(source, CmsFileType.ENROLLMENTS)

    imported, _ = import_cms_file(
        source,
        CmsFileType.ENROLLMENTS,
        la_county_zip_codes={"91411"},
    )
    assert imported["ENROLLMENT_ID"].tolist() == ["E-1"]


def test_rows_missing_identifiers_are_rejected_and_reported(tmp_path: Path) -> None:
    source = write_csv(
        tmp_path / "owners.csv",
        [owner_row("E-1"), owner_row("E-2", owner_id="")],
    )

    imported, summary = import_cms_file(source, CmsFileType.OWNERS)

    assert imported["ENROLLMENT_ID"].tolist() == ["E-1"]
    assert summary.rejected_rows == 1
    assert summary.rejection_reasons == {"missing_owner_associate_id": 1}


def test_official_windows_1252_text_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "enrollments.csv"
    path.write_bytes(
        (
            "ENROLLMENT ID,NPI,ORGANIZATION NAME,ADDRESS LINE 1,CITY,STATE,ZIP CODE,COUNTY\n"
            "E-1,1234567890,HOSPICE D’AMOUR,100 MAIN ST,LOS ANGELES,CA,90012,LOS ANGELES\n"
        ).encode("cp1252")
    )

    frame, summary = import_cms_file(path, CmsFileType.ENROLLMENTS)

    assert summary.retained_rows == 1
    assert frame.iloc[0]["ORGANIZATION_NAME"] == "HOSPICE D’AMOUR"
