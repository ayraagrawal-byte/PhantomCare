from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from engine.clustering import calculate_clustering_baseline
from engine.indicators import IndicatorEngine, OwnershipMetrics
from engine.ownership import OwnershipNetwork, build_ownership_network
from engine.scoring import ScoreDecision, score_indicators
from pipeline.cms import CmsBundleResult, import_cms_bundle, write_bundle
from pipeline.costar_extract import CostarExtract
from pipeline.group_buildings import group_by_building, normalize_enrollment_addresses


@dataclass(frozen=True)
class BuildingAnalysis:
    building_id: str
    building_key: str
    hospice_count: int
    indicators: tuple[dict[str, Any], ...]
    priority: dict[str, Any]
    costar_match_status: str


@dataclass(frozen=True)
class AnalysisRun:
    imported: CmsBundleResult
    normalized_enrollments: pd.DataFrame
    ranked_buildings: pd.DataFrame
    ownership: OwnershipNetwork
    buildings: tuple[BuildingAnalysis, ...]
    generated_at: datetime


def _costar_match(
    extract: CostarExtract | None, building_key: str
) -> tuple[dict[str, Any] | None, str]:
    if extract is None:
        return None, "not_configured"
    matches = extract.lookup(building_key)
    if not matches:
        return None, "no_exact_match"
    if len(matches) > 1:
        return None, "ambiguous_exact_match"
    return matches[0], "exact_match"


def run_analysis(
    *,
    enrollments_source: str | Path,
    owners_source: str | Path,
    additional_addresses_source: str | Path,
    la_county_zip_codes: set[str] | None = None,
    costar_kit: str | Path | None = None,
    run_at: datetime | None = None,
) -> AnalysisRun:
    timestamp = run_at or datetime.now(UTC)
    imported = import_cms_bundle(
        enrollments_source,
        owners_source,
        additional_addresses_source,
        la_county_zip_codes=la_county_zip_codes,
    )
    normalized = normalize_enrollment_addresses(imported.enrollments)
    buildings = group_by_building(normalized)
    ranked = calculate_clustering_baseline(buildings, normalized)
    ownership = build_ownership_network(imported.owners, normalized, ranked)
    ownership_by_building = {
        item.building_id: item.metrics for item in ownership.buildings
    }
    extract = CostarExtract(costar_kit) if costar_kit else None
    indicator_engine = IndicatorEngine()
    results: list[BuildingAnalysis] = []

    for _, row in ranked.iterrows():
        building_id = str(row["BUILDING_ID"])
        building_key = str(row["BUILDING_KEY"])
        costar, match_status = _costar_match(extract, building_key)
        indicators = indicator_engine.evaluate_building(
            building_id=building_id,
            hospice_count=int(row["HOSPICE_COUNT"]),
            percentile=float(row["HOSPICE_COUNT_PERCENTILE"]),
            county_median=float(row["LA_MEDIAN_HOSPICES_PER_BUILDING"]),
            costar=costar,
            ownership=ownership_by_building.get(building_id, OwnershipMetrics()),
            run_at=timestamp,
        )
        decision: ScoreDecision = score_indicators(
            target_id=building_id,
            indicators=indicators,
        )
        results.append(
            BuildingAnalysis(
                building_id=building_id,
                building_key=building_key,
                hospice_count=int(row["HOSPICE_COUNT"]),
                indicators=tuple(
                    indicator.model_dump(mode="json") for indicator in indicators
                ),
                priority=decision.to_dict(),
                costar_match_status=match_status,
            )
        )

    return AnalysisRun(
        imported=imported,
        normalized_enrollments=normalized,
        ranked_buildings=ranked,
        ownership=ownership,
        buildings=tuple(results),
        generated_at=timestamp,
    )


def write_analysis(run: AnalysisRun, output_dir: str | Path) -> None:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    write_bundle(run.imported, destination)
    run.normalized_enrollments.to_csv(
        destination / "hospice_enrollments_normalized.csv", index=False
    )
    run.ranked_buildings.to_csv(destination / "buildings_ranked.csv", index=False)
    (destination / "ownership_network.json").write_text(
        json.dumps(run.ownership.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    (destination / "building_analysis.json").write_text(
        json.dumps([asdict(item) for item in run.buildings], indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "generated_at": run.generated_at.isoformat(),
        "enrollment_count": int(run.normalized_enrollments["ENROLLMENT_ID"].nunique()),
        "building_count": len(run.buildings),
        "high_priority_count": sum(
            item.priority["score"]["level"] == "high_priority" for item in run.buildings
        ),
        "worth_a_look_count": sum(
            item.priority["score"]["level"] == "worth_a_look" for item in run.buildings
        ),
        "disclaimer": "Review priorities are screening aids, not findings of fraud.",
    }
    (destination / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PhantomCare ingestion through scoring.")
    parser.add_argument("--enrollments", type=Path, required=True)
    parser.add_argument("--owners", type=Path, required=True)
    parser.add_argument("--additional-addresses", type=Path, required=True)
    parser.add_argument("--la-county-zip-file", type=Path)
    parser.add_argument("--costar-kit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    zip_codes = None
    if args.la_county_zip_file:
        zip_codes = {
            line.strip()
            for line in args.la_county_zip_file.read_text().splitlines()
            if line.strip()
        }
    run = run_analysis(
        enrollments_source=args.enrollments,
        owners_source=args.owners,
        additional_addresses_source=args.additional_addresses,
        la_county_zip_codes=zip_codes,
        costar_kit=args.costar_kit,
    )
    write_analysis(run, args.output)


if __name__ == "__main__":
    main()
