from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

STREET_SUFFIXES = {
    "AVENUE": "AVE",
    "BOULEVARD": "BLVD",
    "CIRCLE": "CIR",
    "COURT": "CT",
    "DRIVE": "DR",
    "HIGHWAY": "HWY",
    "LANE": "LN",
    "PARKWAY": "PKWY",
    "PLACE": "PL",
    "ROAD": "RD",
    "STREET": "ST",
    "TERRACE": "TER",
}

DIRECTIONALS = {
    "NORTH": "N",
    "SOUTH": "S",
    "EAST": "E",
    "WEST": "W",
    "NORTHEAST": "NE",
    "NORTHWEST": "NW",
    "SOUTHEAST": "SE",
    "SOUTHWEST": "SW",
}

SUITE_PATTERN = re.compile(
    r"(?:\s+|,)(?:SUITE|STE|UNIT|#)\s*([A-Z0-9][A-Z0-9-]*)\s*$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class NormalizedAddress:
    raw: str
    normalized: str
    building_key: str
    suite: str | None
    confidence: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AddressOverride:
    building_key: str
    suite: str | None = None
    note: str = "manual override"


def _clean_tokens(value: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9# -]", " ", value.upper())
    tokens = re.sub(r"\s+", " ", cleaned).strip().split()
    normalized = [DIRECTIONALS.get(token, STREET_SUFFIXES.get(token, token)) for token in tokens]
    return " ".join(normalized)


def _extract_suite(line1: str, line2: str) -> tuple[str, str | None, list[str]]:
    warnings: list[str] = []
    match = SUITE_PATTERN.search(line1)
    suite_from_line1 = match.group(1).upper() if match else None
    street = line1[: match.start()].strip(" ,") if match else line1

    suite_from_line2: str | None = None
    if line2.strip():
        line2_clean = _clean_tokens(line2).replace("SUITE ", "").replace("STE ", "")
        line2_clean = line2_clean.replace("UNIT ", "").lstrip("# ")
        suite_from_line2 = line2_clean or None

    if suite_from_line1 and suite_from_line2 and suite_from_line1 != suite_from_line2:
        warnings.append("conflicting suite values in address lines")

    return street, suite_from_line2 or suite_from_line1, warnings


def normalize_address(
    *,
    line1: str,
    line2: str = "",
    city: str,
    state: str,
    postal_code: str,
    override: AddressOverride | None = None,
) -> NormalizedAddress:
    raw_parts = [line1.strip(), line2.strip(), city.strip(), state.strip(), postal_code.strip()]
    raw = ", ".join(part for part in raw_parts if part)
    street, suite, warnings = _extract_suite(line1, line2)
    street_norm = _clean_tokens(street)
    city_norm = _clean_tokens(city)
    state_norm = _clean_tokens(state)
    zip_match = re.search(r"\d{5}", postal_code)
    zip5 = zip_match.group(0) if zip_match else ""

    street_number = re.match(r"^\d+[A-Z]?\b", street_norm)
    if not street_number:
        warnings.append("street number missing or unrecognized")
    if not zip5:
        warnings.append("five-digit ZIP code missing")
    if len(state_norm) != 2:
        warnings.append("state code is not two characters")

    normalized_parts = [street_norm]
    if suite:
        normalized_parts.append(f"STE {suite}")
    normalized_parts.extend(part for part in (city_norm, state_norm, zip5) if part)
    normalized = " ".join(normalized_parts)
    building_key = " ".join(
        part for part in (street_norm, city_norm, state_norm, zip5) if part
    )

    confidence = max(0.0, 1.0 - 0.2 * len(warnings))
    if override is not None:
        building_key = override.building_key
        suite = override.suite if override.suite is not None else suite
        warnings.append(f"manual override applied: {override.note}")
        confidence = 1.0

    return NormalizedAddress(
        raw=raw,
        normalized=normalized,
        building_key=building_key,
        suite=suite,
        confidence=confidence,
        warnings=tuple(warnings),
    )


def address_override_key(
    *, line1: str, line2: str, city: str, state: str, postal_code: str
) -> str:
    return "|".join(part.strip().upper() for part in (line1, line2, city, state, postal_code))


def load_overrides(path: str | Path | None) -> dict[str, AddressOverride]:
    if path is None:
        return {}
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("address override file must contain a JSON object")
    return {
        key.upper(): AddressOverride(
            building_key=value["building_key"],
            suite=value.get("suite"),
            note=value.get("note", "manual override"),
        )
        for key, value in payload.items()
    }

