from pathlib import Path

import pytest

from agent.interactive import (
    AgentToolTrace,
    EvidenceToolkit,
    _validated_agent_summary,
    investigate_interactively,
)
from api.analysis import AnalysisRepository

TARGET_ID = "bldg_793ac00ed2ae2571"


@pytest.fixture
def repository() -> AnalysisRepository:
    return AnalysisRepository(Path("data/runtime"))


def test_deterministic_fallback_runs_real_read_only_tools(
    repository: AnalysisRepository,
) -> None:
    result = investigate_interactively(repository, TARGET_ID)

    assert result.mode == "deterministic_fallback"
    assert result.target_id == TARGET_ID
    assert [event.tool_name for event in result.tool_trace] == [
        "get_building_profile",
        "get_cms_enrollments",
        "get_ownership_network",
        "get_costar_property_context",
        "get_vexcel_aerial_evidence",
        "get_indicator_breakdown",
        "get_source_records",
        "generate_case_report",
    ]
    assert {layer.source for layer in result.fusion_layers} == {
        "CMS",
        "Ownership",
        "CoStar",
        "Vexcel",
    }
    assert "not conclusions of fraud" in result.disclaimer
    assert all(event.input_identifiers["target_id"] == TARGET_ID for event in result.tool_trace)


def test_toolkit_preserves_owner_masking(repository: AnalysisRepository) -> None:
    result = EvidenceToolkit(repository, TARGET_ID).get_ownership_network()

    individual_owners = [owner for owner in result["owners"] if owner["is_masked"]]
    assert individual_owners
    assert all(owner["label"].startswith("Individual owner ") for owner in individual_owners)


def test_toolkit_enforces_maximum_tool_calls(repository: AnalysisRepository) -> None:
    toolkit = EvidenceToolkit(repository, TARGET_ID, maximum_tool_calls=1)
    toolkit.get_building_profile()

    with pytest.raises(RuntimeError, match="maximum evidence tool calls"):
        toolkit.get_cms_enrollments()


def test_missing_target_stops_without_fabricating_evidence(
    repository: AnalysisRepository,
) -> None:
    with pytest.raises(KeyError):
        investigate_interactively(repository, "bldg_missing")


def test_live_summary_requires_citation_and_rejects_fraud_claims() -> None:
    trace = [
        AgentToolTrace(
            tool_name="get_source_records",
            purpose="Retrieve evidence.",
            input_identifiers={"target_id": TARGET_ID},
            result_summary="Loaded one record.",
            evidence_references=("derived:record-1",),
        )
    ]

    assert _validated_agent_summary("Neutral observation [derived:record-1].", trace)
    assert _validated_agent_summary("Neutral observation without citation.", trace) is None
    assert _validated_agent_summary("This hospice is fraudulent [derived:record-1].", trace) is None
