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


def test_fallback_includes_source_aware_review_checklist(repository: AnalysisRepository) -> None:
    result = investigate_interactively(repository, TARGET_ID)

    checklist = " ".join(result.review_checklist)
    assert "No exact CoStar property record" in checklist
    assert "exterior context only" in checklist
    assert "Keep owner identities masked" in checklist


def test_validator_rejects_paraphrased_allegations_and_fabricated_citations() -> None:
    trace = [
        AgentToolTrace(
            tool_name="get_source_records",
            purpose="test",
            input_identifiers={"target_id": "target"},
            result_summary="test",
            evidence_references=("derived:record-1",),
        )
    ]
    for text in (
        "The operator is committing hospice fraud [derived:record-1].",
        "These are sham hospices [derived:record-1].",
        "An illegal scheme [derived:record-1].",
    ):
        assert _validated_agent_summary(text, trace) is None
    assert _validated_agent_summary("Review [derived:record-1] [costar:999].", trace) is None
    assert _validated_agent_summary(
        "Merits review; this is not evidence of fraud [derived:record-1].", trace
    )


def test_costar_match_produces_labeled_cross_source_comparison(
    repository: AnalysisRepository,
) -> None:
    result = investigate_interactively(repository, "bldg_1161264fd5dbc223")

    layers = {layer.source: layer for layer in result.fusion_layers}
    assert layers["CMS"].data_class == "public_record"
    assert layers["CoStar"].data_class == "licensed_property_data"
    assert layers["Vexcel"].data_class == "aerial_imagery"
    assert "85,831 sq ft" in layers["CoStar"].establishes[0]
    comparison = result.cross_source_comparison
    assert comparison is not None
    assert comparison.sources_compared == ("CMS", "CoStar", "Ownership")
    assert any("per registration" in item for item in comparison.combined_observations)
    assert any("no Vexcel imagery" in item for item in comparison.remains_uncertain)
    text = " ".join(comparison.combined_observations).casefold()
    assert "fraud" not in text and "operates" not in text


def test_missing_costar_comparison_requests_property_records(
    repository: AnalysisRepository,
) -> None:
    comparison = investigate_interactively(repository, TARGET_ID).cross_source_comparison

    assert comparison is not None
    assert "CoStar" not in comparison.sources_compared
    assert any("assessor" in item for item in comparison.records_to_request)
    assert any("cannot show what happens inside" in item for item in comparison.remains_uncertain)


def test_fallback_summary_reflects_actual_review_level(repository: AnalysisRepository) -> None:
    unremarkable = investigate_interactively(repository, "bldg_1161264fd5dbc223")
    flagged = investigate_interactively(repository, TARGET_ID)

    assert "found no screening indicators" in unremarkable.reasoning_summary
    assert "prioritizes" not in unremarkable.reasoning_summary
    assert "1 hospice registration at" in unremarkable.reasoning_summary
    assert "marks the target as worth a look" in flagged.reasoning_summary
