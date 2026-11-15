from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel

from agent.investigation import investigate_building
from api.analysis import AnalysisRepository
from api.schemas import BuildingAnalysisResponse


class AgentToolTrace(BaseModel):
    tool_name: str
    purpose: str
    input_identifiers: dict[str, str]
    result_summary: str
    evidence_references: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()


class FusionLayer(BaseModel):
    source: Literal["CMS", "CoStar", "Vexcel", "Ownership"]
    establishes: tuple[str, ...]
    evidence_references: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class InteractiveInvestigation(BaseModel):
    target_id: str
    mode: Literal["live_ai", "deterministic_fallback"]
    model: str | None = None
    generated_at: datetime
    reasoning_summary: str
    recommended_next_step: str
    unknowns: tuple[str, ...]
    tool_trace: tuple[AgentToolTrace, ...]
    fusion_layers: tuple[FusionLayer, ...]
    review_checklist: tuple[str, ...] = ()
    disclaimer: str = "These are questions for human review, not conclusions of fraud."
    fallback_reason: str | None = None


def _evidence_refs(
    building: BuildingAnalysisResponse, indicator_name: str | None = None
) -> tuple[str, ...]:
    refs = {
        f"{evidence.source.value}:{evidence.record_id}"
        for indicator in building.indicators
        if indicator_name is None or indicator.indicator == indicator_name
        for evidence in indicator.evidence
    }
    return tuple(sorted(refs))


class EvidenceToolkit:
    """Read-only, artifact-backed evidence tools with an auditable call log."""

    def __init__(
        self, repository: AnalysisRepository, target_id: str, *, maximum_tool_calls: int = 8
    ) -> None:
        self.repository = repository
        self.target_id = target_id
        self.maximum_tool_calls = maximum_tool_calls
        self.trace: list[AgentToolTrace] = []

    def _building(self) -> BuildingAnalysisResponse:
        for building in self.repository.buildings():
            if building.building_id == self.target_id:
                return building
        raise KeyError(self.target_id)

    def _record(
        self,
        name: str,
        purpose: str,
        summary: str,
        refs: tuple[str, ...] = (),
        missing: tuple[str, ...] = (),
    ) -> None:
        if len(self.trace) >= self.maximum_tool_calls:
            raise RuntimeError("maximum evidence tool calls reached")
        self.trace.append(
            AgentToolTrace(
                tool_name=name,
                purpose=purpose,
                input_identifiers={"target_id": self.target_id},
                result_summary=summary,
                evidence_references=refs,
                missing_information=missing,
            )
        )

    def get_building_profile(self) -> dict[str, Any]:
        building = self._building()
        result = {
            "building_id": building.building_id,
            "address": building.building_key,
            "hospice_count": building.hospice_count,
            "score": building.priority.score.total,
            "review_level": building.priority.score.level.value,
            "score_model": building.priority.score.model_version,
        }
        self._record(
            "get_building_profile",
            "Establish the selected target and deterministic screening result.",
            f"Loaded {building.building_key} with {building.hospice_count} registrations.",
            _evidence_refs(building, "address_clustering"),
        )
        return result

    def get_cms_enrollments(self) -> dict[str, Any]:
        building = self._building()
        refs = _evidence_refs(building, "address_clustering")
        result = {
            "registration_count": building.hospice_count,
            "normalized_address": building.building_key,
        }
        self._record(
            "get_cms_enrollments",
            "Review CMS registration concentration at the normalized address.",
            f"CMS-derived analysis groups {building.hospice_count} registrations at this address.",
            refs,
            ("Individual enrollment rows are not included in the public runtime bundle.",),
        )
        return result

    def get_ownership_network(self) -> dict[str, Any]:
        network = self.repository.network(self.target_id)
        owners = [node for node in network.nodes if node.kind == "owner"]
        hospices = [node for node in network.nodes if node.kind == "hospice"]
        result = {
            "masked_owner_count": len(owners),
            "hospice_node_count": len(hospices),
            "link_count": len(network.links),
            "owners": [node.model_dump(mode="json") for node in owners],
        }
        building = self._building()
        summary = (
            f"Loaded {len(owners)} masked/organizational owner nodes and "
            f"{len(network.links)} links."
        )
        self._record(
            "get_ownership_network",
            "Inspect masked aggregate ownership relationships.",
            summary,
            _evidence_refs(building, "ownership_network"),
            tuple(network.limitations),
        )
        return result

    def get_costar_property_context(self) -> dict[str, Any]:
        building = self._building()
        context = building.building_context
        refs = tuple(ref for ref in _evidence_refs(building) if ref.startswith("costar:"))
        if context is None:
            result = {"match_status": building.costar_match_status, "property": None}
            self._record(
                "get_costar_property_context",
                "Compare registration concentration with physical-property metadata.",
                f"No exact CoStar property was available ({building.costar_match_status}).",
                refs,
                ("Building type, area, and occupancy context are unavailable.",),
            )
            return result
        result = {
            "match_status": building.costar_match_status,
            "property": context.model_dump(mode="json"),
        }
        self._record(
            "get_costar_property_context",
            "Compare registration concentration with physical-property metadata.",
            f"Loaded exact CoStar property {context.property_id}.",
            refs or (f"costar:{context.property_id}",),
            (() if context.occupancy_scope else ("Occupancy scope was not reported.",)),
        )
        return result

    def get_vexcel_aerial_evidence(self) -> dict[str, Any]:
        try:
            aerial = self.repository.aerial(self.target_id)
        except KeyError:
            self._record(
                "get_vexcel_aerial_evidence",
                "Check whether exterior geographic context is available.",
                "No Vexcel aerial evidence is available for this target.",
                missing=("Aerial imagery is unavailable.",),
            )
            return {"available": False}
        ref = f"vexcel:{aerial.image_sha256}"
        self._record(
            "get_vexcel_aerial_evidence",
            "Inspect imagery provenance and limitations without inferring interior use.",
            f"Loaded Vexcel {aerial.kind} metadata retrieved {aerial.retrieved_at.isoformat()}.",
            (ref,),
            tuple(aerial.limitations),
        )
        return {"available": True, **aerial.model_dump(mode="json")}

    def get_indicator_breakdown(self) -> list[dict[str, Any]]:
        building = self._building()
        result = [indicator.model_dump(mode="json") for indicator in building.indicators]
        self._record(
            "get_indicator_breakdown",
            "Inspect deterministic score inputs without modifying the score.",
            f"Loaded {len(result)} versioned indicator results.",
            _evidence_refs(building),
            tuple(building.priority.missing_indicators),
        )
        return result

    def get_source_records(self) -> list[dict[str, Any]]:
        building = self._building()
        records = {
            (evidence.source.value, evidence.record_id): evidence
            for indicator in building.indicators
            for evidence in indicator.evidence
        }
        result = [
            evidence.model_dump(mode="json")
            for evidence in sorted(
                records.values(), key=lambda item: (item.source, item.record_id)
            )
        ]
        self._record(
            "get_source_records",
            "Retrieve source pointers attached to deterministic indicators.",
            f"Loaded {len(result)} unique evidence record pointer(s).",
            _evidence_refs(building),
        )
        return result

    def generate_case_report(self) -> dict[str, Any]:
        building = self._building()
        result = investigate_building(building)
        refs = tuple(
            sorted(
                {
                    f"{evidence.source.value}:{evidence.record_id}"
                    for event in result.trace
                    for evidence in event.evidence
                }
            )
        )
        summary = (
            "Generated the existing deterministic evidence-bound case report."
            if result.case_file
            else f"Deterministic case generation stopped: {result.stopped_reason}"
        )
        self._record(
            "generate_case_report",
            "Generate a neutral case artifact without replacing the screening score.",
            summary,
            refs,
            (() if result.case_file else ((result.stopped_reason or "No case generated."),)),
        )
        return result.to_dict()


def _fallback_investigation(
    toolkit: EvidenceToolkit, *, reason: str = "live_ai_not_enabled"
) -> InteractiveInvestigation:
    profile = toolkit.get_building_profile()
    toolkit.get_cms_enrollments()
    toolkit.get_ownership_network()
    costar = toolkit.get_costar_property_context()
    aerial = toolkit.get_vexcel_aerial_evidence()
    toolkit.get_indicator_breakdown()
    toolkit.get_source_records()
    toolkit.generate_case_report()
    unknowns = sorted({item for event in toolkit.trace for item in event.missing_information})
    available = []
    if costar.get("property"):
        available.append("CoStar property context")
    if aerial.get("available"):
        available.append("Vexcel exterior context")
    additions = ", ".join(available) if available else "no matched physical-property layer"
    summary = (
        f"CMS-derived records group {profile['hospice_count']} hospice registrations at the "
        f"selected address. Deterministic scoring prioritizes the target for review; {additions} "
        "is available. Registration concentration and exterior context do not establish "
        "improper conduct."
    )
    return InteractiveInvestigation(
        target_id=toolkit.target_id,
        mode="deterministic_fallback",
        generated_at=datetime.now(UTC),
        reasoning_summary=summary,
        recommended_next_step=(
            "Verify current licensing and occupancy records, then request interior or tenant "
            "evidence only if authorized and useful."
        ),
        unknowns=tuple(unknowns),
        tool_trace=tuple(toolkit.trace),
        fusion_layers=_fusion_layers(toolkit),
        review_checklist=_review_checklist(toolkit),
        fallback_reason=reason,
    )


def _review_checklist(toolkit: EvidenceToolkit) -> tuple[str, ...]:
    """Deterministic human-review steps derived from what the tools actually returned."""
    events = {event.tool_name: event for event in toolkit.trace}
    items = [
        "Confirm each cited evidence reference against its source record before relying on it.",
        "Verify current CMS enrollment and state licensing status for each registration.",
    ]
    costar = events.get("get_costar_property_context")
    if costar is None or costar.result_summary.startswith("No exact CoStar"):
        items.append(
            "No exact CoStar property record: confirm building type and leasable area from "
            "another authorized source before weighing space-based context."
        )
    else:
        items.append("Confirm the CoStar property match is the same building and suite.")
    vexcel = events.get("get_vexcel_aerial_evidence")
    if vexcel is None or not vexcel.evidence_references:
        items.append("No Vexcel imagery: do not draw conclusions about the exterior.")
    else:
        items.append(
            "Treat Vexcel imagery as exterior context only; it cannot show interior use or "
            "whether a hospice operates."
        )
    items.extend(
        (
            "Keep owner identities masked; do not attempt to re-identify individuals.",
            "Consider legitimate explanations (administrative offices, shared corporate "
            "ownership) before any referral.",
            "Record the reviewer decision and rationale; the screening score is not a finding.",
        )
    )
    return tuple(items)


def _fusion_layers(toolkit: EvidenceToolkit) -> tuple[FusionLayer, ...]:
    events = {event.tool_name: event for event in toolkit.trace}
    mapping = (
        ("CMS", "get_cms_enrollments"),
        ("Ownership", "get_ownership_network"),
        ("CoStar", "get_costar_property_context"),
        ("Vexcel", "get_vexcel_aerial_evidence"),
    )
    return tuple(
        FusionLayer(
            source=source,
            establishes=(events[name].result_summary,),
            evidence_references=events[name].evidence_references,
            limitations=events[name].missing_information,
        )
        for source, name in mapping
        if name in events
    )


_CITATION_PATTERN = re.compile(
    r"\b(?:cms_hospice_enrollments|cms_hospice_all_owners|cms_hospice_additional_addresses"
    r"|costar|vexcel|matterport|derived):[a-z0-9_\-]+(?:\.[a-z0-9_\-]+)*"
)
# Neutral disclaimers that mention fraud only to deny it are allowed.
_NEUTRAL_FRAUD_PHRASES = (
    "not evidence of fraud",
    "not proof of fraud",
    "not conclusions of fraud",
    "not a conclusion of fraud",
    "not an allegation of fraud",
    "no finding of fraud",
    "does not establish fraud",
    "do not establish fraud",
    "without alleging fraud",
)
_ALLEGATION_PATTERN = re.compile(
    r"\b(?:fraud\w*|scam\w*|sham|bogus|illegal\w*|criminal\w*|kickback\w*)\b"
    r"|proves? no hospice|no hospice operates"
)


def _validated_agent_summary(content: object, trace: list[AgentToolTrace]) -> str | None:
    """Accept a model summary only if it is neutral and cites only tool-returned evidence."""
    if not isinstance(content, str) or not content.strip():
        return None
    normalized = content.casefold()
    screened = normalized
    for phrase in _NEUTRAL_FRAUD_PHRASES:
        screened = screened.replace(phrase, " ")
    if _ALLEGATION_PATTERN.search(screened):
        return None
    references = {
        reference.casefold()
        for event in trace
        for reference in event.evidence_references
    }
    cited = set(_CITATION_PATTERN.findall(normalized))
    if not references or not cited or not cited <= references:
        return None
    return content.strip()[:4000]


def investigate_interactively(
    repository: AnalysisRepository,
    target_id: str,
    *,
    model: str | None = None,
    maximum_tool_calls: int = 8,
    maximum_tokens: int = 1200,
    timeout_seconds: int = 25,
    maximum_retries: int = 0,
    fallback_reason: str = "live_ai_not_enabled",
) -> InteractiveInvestigation:
    if maximum_tool_calls < 8:
        raise ValueError("maximum_tool_calls must permit the eight-tool fallback")
    toolkit = EvidenceToolkit(repository, target_id, maximum_tool_calls=maximum_tool_calls)
    if not model:
        return _fallback_investigation(toolkit, reason=fallback_reason)
    try:
        from deepagents import create_deep_agent
        from langchain.chat_models import init_chat_model
        from langchain_core.tools import StructuredTool
    except ImportError:
        return _fallback_investigation(toolkit, reason="agent_dependency_unavailable")

    functions = [
        toolkit.get_building_profile,
        toolkit.get_cms_enrollments,
        toolkit.get_ownership_network,
        toolkit.get_costar_property_context,
        toolkit.get_vexcel_aerial_evidence,
        toolkit.get_indicator_breakdown,
        toolkit.get_source_records,
        toolkit.generate_case_report,
    ]
    tools = [
        StructuredTool.from_function(
            function,
            name=function.__name__,
            description=f"Read validated evidence using {function.__name__}.",
        )
        for function in functions
    ]
    try:
        bounded_model = init_chat_model(
            model,
            max_tokens=maximum_tokens,
            max_retries=maximum_retries,
            timeout=timeout_seconds,
        )
        agent = create_deep_agent(
            model=bounded_model,
            tools=tools,
            system_prompt=(
                "Investigate a hospice registration screening target using only provided tools. "
                "Deterministic scores are authoritative and must not be changed. Never allege "
                "fraud, infer interior use from aerial imagery, reveal masked identities, or "
                "invent evidence. Compare sources, identify alternatives and missing facts, then "
                "give a neutral concise report with evidence reference IDs returned by tools."
            ),
        )
        result = agent.invoke(
            {
                "messages": [
                    {"role": "user", "content": f"Investigate target {target_id}."}
                ],
                "files": {},
            },
            config={"recursion_limit": maximum_tool_calls * 2 + 4},
        )
    except Exception:
        return _fallback_investigation(
            EvidenceToolkit(repository, target_id, maximum_tool_calls=maximum_tool_calls),
            reason="live_ai_execution_failed",
        )
    messages = result.get("messages", [])
    content = getattr(messages[-1], "content", "") if messages else ""
    validated_summary = _validated_agent_summary(content, toolkit.trace)
    if validated_summary is None:
        return _fallback_investigation(
            EvidenceToolkit(repository, target_id, maximum_tool_calls=maximum_tool_calls),
            reason="live_ai_output_failed_validation",
        )
    unknowns = sorted({item for event in toolkit.trace for item in event.missing_information})
    return InteractiveInvestigation(
        target_id=target_id,
        mode="live_ai",
        model=model,
        generated_at=datetime.now(UTC),
        reasoning_summary=validated_summary,
        recommended_next_step=(
            "Review the cited evidence and verify licensing or occupancy records where the agent "
            "identified missing information."
        ),
        unknowns=tuple(unknowns),
        tool_trace=tuple(toolkit.trace),
        fusion_layers=_fusion_layers(toolkit),
        review_checklist=_review_checklist(toolkit),
        fallback_reason=None,
    )


def investigation_json(result: InteractiveInvestigation) -> str:
    return json.dumps(result.model_dump(mode="json"), indent=2)
