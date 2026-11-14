from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

import pandas as pd


class CmsFileType(StrEnum):
    ENROLLMENTS = "enrollments"
    OWNERS = "owners"
    ADDITIONAL_ADDRESSES = "additional_addresses"


class CmsSchemaError(ValueError):
    """Raised when a CMS file does not match the documented schema."""


COLUMN_ALIASES = {
    "ENROLLMENT_ID": ("ENROLLMENT ID", "ENROLLMENT_ID"),
    "NPI": ("NPI",),
    "CCN": ("CCN",),
    "ORGANIZATION_NAME": ("ORGANIZATION NAME", "ORGANIZATION_NAME"),
    "ADDRESS_LINE_1": ("ADDRESS LINE 1", "ADDRESS_LINE_1"),
    "ADDRESS_LINE_2": ("ADDRESS LINE 2", "ADDRESS_LINE_2"),
    "CITY": ("CITY", "CITY/TOWN"),
    "STATE": ("STATE",),
    "ZIP_CODE": ("ZIP CODE", "ZIP_CODE"),
    "COUNTY": ("COUNTY", "COUNTY/PARISH"),
    "OWNER_ASSOCIATE_ID": ("ASSOCIATE ID - OWNER", "OWNER_ASSOCIATE_ID"),
    "OWNER_TYPE": ("TYPE - OWNER", "OWNER_TYPE"),
    "OWNER_ORGANIZATION_NAME": (
        "ORGANIZATION NAME - OWNER",
        "OWNER_ORGANIZATION_NAME",
    ),
    "OWNER_FIRST_NAME": ("FIRST NAME - OWNER", "OWNER_FIRST_NAME"),
    "OWNER_MIDDLE_NAME": ("MIDDLE NAME - OWNER", "OWNER_MIDDLE_NAME"),
    "OWNER_LAST_NAME": ("LAST NAME - OWNER", "OWNER_LAST_NAME"),
    "OWNER_ADDRESS_LINE_1": ("ADDRESS LINE 1 - OWNER", "OWNER_ADDRESS_LINE_1"),
    "OWNER_ADDRESS_LINE_2": ("ADDRESS LINE 2 - OWNER", "OWNER_ADDRESS_LINE_2"),
    "OWNER_CITY": ("CITY - OWNER", "OWNER_CITY"),
    "OWNER_STATE": ("STATE - OWNER", "OWNER_STATE"),
    "OWNER_ZIP_CODE": ("ZIP CODE - OWNER", "OWNER_ZIP_CODE"),
    "PERCENTAGE_OWNERSHIP": ("PERCENTAGE OWNERSHIP", "PERCENTAGE_OWNERSHIP"),
}

REQUIRED_COLUMNS = {
    CmsFileType.ENROLLMENTS: {
        "ENROLLMENT_ID",
        "NPI",
        "ORGANIZATION_NAME",
        "ADDRESS_LINE_1",
        "CITY",
        "STATE",
        "ZIP_CODE",
    },
    CmsFileType.OWNERS: {"ENROLLMENT_ID", "OWNER_ASSOCIATE_ID", "OWNER_TYPE"},
    CmsFileType.ADDITIONAL_ADDRESSES: {
        "ENROLLMENT_ID",
        "ADDRESS_LINE_1",
        "CITY",
        "STATE",
        "ZIP_CODE",
    },
}

DEDUPE_KEYS = {
    CmsFileType.ENROLLMENTS: ("ENROLLMENT_ID",),
    CmsFileType.OWNERS: ("ENROLLMENT_ID", "OWNER_ASSOCIATE_ID"),
    CmsFileType.ADDITIONAL_ADDRESSES: (
        "ENROLLMENT_ID",
        "ADDRESS_LINE_1",
        "ADDRESS_LINE_2",
        "CITY",
        "STATE",
        "ZIP_CODE",
    ),
}


@dataclass(frozen=True)
class ImportSummary:
    file_type: str
    source: str
    input_rows: int
    retained_rows: int
    duplicate_rows_removed: int
    rejected_rows: int
    rejection_reasons: dict[str, int]


@dataclass(frozen=True)
class CmsBundleResult:
    enrollments: pd.DataFrame
    owners: pd.DataFrame
    additional_addresses: pd.DataFrame
    summaries: tuple[ImportSummary, ...]


def _normalized_header(value: str) -> str:
    return " ".join(value.strip().upper().replace("_", " ").split())


def _column_mapping(columns: Iterable[str]) -> dict[str, str]:
    by_normalized = {_normalized_header(column): column for column in columns}
    mapping: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            original = by_normalized.get(_normalized_header(alias))
            if original is not None:
                mapping[original] = canonical
                break
    return mapping


def _read_csv(source: str | Path) -> pd.DataFrame:
    try:
        return pd.read_csv(source, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception as error:
        raise CmsSchemaError(f"Unable to read CMS CSV {source}: {error}") from error


def _validate_columns(frame: pd.DataFrame, file_type: CmsFileType) -> None:
    missing = sorted(REQUIRED_COLUMNS[file_type] - set(frame.columns))
    if missing:
        available = ", ".join(sorted(frame.columns))
        raise CmsSchemaError(
            f"{file_type.value} is missing required columns: {', '.join(missing)}. "
            f"Available canonical columns: {available}"
        )


def _clean_strings(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        result[column] = result[column].astype("string").str.strip()
    return result


def _add_provenance(frame: pd.DataFrame, source: str | Path) -> pd.DataFrame:
    result = frame.copy()
    result["_SOURCE_ROW_NUMBER"] = range(2, len(result) + 2)
    result["_SOURCE_FILE"] = str(source)
    source_columns = sorted(column for column in result.columns if not column.startswith("_"))

    def digest(row: pd.Series) -> str:
        payload = "\x1f".join(str(row[column]) for column in source_columns)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    result["_ROW_HASH"] = result.apply(digest, axis=1)
    return result


def _valid_required_rows(
    frame: pd.DataFrame, file_type: CmsFileType
) -> tuple[pd.DataFrame, dict[str, int]]:
    keep = pd.Series(True, index=frame.index)
    reasons: dict[str, int] = {}
    for column in sorted(REQUIRED_COLUMNS[file_type]):
        empty = frame[column].isna() | frame[column].eq("")
        count = int((keep & empty).sum())
        if count:
            reasons[f"missing_{column.lower()}"] = count
        keep &= ~empty
    return frame.loc[keep].copy(), reasons


def _filter_la_county(
    frame: pd.DataFrame, la_county_zip_codes: set[str] | None
) -> pd.DataFrame:
    state_matches = frame["STATE"].str.upper().eq("CA")
    if "COUNTY" in frame.columns:
        county = frame["COUNTY"].str.upper().str.replace(" COUNTY", "", regex=False)
        return frame.loc[state_matches & county.eq("LOS ANGELES")].copy()

    if not la_county_zip_codes:
        raise CmsSchemaError(
            "enrollments has no COUNTY column. Supply an authoritative LA County ZIP-code "
            "allowlist; the pipeline will not guess county membership from city names."
        )

    zip5 = frame["ZIP_CODE"].str.extract(r"(\d{5})", expand=False)
    return frame.loc[state_matches & zip5.isin(la_county_zip_codes)].copy()


def import_cms_file(
    source: str | Path,
    file_type: CmsFileType,
    *,
    la_county_zip_codes: set[str] | None = None,
    allowed_enrollment_ids: set[str] | None = None,
) -> tuple[pd.DataFrame, ImportSummary]:
    raw = _read_csv(source)
    input_rows = len(raw)
    canonical = raw.rename(columns=_column_mapping(raw.columns))
    canonical = canonical.loc[:, ~canonical.columns.duplicated()].copy()
    _validate_columns(canonical, file_type)
    canonical = _clean_strings(canonical)
    canonical = _add_provenance(canonical, source)

    valid, reasons = _valid_required_rows(canonical, file_type)
    rejected_rows = input_rows - len(valid)

    if file_type == CmsFileType.ENROLLMENTS:
        valid = _filter_la_county(valid, la_county_zip_codes)
    elif allowed_enrollment_ids is not None:
        valid = valid.loc[valid["ENROLLMENT_ID"].isin(allowed_enrollment_ids)].copy()

    dedupe_keys = [key for key in DEDUPE_KEYS[file_type] if key in valid.columns]
    before_dedupe = len(valid)
    valid = valid.drop_duplicates(subset=dedupe_keys, keep="first")
    duplicates = before_dedupe - len(valid)
    valid = valid.sort_values(dedupe_keys, kind="stable").reset_index(drop=True)

    summary = ImportSummary(
        file_type=file_type.value,
        source=str(source),
        input_rows=input_rows,
        retained_rows=len(valid),
        duplicate_rows_removed=duplicates,
        rejected_rows=rejected_rows,
        rejection_reasons=reasons,
    )
    return valid, summary


def import_cms_bundle(
    enrollments_source: str | Path,
    owners_source: str | Path,
    additional_addresses_source: str | Path,
    *,
    la_county_zip_codes: set[str] | None = None,
) -> CmsBundleResult:
    enrollments, enrollment_summary = import_cms_file(
        enrollments_source,
        CmsFileType.ENROLLMENTS,
        la_county_zip_codes=la_county_zip_codes,
    )
    enrollment_ids = set(enrollments["ENROLLMENT_ID"])
    owners, owner_summary = import_cms_file(
        owners_source,
        CmsFileType.OWNERS,
        allowed_enrollment_ids=enrollment_ids,
    )
    additional, additional_summary = import_cms_file(
        additional_addresses_source,
        CmsFileType.ADDITIONAL_ADDRESSES,
        allowed_enrollment_ids=enrollment_ids,
    )
    return CmsBundleResult(
        enrollments=enrollments,
        owners=owners,
        additional_addresses=additional,
        summaries=(enrollment_summary, owner_summary, additional_summary),
    )


def write_bundle(result: CmsBundleResult, output_dir: str | Path) -> None:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    result.enrollments.to_csv(destination / "hospice_enrollments.csv", index=False)
    result.owners.to_csv(destination / "hospice_owners.csv", index=False)
    result.additional_addresses.to_csv(
        destination / "hospice_additional_addresses.csv", index=False
    )
    with (destination / "import_summary.json").open("w", encoding="utf-8") as stream:
        json.dump([asdict(summary) for summary in result.summaries], stream, indent=2)
        stream.write("\n")

