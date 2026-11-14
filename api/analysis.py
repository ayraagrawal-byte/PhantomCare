from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import TypeAdapter, ValidationError

from api.config import settings
from api.contracts import ReviewLevel
from api.schemas import (
    AerialEvidenceResponse,
    AnalysisSummaryResponse,
    BuildingAnalysisResponse,
    BuildingListItemResponse,
    BuildingNetworkResponse,
    OwnershipLinkResponse,
    OwnershipNodeResponse,
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

    def network(self, building_id: str) -> BuildingNetworkResponse:
        raw = self._read("ownership_network.json")
        if not isinstance(raw, dict):
            raise AnalysisArtifactError("ownership network failed validation")
        match = next(
            (item for item in raw.get("buildings", []) if item.get("building_id") == building_id),
            None,
        )
        if match is None:
            raise KeyError(building_id)
        owner_keys = set(match.get("owner_keys", []))
        owners = {
            item["owner_key"]: item
            for item in raw.get("owners", [])
            if item.get("owner_key") in owner_keys
        }
        edges = [item for item in raw.get("edges", []) if item.get("owner_key") in owner_keys]
        enrollment_ids = sorted({str(item["enrollment_id"]) for item in edges})
        nodes = [
            OwnershipNodeResponse(
                id=building_id,
                label="Selected building",
                kind="building",
                count=len(enrollment_ids) or 1,
            ),
            *(
                OwnershipNodeResponse(
                    id=key,
                    label=str(owner["display_name"]),
                    kind="owner",
                    is_masked=bool(owner.get("is_masked")),
                    count=max(1, int(owner.get("hospice_count", 1))),
                )
                for key, owner in sorted(owners.items())
            ),
            *(
                OwnershipNodeResponse(id=item, label=f"Hospice {index + 1}", kind="hospice")
                for index, item in enumerate(enrollment_ids)
            ),
        ]
        links = [OwnershipLinkResponse(source=building_id, target=item) for item in enrollment_ids]
        links.extend(
            OwnershipLinkResponse(source=str(item["enrollment_id"]), target=str(item["owner_key"]))
            for item in edges
        )
        return BuildingNetworkResponse(
            building_id=building_id,
            nodes=tuple(nodes),
            links=tuple(links),
            limitations=tuple(str(item) for item in raw.get("limitations", [])),
        )

    def aerial(self, building_id: str) -> AerialEvidenceResponse:
        raw = self._read("vexcel_evidence.json")
        if not isinstance(raw, list):
            raise AnalysisArtifactError("Vexcel evidence failed validation")
        match = next((item for item in raw if item.get("target_id") == building_id), None)
        if match is None:
            raise KeyError(building_id)
        payload = dict(match)
        payload.pop("image_filename", None)
        payload["image_url"] = f"/analysis/buildings/{building_id}/aerial/image"
        return AerialEvidenceResponse.model_validate(payload)

    def aerial_image(self, building_id: str) -> Path:
        evidence = self.aerial(building_id)
        manifest = self._read("vexcel_evidence.json")
        match = next(item for item in manifest if item.get("target_id") == building_id)
        filename = Path(str(match["image_filename"])).name
        path = (self.root / "vexcel" / filename).resolve()
        if path.parent != (self.root / "vexcel").resolve() or not path.is_file():
            raise AnalysisArtifactError("Vexcel evidence image is unavailable")
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence.image_sha256:
            raise AnalysisArtifactError("Vexcel evidence image failed integrity validation")
        return path


def get_analysis_repository() -> AnalysisRepository:
    return AnalysisRepository(settings.analysis_dir)


router = APIRouter(prefix="/analysis", tags=["analysis"])
AnalysisRepositoryDependency = Annotated[AnalysisRepository, Depends(get_analysis_repository)]


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


@router.get("/buildings/{building_id}/network", response_model=BuildingNetworkResponse)
def building_network(
    building_id: str, repository: AnalysisRepositoryDependency
) -> BuildingNetworkResponse:
    try:
        return repository.network(building_id)
    except AnalysisArtifactError as error:
        raise _unavailable(error) from error
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "building_network_not_found", "building_id": building_id},
        ) from error


@router.get("/buildings/{building_id}/aerial", response_model=AerialEvidenceResponse)
def building_aerial(
    building_id: str, repository: AnalysisRepositoryDependency
) -> AerialEvidenceResponse:
    try:
        return repository.aerial(building_id)
    except AnalysisArtifactError as error:
        raise _unavailable(error) from error
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "aerial_evidence_not_found", "building_id": building_id},
        ) from error


@router.get("/buildings/{building_id}/aerial/image", response_class=FileResponse)
def building_aerial_image(
    building_id: str, repository: AnalysisRepositoryDependency
) -> FileResponse:
    try:
        path = repository.aerial_image(building_id)
    except AnalysisArtifactError as error:
        raise _unavailable(error) from error
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "aerial_evidence_not_found", "building_id": building_id},
        ) from error
    return FileResponse(path, media_type="image/jpeg", filename=f"{building_id}-vexcel-ortho.jpg")
