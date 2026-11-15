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
from api.contracts.geocodes import (
    CAMS_LAYER,
    CamsCache,
    CamsResult,
    ReviewedCache,
    ReviewedLocation,
    SupplementalCache,
    SupplementalResult,
)
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

    def aerial_locations(self) -> dict[str, AerialEvidenceResponse]:
        try:
            raw = self._read("vexcel_evidence.json")
        except AnalysisArtifactError:
            return {}
        locations: dict[str, AerialEvidenceResponse] = {}
        duplicates: set[str] = set()
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            try:
                evidence = AerialEvidenceResponse.model_validate({**item, "image_url": ""})
            except ValidationError:
                continue
            if evidence.target_id in locations:
                duplicates.add(evidence.target_id)
            locations[evidence.target_id] = evidence
        return {key: value for key, value in locations.items() if key not in duplicates}

    def cams_locations(self) -> dict[str, CamsResult] | None:
        try:
            data = (self.root / "cams_geocodes.json").read_bytes()
        except FileNotFoundError:
            return None
        except OSError:
            return {}
        try:
            cache = CamsCache.model_validate_json(data)
        except ValidationError:
            return {}
        return cache.results if cache.source_url == CAMS_LAYER else {}

    def supplemental_locations(self, cams: dict[str, CamsResult]) -> dict[str, SupplementalResult]:
        try:
            cache = SupplementalCache.model_validate_json(
                (self.root / "supplemental_geocodes.json").read_bytes()
            )
        except (OSError, ValidationError):
            return {}
        if cache.cams_url != CAMS_LAYER:
            return {}
        return {
            key: item for key, item in cache.results.items()
            if key in cams and cams[key].location is None
            and cams[key].building_key == item.building_key
        }

    def reviewed_locations(
        self, supplemental: dict[str, SupplementalResult]
    ) -> dict[str, ReviewedLocation]:
        try:
            cache = ReviewedCache.model_validate_json(
                (self.root / "reviewed_geocodes.json").read_bytes()
            )
        except (OSError, ValidationError):
            return {}
        return {
            key: item.location for key, item in cache.results.items()
            if item.location and key in supplemental and supplemental[key].anchor is None
            and supplemental[key].building_key == item.building_key
        }

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
        summary = repository.summary()
    except AnalysisArtifactError as error:
        raise _unavailable(error) from error
    cams = repository.cams_locations()
    if cams:
        supplemental = repository.supplemental_locations(cams)
        reviewed = repository.reviewed_locations(supplemental)
        summary.cams_mapped_count = sum(result.location is not None for result in cams.values())
        summary.cams_mapped_count += sum(
            result.verified is not None for result in supplemental.values()
        )
        summary.cams_mapped_count += sum(
            point.confidence == "verified" for point in reviewed.values()
        )
        summary.approximate_mapped_count = sum(
            result.anchor is not None and result.verified is None
            for result in supplemental.values()
        )
        summary.approximate_mapped_count += sum(
            point.confidence == "approximate" for point in reviewed.values()
        )
    return summary


@router.get("/buildings", response_model=list[BuildingListItemResponse])
def list_buildings(
    repository: AnalysisRepositoryDependency,
    level: ReviewLevel | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[BuildingListItemResponse]:
    try:
        buildings = repository.buildings()
    except AnalysisArtifactError as error:
        raise _unavailable(error) from error
    items = [BuildingListItemResponse.from_analysis(building) for building in buildings]
    if level is not None:
        items = [item for item in items if item.review_level == level]
    items = sorted(items, key=lambda item: (-item.total_score, item.building_id))[
        offset : offset + limit
    ]
    cams = repository.cams_locations()
    if cams is not None:
        supplemental = repository.supplemental_locations(cams)
        reviewed = repository.reviewed_locations(supplemental)
        for item in items:
            result = cams.get(item.building_id)
            location = approximate = None
            if result and result.building_key == item.building_key:
                location = result.location
                if extra := supplemental.get(item.building_id):
                    location = extra.verified
                    approximate = extra.anchor if location is None else None
                if review := reviewed.get(item.building_id):
                    if review.confidence == "verified":
                        location = review
                    else:
                        approximate = review
            item.verified_location = location
            item.approximate_location = approximate
            location = location or approximate
            item.latitude = location.latitude if location else None
            item.longitude = location.longitude if location else None
            item.coordinate_source = location.source if location else None
        return items

    aerial_locations = repository.aerial_locations()
    for item in items:
        if item.latitude is not None and item.longitude is not None:
            if item.costar_match_status == "exact_match":
                item.coordinate_source = "CoStar"
        elif (location := aerial_locations.get(item.building_id)) and (
            location.address == item.building_key
        ):
            item.latitude = location.latitude
            item.longitude = location.longitude
            item.coordinate_source = "Vexcel imagery address center"
    return items


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
