from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from api.contracts import (
    Address,
    EvidenceRecord,
    Hospice,
    IndicatorResult,
    Owner,
    OwnerType,
    ReviewLevel,
    ReviewPriorityScore,
    ScoreComponent,
    SourceDataset,
)


def evidence() -> EvidenceRecord:
    return EvidenceRecord(
        source=SourceDataset.CMS_ENROLLMENTS,
        record_id="enrollment-row-7",
        retrieved_at=datetime(2026, 11, 13, tzinfo=UTC),
        fields={"ENROLLMENT_ID": "E-7", "ORGANIZATION_NAME": "Example Hospice"},
    )


def address() -> Address:
    return Address(
        raw="14545 Friar St Ste 210, Van Nuys, CA 91411",
        normalized="14545 FRIAR ST STE 210 VAN NUYS CA 91411",
        building_key="14545 FRIAR ST VAN NUYS CA 91411",
        suite="210",
        city="Van Nuys",
        state="ca",
        postal_code="91411",
        normalization_confidence=0.98,
    )


def test_hospice_round_trip_preserves_raw_and_normalized_address() -> None:
    hospice = Hospice(
        enrollment_id="E-7",
        npi="1234567890",
        ccn="051234",
        name="Example Hospice",
        address=address(),
        evidence=(evidence(),),
    )

    restored = Hospice.model_validate_json(hospice.model_dump_json())

    assert restored == hospice
    assert restored.address.raw.startswith("14545 Friar")
    assert restored.address.state == "CA"


def test_invalid_npi_is_rejected() -> None:
    with pytest.raises(ValidationError, match="String should match pattern"):
        Hospice(
            enrollment_id="E-7",
            npi="not-an-npi",
            name="Example Hospice",
            address=address(),
            evidence=(evidence(),),
        )


def test_individual_owner_cannot_expose_name() -> None:
    with pytest.raises(ValidationError, match="individual owners must be masked"):
        Owner(
            owner_id="O-1",
            display_name="Unmasked Person",
            owner_type=OwnerType.INDIVIDUAL,
            is_masked=False,
            evidence=(evidence(),),
        )


def test_scored_indicator_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="must include evidence"):
        IndicatorResult(
            indicator="address_clustering",
            value=46,
            score_contribution=25,
            evidence=(),
        )


def test_score_total_must_match_component_sum() -> None:
    component = ScoreComponent(
        indicator="address_clustering",
        weight=0.4,
        raw_score=80,
        weighted_score=32,
    )

    with pytest.raises(ValidationError, match="total must equal"):
        ReviewPriorityScore(
            target_id="B-1",
            total=90,
            level=ReviewLevel.HIGH_PRIORITY,
            model_version="v1",
            components=(component,),
        )


def test_contracts_reject_unrecognized_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Address(
            raw="1 Main St",
            normalized="1 MAIN ST",
            building_key="1 MAIN ST",
            unexpected="value",
        )


def test_evidence_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone info"):
        EvidenceRecord(
            source=SourceDataset.CMS_ENROLLMENTS,
            record_id="row-1",
            retrieved_at=datetime(2026, 11, 13),
        )

