from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import TypeAdapter, ValidationError

from api.config import settings
from api.contracts import ReviewLevel
from api.schemas import (
    AnalysisSummaryResponse,
    BuildingAnalysisResponse,
    BuildingListItemResponse,
)


class AnalysisArtifactError(RuntimeError):
    """Raised when generated analysis artifacts are unavailable or invalid."""


class AnalysisRepository:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _read(self, filename: str) -> object:
        path = self.root / filename
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise AnalysisArtifactError(f"analysis artifact is missing: {filename}") from error
        except (OSError, json.JSONDecodeError) as error:
            raise AnalysisArtifactError(f"analysis artifact is unreadable: {filename}") from error

    def summary(self) -> AnalysisSummaryResponse:
        try:
            return AnalysisSummaryResponse.model_validate(self._read("analysis_summary.json"))
        except ValidationError as error:
            raise AnalysisArtifactError("analysis summary failed validation") from error

    def buildings(self) -> tuple[BuildingAnalysisResponse, ...]:
        try:
            return tuple(
                TypeAdapter(list[BuildingAnalysisResponse]).validate_python(
                    self._read("building_analysis.json")
                )
            )
        except ValidationError as error:
            raise AnalysisArtifactError("building analysis failed validation") from error


def get_analysis_repository() -> AnalysisRepository:
    return AnalysisRepository(settings.analysis_dir)


router = APIRouter(prefix="/analysis", tags=["analysis"])
AnalysisRepositoryDependency = Annotated[
    AnalysisRepository, Depends(get_analysis_repository)
]


def _unavailable(error: AnalysisArtifactError) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "analysis_unavailable",
            "message": str(error),
            "action": "Run python -m pipeline.analysis to generate validated artifacts.",
        },
    )


@router.get("/summary", response_model=AnalysisSummaryResponse)
def analysis_summary(
    repository: AnalysisRepositoryDependency,
) -> AnalysisSummaryResponse:
    try:
        return repository.summary()
    except AnalysisArtifactError as error:
        raise _unavailable(error) from error


@router.get("/buildings", response_model=list[BuildingListItemResponse])
def list_buildings(
    repository: AnalysisRepositoryDependency,
    level: ReviewLevel | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[BuildingListItemResponse]:
    try:
        buildings = repository.buildings()
    except AnalysisArtifactError as error:
        raise _unavailable(error) from error
    items = [BuildingListItemResponse.from_analysis(building) for building in buildings]
    if level is not None:
        items = [item for item in items if item.review_level == level]
    return sorted(items, key=lambda item: (-item.total_score, item.building_id))[:limit]


@router.get("/buildings/{building_id}", response_model=BuildingAnalysisResponse)
def building_detail(
    building_id: str,
    repository: AnalysisRepositoryDependency,
) -> BuildingAnalysisResponse:
    try:
        buildings = repository.buildings()
    except AnalysisArtifactError as error:
        raise _unavailable(error) from error
    for building in buildings:
        if building.building_id == building_id:
            return building
    raise HTTPException(
        status_code=404,
        detail={"code": "building_not_found", "building_id": building_id},
    )
