from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from api.contracts import EvidenceRecord, IndicatorResult, SourceDataset


@dataclass(frozen=True)
class IndicatorThresholds:
    clustering_percentile_high: float = 99
    clustering_percentile_elevated: float = 95
    clustering_percentile_watch: float = 90
    space_per_hospice_critical: float = 250
    space_per_hospice_low: float = 500
    space_per_hospice_watch: float = 1000
    owner_hospice_count_high: int = 10
    owner_hospice_count_watch: int = 5


@dataclass(frozen=True)
class OwnershipMetrics:
    max_hospices_per_owner: int = 0
    owners_shared_across_hospices: int = 0
    shared_owner_address_count: int = 0


@dataclass(frozen=True)
class AerialReview:
    reviewer: str
    reviewed_at: datetime
    observations: tuple[str, ...]
    image_record_id: str


def _evidence(
    *,
    source: SourceDataset,
    record_id: str,
    fields: dict[str, Any],
    retrieved_at: datetime,
    notes: tuple[str, ...] = (),
) -> EvidenceRecord:
    return EvidenceRecord(
        source=source,
        record_id=record_id,
        retrieved_at=retrieved_at,
        fields=fields,
        notes=notes,
    )


class IndicatorEngine:
    def __init__(self, thresholds: IndicatorThresholds | None = None) -> None:
        self.thresholds = thresholds or IndicatorThresholds()

    def address_clustering(
        self,
        *,
        building_id: str,
        hospice_count: int,
        percentile: float,
        county_median: float,
        run_at: datetime,
    ) -> IndicatorResult:
        if percentile >= self.thresholds.clustering_percentile_high:
            score = 100.0
        elif percentile >= self.thresholds.clustering_percentile_elevated:
            score = 80.0
        elif percentile >= self.thresholds.clustering_percentile_watch:
            score = 60.0
        elif hospice_count > county_median:
            score = 35.0
        else:
            score = 0.0
        return IndicatorResult(
            indicator="address_clustering",
            value={
                "hospice_count": hospice_count,
                "la_county_percentile": percentile,
                "la_county_median": county_median,
            },
            score_contribution=score,
            evidence=(
                _evidence(
                    source=SourceDataset.DERIVED,
                    record_id=building_id,
                    retrieved_at=run_at,
                    fields={
                        "hospice_count": hospice_count,
                        "la_county_percentile": percentile,
                        "la_county_median": county_median,
                    },
                    notes=("Calculated from normalized CMS enrollment addresses.",),
                ),
            ),
            limitations=(
                "Clustering alone does not show that any enrollment or organization is improper.",
            ),
        )

    def building_type_fit(
        self,
        *,
        building_id: str,
        costar: dict[str, Any] | None,
        run_at: datetime,
    ) -> IndicatorResult:
        if not costar:
            return IndicatorResult(
                indicator="building_type_fit",
                value={"status": "no_building_data"},
                score_contribution=0,
                evidence=(),
                limitations=("No CoStar property match was available.",),
            )

        labels = " ".join(
            str(costar.get(field) or "")
            for field in ("property_type", "property_subtype", "building_name")
        ).lower()
        high_context = ("executive suite", "business center", "virtual office")
        medical_context = ("medical office", "healthcare", "hospital")
        if any(term in labels for term in high_context):
            score = 100.0
            classification = "executive_suite_or_virtual_office_context"
        elif any(term in labels for term in medical_context):
            score = 0.0
            classification = "medical_use_context"
        elif "office" in labels:
            score = 25.0
            classification = "generic_office_context"
        else:
            score = 0.0
            classification = "other_or_unknown_context"

        source = costar.get("source") or {}
        return IndicatorResult(
            indicator="building_type_fit",
            value={
                "classification": classification,
                "property_type": costar.get("property_type"),
                "property_subtype": costar.get("property_subtype"),
                "building_name": costar.get("building_name"),
            },
            score_contribution=score,
            evidence=(
                _evidence(
                    source=SourceDataset.COSTAR,
                    record_id=str(costar.get("property_id", building_id)),
                    retrieved_at=run_at,
                    fields={
                        "property_type": costar.get("property_type"),
                        "property_subtype": costar.get("property_subtype"),
                        "building_name": costar.get("building_name"),
                        "source_line": source.get("line_number"),
                        "source_sha256": source.get("row_sha256"),
                    },
                ),
            ),
            limitations=(
                "A building classification describes context, not the legitimacy of its tenants.",
            ),
        )

    def space_per_hospice(
        self,
        *,
        building_id: str,
        hospice_count: int,
        costar: dict[str, Any] | None,
        run_at: datetime,
    ) -> IndicatorResult:
        if hospice_count <= 0:
            raise ValueError("hospice_count must be greater than zero")
        if not costar:
            return IndicatorResult(
                indicator="space_per_hospice",
                value={"status": "no_building_data"},
                score_contribution=0,
                evidence=(),
                limitations=("No CoStar area measurement was available.",),
            )

        area = costar.get("rentable_building_area_sqft")
        area_basis = "rentable_building_area_sqft"
        if area in (None, 0):
            area = costar.get("gross_building_area_sqft")
            area_basis = "gross_building_area_sqft"
        if area in (None, 0):
            return IndicatorResult(
                indicator="space_per_hospice",
                value={"status": "no_area_measurement"},
                score_contribution=0,
                evidence=(),
                limitations=("The matched CoStar record has no usable building-area measurement.",),
            )

        space = float(area) / hospice_count
        if space < self.thresholds.space_per_hospice_critical:
            score = 100.0
        elif space < self.thresholds.space_per_hospice_low:
            score = 75.0
        elif space < self.thresholds.space_per_hospice_watch:
            score = 45.0
        else:
            score = 0.0
        return IndicatorResult(
            indicator="space_per_hospice",
            value={
                "space_per_hospice_sqft": round(space, 2),
                "area_sqft": float(area),
                "area_basis": area_basis,
                "hospice_count": hospice_count,
            },
            score_contribution=score,
            evidence=(
                _evidence(
                    source=SourceDataset.COSTAR,
                    record_id=str(costar.get("property_id", building_id)),
                    retrieved_at=run_at,
                    fields={area_basis: float(area)},
                ),
                _evidence(
                    source=SourceDataset.DERIVED,
                    record_id=building_id,
                    retrieved_at=run_at,
                    fields={"hospice_count": hospice_count},
                ),
            ),
            limitations=(
                "Area per registration is a screening ratio; administrative offices may be "
                "legitimate.",
                "The calculation does not show how much space any specific hospice leases.",
            ),
        )

    def ownership_network(
        self,
        *,
        building_id: str,
        metrics: OwnershipMetrics,
        run_at: datetime,
    ) -> IndicatorResult:
        if metrics.max_hospices_per_owner >= self.thresholds.owner_hospice_count_high:
            score = 100.0
        elif metrics.max_hospices_per_owner >= self.thresholds.owner_hospice_count_watch:
            score = 65.0
        elif metrics.owners_shared_across_hospices > 0:
            score = 35.0
        else:
            score = 0.0
        values = {
            "max_hospices_per_owner": metrics.max_hospices_per_owner,
            "owners_shared_across_hospices": metrics.owners_shared_across_hospices,
            "shared_owner_address_count": metrics.shared_owner_address_count,
        }
        return IndicatorResult(
            indicator="ownership_network",
            value=values,
            score_contribution=score,
            evidence=(
                _evidence(
                    source=SourceDataset.DERIVED,
                    record_id=building_id,
                    retrieved_at=run_at,
                    fields=values,
                    notes=("Individual owner names are masked in application outputs.",),
                ),
            ),
            limitations=(
                "Shared ownership is common in legitimate multi-entity healthcare organizations.",
            ),
        )

    def aerial_context(self, *, review: AerialReview | None) -> IndicatorResult:
        if review is None:
            return IndicatorResult(
                indicator="aerial_context",
                value={"status": "not_reviewed"},
                score_contribution=0,
                evidence=(),
                limitations=("No human-reviewed Vexcel imagery context is available.",),
            )
        return IndicatorResult(
            indicator="aerial_context",
            value={"observations": list(review.observations), "reviewer": review.reviewer},
            score_contribution=0,
            evidence=(
                _evidence(
                    source=SourceDataset.VEXCEL,
                    record_id=review.image_record_id,
                    retrieved_at=review.reviewed_at,
                    fields={"observations": list(review.observations)},
                    notes=(f"Human review by {review.reviewer}.",),
                ),
            ),
            limitations=(
                "Aerial imagery is contextual and is never scored as proof of hospice operations.",
            ),
        )

    def evaluate_building(
        self,
        *,
        building_id: str,
        hospice_count: int,
        percentile: float,
        county_median: float,
        costar: dict[str, Any] | None = None,
        ownership: OwnershipMetrics | None = None,
        aerial_review: AerialReview | None = None,
        run_at: datetime | None = None,
    ) -> tuple[IndicatorResult, ...]:
        timestamp = run_at or datetime.now(UTC)
        return (
            self.address_clustering(
                building_id=building_id,
                hospice_count=hospice_count,
                percentile=percentile,
                county_median=county_median,
                run_at=timestamp,
            ),
            self.building_type_fit(
                building_id=building_id,
                costar=costar,
                run_at=timestamp,
            ),
            self.space_per_hospice(
                building_id=building_id,
                hospice_count=hospice_count,
                costar=costar,
                run_at=timestamp,
            ),
            self.ownership_network(
                building_id=building_id,
                metrics=ownership or OwnershipMetrics(),
                run_at=timestamp,
            ),
            self.aerial_context(review=aerial_review),
        )

