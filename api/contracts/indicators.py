from enum import StrEnum

from pydantic import Field, JsonValue, model_validator

from api.contracts.base import ContractModel
from api.contracts.evidence import EvidenceRecord


class ReviewLevel(StrEnum):
    HIGH_PRIORITY = "high_priority"
    WORTH_A_LOOK = "worth_a_look"
    NO_INDICATORS = "no_indicators_found"


class IndicatorResult(ContractModel):
    indicator: str = Field(min_length=1, max_length=100)
    value: JsonValue
    score_contribution: float = Field(ge=0, le=100)
    evidence: tuple[EvidenceRecord, ...]
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def scored_indicators_require_evidence(self) -> "IndicatorResult":
        if self.score_contribution > 0 and not self.evidence:
            raise ValueError("a scored indicator must include evidence")
        return self


class ScoreComponent(ContractModel):
    indicator: str = Field(min_length=1, max_length=100)
    weight: float = Field(ge=0, le=1)
    raw_score: float = Field(ge=0, le=100)
    weighted_score: float = Field(ge=0, le=100)


class ReviewPriorityScore(ContractModel):
    target_id: str = Field(min_length=1, max_length=100)
    total: float = Field(ge=0, le=100)
    level: ReviewLevel
    model_version: str = Field(min_length=1, max_length=50)
    components: tuple[ScoreComponent, ...]

    @model_validator(mode="after")
    def total_matches_components(self) -> "ReviewPriorityScore":
        calculated = round(sum(component.weighted_score for component in self.components), 4)
        if abs(calculated - self.total) > 0.01:
            raise ValueError("total must equal the sum of weighted component scores")
        return self

