from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from api.contracts import (
    CaseFile,
    CaseFinding,
    EvidenceRecord,
    IndicatorResult,
    ReviewLevel,
    TraceEvent,
    TraceEventType,
)
from api.schemas import BuildingAnalysisResponse


@dataclass(frozen=True)
class InvestigationPolicy:
    minimum_case_score: float = 35
    minimum_finding_score: float = 35
    minimum_evidence_records: int = 2
    maximum_findings: int = 5
    maximum_limitation_penalty: float = 0.3


@dataclass(frozen=True)
class InvestigationResult:
    target_id: str
    case_file: CaseFile | None
    trace: tuple[TraceEvent, ...]
    stopped_reason: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "target_id": self.target_id,
            "case_file": (
                self.case_file.model_dump(mode="json") if self.case_file else None
            ),
            "trace": [event.model_dump(mode="json") for event in self.trace],
            "stopped_reason": self.stopped_reason,
        }


FINDING_LANGUAGE = {
    "address_clustering": (
        "Elevated address clustering",
        "The registration count at this normalized building address is elevated relative "
        "to the county building baseline.",
    ),
    "building_type_fit": (
        "Building-use context",
        "The exact-matched property classification provides context that may merit review "
        "alongside the registration records.",
    ),
    "space_per_hospice": (
        "Building-area ratio",
        "The calculated building area per registered hospice is below the configured "
        "screening threshold.",
    ),
    "ownership_network": (
        "Shared ownership links",
        "Masked aggregate ownership records connect multiple retained hospice enrollments.",
    ),
}


def _stable_id(prefix: str, *parts: str) -> str:
    value = "\x1f".join(parts)
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:20]}"


def _event(
    *,
    case_id: str,
    index: int,
    event_type: TraceEventType,
    message: str,
    occurred_at: datetime,
    evidence: tuple[EvidenceRecord, ...] = (),
) -> TraceEvent:
    return TraceEvent(
        event_id=_stable_id("evt", case_id, str(index), event_type.value),
        case_id=case_id,
        occurred_at=occurred_at,
        event_type=event_type,
        message=message,
        evidence=evidence,
    )


def _finding(
    indicator: IndicatorResult,
    policy: InvestigationPolicy,
) -> CaseFinding | None:
    language = FINDING_LANGUAGE.get(indicator.indicator)
    if (
        language is None
        or indicator.score_contribution < policy.minimum_finding_score
        or not indicator.evidence
    ):
        return None
    penalty = min(
        len(indicator.limitations) * 0.1,
        policy.maximum_limitation_penalty,
    )
    strength = max(0, min(1, indicator.score_contribution / 100 - penalty))
    return CaseFinding(
        title=language[0],
        summary=language[1],
        strength=round(strength, 2),
        evidence=indicator.evidence,
        limitations=indicator.limitations,
    )


def investigate_building(
    building: BuildingAnalysisResponse,
    *,
    policy: InvestigationPolicy | None = None,
    run_at: datetime | None = None,
) -> InvestigationResult:
    active_policy = policy or InvestigationPolicy()
    timestamp = run_at or datetime.now(UTC)
    case_id = _stable_id(
        "case",
        building.building_id,
        building.priority.score.model_version,
        str(building.priority.score.total),
    )
    trace = [
        _event(
            case_id=case_id,
            index=0,
            event_type=TraceEventType.STARTED,
            message=f"Started evidence review for {building.building_id}.",
            occurred_at=timestamp,
        )
    ]
    evidence_count = sum(len(indicator.evidence) for indicator in building.indicators)
    if (
        building.priority.score.level == ReviewLevel.NO_INDICATORS
        or building.priority.score.total < active_policy.minimum_case_score
    ):
        reason = "Review priority did not meet the case-file threshold."
        trace.append(
            _event(
                case_id=case_id,
                index=1,
                event_type=TraceEventType.EARLY_STOPPED,
                message=reason,
                occurred_at=timestamp,
            )
        )
        return InvestigationResult(building.building_id, None, tuple(trace), reason)
    if evidence_count < active_policy.minimum_evidence_records:
        reason = (
            f"Only {evidence_count} evidence record(s) were available; "
            f"at least {active_policy.minimum_evidence_records} are required."
        )
        trace.append(
            _event(
                case_id=case_id,
                index=1,
                event_type=TraceEventType.EARLY_STOPPED,
                message=reason,
                occurred_at=timestamp,
            )
        )
        return InvestigationResult(building.building_id, None, tuple(trace), reason)

    trace.append(
        _event(
            case_id=case_id,
            index=1,
            event_type=TraceEventType.TOOL_CALLED,
            message="Reviewed deterministic indicators and their attached evidence.",
            occurred_at=timestamp,
        )
    )
    candidates = [
        finding
        for indicator in building.indicators
        if (finding := _finding(indicator, active_policy)) is not None
    ]
    candidates.sort(key=lambda finding: (-finding.strength, finding.title))
    candidates = candidates[: active_policy.maximum_findings]
    candidate_evidence = tuple(
        evidence for finding in candidates for evidence in finding.evidence
    )
    trace.append(
        _event(
            case_id=case_id,
            index=2,
            event_type=TraceEventType.TOOL_COMPLETED,
            message=f"Produced {len(candidates)} evidence-backed candidate finding(s).",
            occurred_at=timestamp,
            evidence=candidate_evidence,
        )
    )
    if not candidates:
        reason = "No indicator met the evidence-backed finding threshold."
        trace.append(
            _event(
                case_id=case_id,
                index=3,
                event_type=TraceEventType.EARLY_STOPPED,
                message=reason,
                occurred_at=timestamp,
            )
        )
        return InvestigationResult(building.building_id, None, tuple(trace), reason)

    limitation_count = sum(len(finding.limitations) for finding in candidates)
    trace.append(
        _event(
            case_id=case_id,
            index=3,
            event_type=TraceEventType.SKEPTIC_REVIEW,
            message=(
                f"Skeptical review retained {len(candidates)} finding(s) and attached "
                f"{limitation_count} limitation statement(s); strength values include "
                "the configured limitation penalty."
            ),
            occurred_at=timestamp,
            evidence=candidate_evidence,
        )
    )
    case_file = CaseFile(
        case_id=case_id,
        target_id=building.building_id,
        created_at=timestamp,
        score=building.priority.score,
        findings=tuple(candidates),
    )
    trace.append(
        _event(
            case_id=case_id,
            index=4,
            event_type=TraceEventType.CASE_WRITTEN,
            message="Wrote a neutral case file with evidence and limitations.",
            occurred_at=timestamp,
            evidence=candidate_evidence,
        )
    )
    return InvestigationResult(building.building_id, case_file, tuple(trace), None)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create evidence-bound case files from building analysis artifacts."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    results = [
        investigate_building(BuildingAnalysisResponse.model_validate(item)).to_dict()
        for item in payload
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
