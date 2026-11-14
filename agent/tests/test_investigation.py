from __future__ import annotations

from datetime import UTC, datetime

from agent.investigation import InvestigationPolicy, investigate_building
from api.schemas import BuildingAnalysisResponse


def building(*, total: float = 80, level: str = "high_priority", evidence: int = 2):
    records = [
        {
            "source": "derived",
            "record_id": f"record-{index}",
            "retrieved_at": "2026-11-14T00:00:00Z",
            "fields": {"hospice_count": 12},
        }
        for index in range(evidence)
    ]
    indicator_scores = [80, 70 if evidence >= 2 else 0]
    indicators = [
        {
            "indicator": name,
            "value": {"measured": True},
            "score_contribution": score,
            "evidence": records[index : index + 1],
            "limitations": ["This signal can occur in legitimate organizations."],
        }
        for index, (name, score) in enumerate(
            zip(("address_clustering", "ownership_network"), indicator_scores, strict=True)
        )
    ]
    return BuildingAnalysisResponse.model_validate(
        {
            "building_id": "bldg_test",
            "building_key": "100 TEST ST LOS ANGELES CA 90012",
            "hospice_count": 12,
            "indicators": indicators,
            "priority": {
                "score": {
                    "target_id": "bldg_test",
                    "total": total,
                    "level": level,
                    "model_version": "review-priority-v1",
                    "components": [
                        {
                            "indicator": "combined",
                            "weight": 1,
                            "raw_score": total,
                            "weighted_score": total,
                        }
                    ],
                },
                "configured_weights": {"combined": 1},
                "effective_weights": {"combined": 1},
                "missing_indicators": [],
                "strong_indicators": ["address_clustering", "ownership_network"],
                "claim_reason": "Multiple independent signals.",
            },
            "costar_match_status": "not_configured",
        }
    )


def test_writes_neutral_evidence_bound_case_and_complete_trace() -> None:
    result = investigate_building(
        building(), run_at=datetime(2026, 11, 14, tzinfo=UTC)
    )

    assert result.case_file is not None
    assert len(result.case_file.findings) == 2
    assert all(finding.evidence for finding in result.case_file.findings)
    assert all(finding.strength < 0.8 for finding in result.case_file.findings)
    assert "not conclusions of fraud" in result.case_file.disclaimer
    assert [event.event_type.value for event in result.trace] == [
        "started",
        "tool_called",
        "tool_completed",
        "skeptic_review",
        "case_written",
    ]


def test_case_and_event_ids_are_deterministic() -> None:
    timestamp = datetime(2026, 11, 14, tzinfo=UTC)
    first = investigate_building(building(), run_at=timestamp)
    second = investigate_building(building(), run_at=timestamp)

    assert first.case_file is not None and second.case_file is not None
    assert first.case_file.case_id == second.case_file.case_id
    assert [event.event_id for event in first.trace] == [
        event.event_id for event in second.trace
    ]


def test_early_stops_below_priority_threshold() -> None:
    result = investigate_building(building(total=20, level="no_indicators_found"))

    assert result.case_file is None
    assert result.trace[-1].event_type.value == "early_stopped"
    assert "threshold" in (result.stopped_reason or "")


def test_early_stops_when_evidence_is_insufficient() -> None:
    result = investigate_building(building(evidence=1))

    assert result.case_file is None
    assert "at least 2" in (result.stopped_reason or "")


def test_ignores_unrecognized_indicators_and_respects_finding_cap() -> None:
    source = building()
    expanded = source.model_copy(
        update={
            "indicators": source.indicators
            + tuple(
                source.indicators[0].model_copy(
                    update={"indicator": f"unknown-{i}"}
                )
                for i in range(4)
            )
        }
    )
    result = investigate_building(
        expanded,
        policy=InvestigationPolicy(maximum_findings=1),
    )

    assert result.case_file is not None
    assert len(result.case_file.findings) == 1
