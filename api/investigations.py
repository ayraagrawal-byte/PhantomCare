from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from agent.interactive import InteractiveInvestigation, investigate_interactively
from api.analysis import AnalysisArtifactError, AnalysisRepository, get_analysis_repository
from api.config import settings

router = APIRouter(prefix="/investigations", tags=["investigations"])
AnalysisRepositoryDependency = Annotated[AnalysisRepository, Depends(get_analysis_repository)]


@router.post("/{target_id}", response_model=InteractiveInvestigation)
def run_investigation(
    target_id: str,
    repository: AnalysisRepositoryDependency,
) -> InteractiveInvestigation:
    try:
        return investigate_interactively(repository, target_id, model=settings.agent_model)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "investigation_target_not_found", "target_id": target_id},
        ) from error
    except AnalysisArtifactError as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "investigation_evidence_unavailable", "message": str(error)},
        ) from error
