from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.contracts import (
    IndicatorResult,
    ReviewLevel,
    ReviewPriorityScore,
    ScoreComponent,
)


class ScoringConfigError(ValueError):
    """Raised when the versioned scoring configuration is invalid."""


@dataclass(frozen=True)
class ScoringConfig:
    version: str
    weights: dict[str, float]
    high_priority_minimum_score: float
    high_priority_minimum_strong_indicators: int
    worth_a_look_minimum_score: float
    strong_indicator_minimum_score: float


@dataclass(frozen=True)
class ScoreDecision:
    score: ReviewPriorityScore
    configured_weights: dict[str, float]
    effective_weights: dict[str, float]
    missing_indicators: tuple[str, ...]
    strong_indicators: tuple[str, ...]
    claim_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score.model_dump(mode="json"),
            "configured_weights": self.configured_weights,
            "effective_weights": self.effective_weights,
            "missing_indicators": self.missing_indicators,
            "strong_indicators": self.strong_indicators,
            "claim_reason": self.claim_reason,
        }


def load_scoring_config(path: str | Path | None = None) -> ScoringConfig:
    source = Path(path) if path else Path(__file__).with_name("scoring_v1.json")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ScoringConfigError(f"Unable to read scoring config {source}: {error}") from error
    try:
        config = ScoringConfig(**payload)
    except TypeError as error:
        raise ScoringConfigError(f"Invalid scoring config fields: {error}") from error
    _validate_config(config)
    return config


def _validate_config(config: ScoringConfig) -> None:
    if not config.version:
        raise ScoringConfigError("scoring config version is required")
    if not config.weights:
        raise ScoringConfigError("at least one indicator weight is required")
    if any(weight < 0 or weight > 1 for weight in config.weights.values()):
        raise ScoringConfigError("indicator weights must be between 0 and 1")
    score_weight_total = sum(config.weights.values())
    if abs(score_weight_total - 1.0) > 0.0001:
        raise ScoringConfigError("configured indicator weights must sum to 1")
    for value in (
        config.high_priority_minimum_score,
        config.worth_a_look_minimum_score,
        config.strong_indicator_minimum_score,
    ):
        if value < 0 or value > 100:
            raise ScoringConfigError("score thresholds must be between 0 and 100")
    if config.high_priority_minimum_strong_indicators < 2:
        raise ScoringConfigError("high priority must require multiple strong indicators")


def _is_missing(indicator: IndicatorResult) -> bool:
    if indicator.evidence:
        return False
    value = indicator.value
    return isinstance(value, dict) and str(value.get("status", "")).startswith("no_")


def score_indicators(
    *,
    target_id: str,
    indicators: tuple[IndicatorResult, ...] | list[IndicatorResult],
    config: ScoringConfig | None = None,
) -> ScoreDecision:
    scoring_config = config or load_scoring_config()
    by_name: dict[str, IndicatorResult] = {}
    for indicator in indicators:
        if indicator.indicator in by_name:
            raise ValueError(f"duplicate indicator: {indicator.indicator}")
        by_name[indicator.indicator] = indicator

    scored_names = [name for name, weight in scoring_config.weights.items() if weight > 0]
    missing = tuple(
        name
        for name in scored_names
        if name not in by_name or _is_missing(by_name[name])
    )
    available = [name for name in scored_names if name not in missing]
    if not available:
        score = ReviewPriorityScore(
            target_id=target_id,
            total=0,
            level=ReviewLevel.NO_INDICATORS,
            model_version=scoring_config.version,
            components=(),
        )
        return ScoreDecision(
            score=score,
            configured_weights=dict(scoring_config.weights),
            effective_weights={},
            missing_indicators=missing,
            strong_indicators=(),
            claim_reason="No scored indicators had usable evidence.",
        )

    available_weight = sum(scoring_config.weights[name] for name in available)
    effective_weights = {
        name: scoring_config.weights[name] / available_weight for name in available
    }
    components = tuple(
        ScoreComponent(
            indicator=name,
            weight=round(effective_weights[name], 6),
            raw_score=by_name[name].score_contribution,
            weighted_score=round(
                by_name[name].score_contribution * effective_weights[name], 4
            ),
        )
        for name in available
    )
    total = round(sum(component.weighted_score for component in components), 4)
    strong = tuple(
        name
        for name in available
        if by_name[name].score_contribution
        >= scoring_config.strong_indicator_minimum_score
    )

    if (
        total >= scoring_config.high_priority_minimum_score
        and len(strong) >= scoring_config.high_priority_minimum_strong_indicators
    ):
        level = ReviewLevel.HIGH_PRIORITY
        reason = (
            f"Score {total:.1f} with {len(strong)} independent strong indicators."
        )
    elif total >= scoring_config.worth_a_look_minimum_score or strong:
        level = ReviewLevel.WORTH_A_LOOK
        if len(strong) < scoring_config.high_priority_minimum_strong_indicators:
            reason = (
                f"Score {total:.1f}; only {len(strong)} strong indicator(s), fewer than "
                "required for high priority."
            )
        else:
            reason = f"Score {total:.1f}, below the high-priority threshold."
    else:
        level = ReviewLevel.NO_INDICATORS
        reason = f"Score {total:.1f}; no strong indicators were found."

    score = ReviewPriorityScore(
        target_id=target_id,
        total=total,
        level=level,
        model_version=scoring_config.version,
        components=components,
    )
    return ScoreDecision(
        score=score,
        configured_weights=dict(scoring_config.weights),
        effective_weights={name: round(weight, 6) for name, weight in effective_weights.items()},
        missing_indicators=missing,
        strong_indicators=strong,
        claim_reason=reason,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score evidence-bearing building indicators.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    config = load_scoring_config(args.config)
    decisions = []
    for item in payload:
        indicators = [IndicatorResult.model_validate(value) for value in item["indicators"]]
        decision = score_indicators(
            target_id=item["target_id"],
            indicators=indicators,
            config=config,
        )
        decisions.append(decision.to_dict())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decisions, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

