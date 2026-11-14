from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from api.contracts import (
    CaseFile,
    IndicatorResult,
    ReviewLevel,
    ReviewPriorityScore,
    TraceEvent,
)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: str


class AnalysisSummaryResponse(BaseModel):
    generated_at: AwareDatetime
    enrollment_count: int = Field(ge=0)
    building_count: int = Field(ge=0)
    high_priority_count: int = Field(ge=0)
    worth_a_look_count: int = Field(ge=0)
    disclaimer: str = Field(min_length=1, max_length=500)


class PriorityResponse(BaseModel):
    score: ReviewPriorityScore
    configured_weights: dict[str, float]
    effective_weights: dict[str, float]
    missing_indicators: tuple[str, ...]
    strong_indicators: tuple[str, ...]
    claim_reason: str = Field(min_length=1, max_length=1000)


class BuildingAnalysisResponse(BaseModel):
    building_id: str = Field(min_length=1, max_length=100)
    building_key: str = Field(min_length=1, max_length=500)
    hospice_count: int = Field(ge=1)
    indicators: tuple[IndicatorResult, ...]
    priority: PriorityResponse
    costar_match_status: Literal[
        "not_configured",
        "no_exact_match",
        "ambiguous_exact_match",
        "exact_match",
    ]


class BuildingListItemResponse(BaseModel):
    building_id: str
    building_key: str
    hospice_count: int
    total_score: float
    review_level: ReviewLevel
    strong_indicator_count: int
    costar_match_status: str

    @classmethod
    def from_analysis(cls, building: BuildingAnalysisResponse) -> "BuildingListItemResponse":
        return cls(
            building_id=building.building_id,
            building_key=building.building_key,
            hospice_count=building.hospice_count,
            total_score=building.priority.score.total,
            review_level=building.priority.score.level,
            strong_indicator_count=len(building.priority.strong_indicators),
            costar_match_status=building.costar_match_status,
        )


class InvestigationResultResponse(BaseModel):
    target_id: str = Field(min_length=1, max_length=100)
    case_file: CaseFile | None
    trace: tuple[TraceEvent, ...]
    stopped_reason: str | None = Field(default=None, max_length=1000)


class CaseListItemResponse(BaseModel):
    case_id: str
    target_id: str
    created_at: AwareDatetime
    total_score: float
    review_level: ReviewLevel
    finding_count: int = Field(ge=1)

