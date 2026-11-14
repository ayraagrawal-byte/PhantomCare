from datetime import UTC, datetime

import pytest

from api.contracts import EvidenceRecord, IndicatorResult, ReviewLevel, SourceDataset
from engine.scoring import ScoringConfig, ScoringConfigError, load_scoring_config, score_indicators

NOW = datetime(2026, 11, 13, tzinfo=UTC)


def evidence(name: str) -> tuple[EvidenceRecord, ...]:
    return (
        EvidenceRecord(
            source=SourceDataset.DERIVED,
            record_id=name,
            retrieved_at=NOW,
            fields={"test": True},
        ),
    )


def indicator(name: str, score: float, *, missing: bool = False) -> IndicatorResult:
    return IndicatorResult(
        indicator=name,
        value={"status": "no_building_data"} if missing else {"value": score},
        score_contribution=0 if missing else score,
        evidence=() if missing else evidence(name),
    )


def test_default_config_is_versioned_and_weights_sum_to_one() -> None:
    config = load_scoring_config()

    assert config.version == "review-priority-v1"
    assert sum(config.weights.values()) == pytest.approx(1)


def test_three_independent_signals_can_be_high_priority() -> None:
    decision = score_indicators(
        target_id="B-1",
        indicators=[
            indicator("address_clustering", 100),
            indicator("building_type_fit", 80),
            indicator("space_per_hospice", 75),
            indicator("ownership_network", 65),
        ],
    )

    assert decision.score.level == ReviewLevel.HIGH_PRIORITY
    assert decision.score.total == pytest.approx(83)
    assert len(decision.strong_indicators) == 4
    assert sum(component.weight for component in decision.score.components) == pytest.approx(1)


def test_clustering_alone_can_never_be_high_priority() -> None:
    decision = score_indicators(
        target_id="B-1",
        indicators=[
            indicator("address_clustering", 100),
            indicator("building_type_fit", 0, missing=True),
            indicator("space_per_hospice", 0, missing=True),
            indicator("ownership_network", 0, missing=True),
        ],
    )

    assert decision.score.total == 100
    assert decision.score.level == ReviewLevel.WORTH_A_LOOK
    assert "only 1 strong" in decision.claim_reason


def test_missing_sponsor_data_is_excluded_and_weights_are_rescaled() -> None:
    decision = score_indicators(
        target_id="B-1",
        indicators=[
            indicator("address_clustering", 80),
            indicator("building_type_fit", 0, missing=True),
            indicator("space_per_hospice", 0, missing=True),
            indicator("ownership_network", 40),
        ],
    )

    assert set(decision.missing_indicators) == {"building_type_fit", "space_per_hospice"}
    assert decision.effective_weights["address_clustering"] == pytest.approx(0.636364)
    assert decision.score.total == pytest.approx(65.4546)


def test_available_zero_signal_lowers_score() -> None:
    decision = score_indicators(
        target_id="B-1",
        indicators=[
            indicator("address_clustering", 60),
            indicator("building_type_fit", 0),
            indicator("space_per_hospice", 0),
            indicator("ownership_network", 0),
        ],
    )

    assert decision.missing_indicators == ()
    assert decision.score.total == 21
    assert decision.score.level == ReviewLevel.WORTH_A_LOOK


def test_no_available_indicators_returns_no_indicators() -> None:
    decision = score_indicators(
        target_id="B-1",
        indicators=[
            indicator("address_clustering", 0, missing=True),
            indicator("building_type_fit", 0, missing=True),
            indicator("space_per_hospice", 0, missing=True),
            indicator("ownership_network", 0, missing=True),
        ],
    )

    assert decision.score.total == 0
    assert decision.score.level == ReviewLevel.NO_INDICATORS
    assert decision.score.components == ()


def test_duplicate_indicators_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate indicator"):
        score_indicators(
            target_id="B-1",
            indicators=[
                indicator("address_clustering", 60),
                indicator("address_clustering", 80),
            ],
        )


def test_invalid_config_cannot_reduce_high_priority_to_one_signal() -> None:
    config = ScoringConfig(
        version="bad",
        weights={"address_clustering": 1.0},
        high_priority_minimum_score=70,
        high_priority_minimum_strong_indicators=1,
        worth_a_look_minimum_score=35,
        strong_indicator_minimum_score=60,
    )
    with pytest.raises(ScoringConfigError, match="multiple strong indicators"):
        from engine.scoring import _validate_config

        _validate_config(config)

