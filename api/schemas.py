from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from api.contracts import (
    CaseFile,
    IndicatorResult,
    ReviewLevel,
    ReviewPriorityScore,
    TraceEvent,
)
from api.contracts.geocodes import ApproximateLocation, CamsLocation, ReviewedLocation


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: str


class AnalysisSummaryResponse(BaseModel):
    generated_at: AwareDatetime
    enrollment_count: int = Field(ge=0)
    building_count: int = Field(ge=0)
    cams_mapped_count: int | None = Field(default=None, ge=0)
    approximate_mapped_count: int = Field(default=0, ge=0)
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


class BuildingContextResponse(BaseModel):
    property_id: str
    building_name: str | None = None
    property_type: str | None = None
    property_subtype: str | None = None
    building_class: str | None = None
    gross_building_area_sqft: float | None = Field(default=None, ge=0)
    rentable_building_area_sqft: float | None = Field(default=None, ge=0)
    stories_above_grade: int | None = Field(default=None, ge=0)
    floor_count: int | None = Field(default=None, ge=0)
    occupancy_record_count: int = Field(ge=0)
    unique_tenant_location_count: int = Field(ge=0)
    occupancy_scope: str | None = None
    matterport_model_ids: tuple[str, ...]


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
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    building_context: BuildingContextResponse | None = None


class BuildingListItemResponse(BaseModel):
    building_id: str
    building_key: str
    hospice_count: int
    total_score: float
    review_level: ReviewLevel
    strong_indicator_count: int
    costar_match_status: str
    latitude: float | None
    longitude: float | None
    coordinate_source: str | None = None
    verified_location: CamsLocation | ReviewedLocation | None = None
    approximate_location: ApproximateLocation | ReviewedLocation | None = None

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
            latitude=building.latitude,
            longitude=building.longitude,
        )


class OwnershipNodeResponse(BaseModel):
    id: str
    label: str
    kind: Literal["building", "owner", "hospice"]
    is_masked: bool = False
    count: int = Field(default=1, ge=1)


class OwnershipLinkResponse(BaseModel):
    source: str
    target: str


class BuildingNetworkResponse(BaseModel):
    building_id: str
    nodes: tuple[OwnershipNodeResponse, ...]
    links: tuple[OwnershipLinkResponse, ...]
    limitations: tuple[str, ...]


class AerialEvidenceResponse(BaseModel):
    target_id: str
    address: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    provider: Literal["vexcel"]
    kind: Literal["ortho"]
    retrieved_at: AwareDatetime
    image_url: str
    image_sha256: str
    limitations: tuple[str, ...]


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
