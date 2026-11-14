from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import TypeAdapter, ValidationError

from api.config import settings
from api.schemas import CaseListItemResponse, InvestigationResultResponse


class CaseArtifactError(RuntimeError):
    """Raised when investigation artifacts are unavailable or malformed."""


class CaseRepository:
    def __init__(self, root: str | Path) -> None:
        self.path = Path(root) / "investigation_cases.json"

    def results(self) -> tuple[InvestigationResultResponse, ...]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return tuple(TypeAdapter(list[InvestigationResultResponse]).validate_python(payload))
        except FileNotFoundError as error:
            raise CaseArtifactError("investigation_cases.json is missing") from error
        except (OSError, json.JSONDecodeError, ValidationError) as error:
            raise CaseArtifactError("investigation_cases.json failed validation") from error


def get_case_repository() -> CaseRepository:
    return CaseRepository(settings.analysis_dir)


CaseRepositoryDependency = Annotated[CaseRepository, Depends(get_case_repository)]
router = APIRouter(prefix="/cases", tags=["cases"])


def _unavailable(error: CaseArtifactError) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "cases_unavailable",
            "message": str(error),
            "action": ("Run python -m agent.investigation against building_analysis.json."),
        },
    )


@router.get("", response_model=list[CaseListItemResponse])
def list_cases(
    repository: CaseRepositoryDependency,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[CaseListItemResponse]:
    try:
        results = repository.results()
    except CaseArtifactError as error:
        raise _unavailable(error) from error
    items = [
        CaseListItemResponse(
            case_id=result.case_file.case_id,
            target_id=result.target_id,
            created_at=result.case_file.created_at,
            total_score=result.case_file.score.total,
            review_level=result.case_file.score.level,
            finding_count=len(result.case_file.findings),
        )
        for result in results
        if result.case_file is not None
    ]
    return sorted(items, key=lambda item: (-item.total_score, item.case_id))[:limit]


@router.get("/targets/{target_id}", response_model=InvestigationResultResponse)
def case_for_target(
    target_id: str,
    repository: CaseRepositoryDependency,
) -> InvestigationResultResponse:
    try:
        results = repository.results()
    except CaseArtifactError as error:
        raise _unavailable(error) from error
    for result in results:
        if result.target_id == target_id:
            return result
    raise HTTPException(
        status_code=404,
        detail={"code": "case_target_not_found", "target_id": target_id},
    )


@router.get("/{case_id}", response_model=InvestigationResultResponse)
def case_detail(
    case_id: str,
    repository: CaseRepositoryDependency,
) -> InvestigationResultResponse:
    try:
        results = repository.results()
    except CaseArtifactError as error:
        raise _unavailable(error) from error
    for result in results:
        if result.trace and result.trace[0].case_id == case_id:
            return result
    raise HTTPException(
        status_code=404,
        detail={"code": "case_not_found", "case_id": case_id},
    )


@router.get("/{case_id}/download", response_class=Response)
def download_case(case_id: str, repository: CaseRepositoryDependency) -> Response:
    result = case_detail(case_id, repository)
    if result.case_file is None:
        raise HTTPException(status_code=404, detail={"code": "case_not_found", "case_id": case_id})
    body = result.case_file.model_dump_json(indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="phantomcare-{case_id}.json"'},
    )
