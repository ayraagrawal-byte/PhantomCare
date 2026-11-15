"""MOCKED MODEL tests for the Deep Agents path.

No real language model is called. A scripted fake chat model stands in for the
LLM so these tests can prove that, when the live path is enabled, the model's
tool calls (not the deterministic fallback script) decide which read-only
evidence tools run, and that the trace records the actual invocation results.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("deepagents")

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402

from agent.interactive import EvidenceToolkit, investigate_interactively  # noqa: E402
from api.analysis import AnalysisRepository  # noqa: E402

TARGET_ID = "bldg_793ac00ed2ae2571"
MOCK_MODEL_ID = "mock:scripted-test-model"


class ScriptedToolModel(GenericFakeChatModel):
    """Fake chat model that replays scripted AI messages and accepts tool binding."""

    bound_tool_names: list[str] = []

    def bind_tools(self, tools: Any, **_: Any) -> ScriptedToolModel:
        self.bound_tool_names = [getattr(tool, "name", None) or tool["name"] for tool in tools]
        return self


@pytest.fixture
def repository() -> AnalysisRepository:
    return AnalysisRepository(Path("data/runtime"))


@pytest.fixture
def source_reference(repository: AnalysisRepository) -> str:
    toolkit = EvidenceToolkit(repository, TARGET_ID)
    toolkit.get_source_records()
    return toolkit.trace[0].evidence_references[0]


def _tool_call(name: str, index: int) -> dict[str, Any]:
    return {"name": name, "args": {}, "id": f"call_{index}", "type": "tool_call"}


def _install(monkeypatch: pytest.MonkeyPatch, messages: list[AIMessage]) -> ScriptedToolModel:
    model = ScriptedToolModel(messages=itertools.chain(messages))
    captured: dict[str, Any] = {}

    def fake_init_chat_model(model_id: str, **kwargs: Any) -> ScriptedToolModel:
        captured["model_id"] = model_id
        captured.update(kwargs)
        return model

    monkeypatch.setattr("langchain.chat_models.init_chat_model", fake_init_chat_model)
    model.__dict__["captured"] = captured
    return model


def test_mocked_model_directs_tool_selection(
    monkeypatch: pytest.MonkeyPatch, repository: AnalysisRepository, source_reference: str
) -> None:
    chosen = ["get_costar_property_context", "get_source_records"]
    model = _install(
        monkeypatch,
        [
            AIMessage(content="", tool_calls=[_tool_call(chosen[0], 1)]),
            AIMessage(content="", tool_calls=[_tool_call(chosen[1], 2)]),
            AIMessage(
                content=(
                    "Registration concentration warrants human review; no exact CoStar record "
                    f"is available. Evidence: {source_reference}."
                )
            ),
        ],
    )

    result = investigate_interactively(
        repository, TARGET_ID, model=MOCK_MODEL_ID, maximum_tokens=512
    )

    assert result.mode == "live_ai"
    assert result.model == MOCK_MODEL_ID
    # The model chose two tools; the eight-step deterministic script did not run.
    assert [event.tool_name for event in result.tool_trace] == chosen
    assert result.tool_trace[0].result_summary.startswith("No exact CoStar property")
    assert source_reference in result.tool_trace[1].evidence_references
    assert source_reference in result.reasoning_summary
    assert "Building type, area, and occupancy context are unavailable." in result.unknowns
    # All eight read-only evidence tools were genuinely registered with the agent.
    assert {
        "get_building_profile",
        "get_cms_enrollments",
        "get_ownership_network",
        "get_costar_property_context",
        "get_vexcel_aerial_evidence",
        "get_indicator_breakdown",
        "get_source_records",
        "generate_case_report",
    } <= set(model.bound_tool_names)
    assert model.__dict__["captured"]["max_tokens"] == 512
    assert model.__dict__["captured"]["max_retries"] == 0


def test_mocked_model_fraud_allegation_triggers_fallback(
    monkeypatch: pytest.MonkeyPatch, repository: AnalysisRepository, source_reference: str
) -> None:
    _install(
        monkeypatch,
        [
            AIMessage(content="", tool_calls=[_tool_call("get_source_records", 1)]),
            AIMessage(content=f"This building is fraudulent. Evidence: {source_reference}."),
        ],
    )

    result = investigate_interactively(repository, TARGET_ID, model=MOCK_MODEL_ID)

    assert result.mode == "deterministic_fallback"
    assert result.fallback_reason == "live_ai_output_failed_validation"
    assert "fraudulent" not in result.reasoning_summary.casefold()
    assert len(result.tool_trace) == 8


def test_mocked_model_uncited_summary_triggers_fallback(
    monkeypatch: pytest.MonkeyPatch, repository: AnalysisRepository
) -> None:
    _install(
        monkeypatch,
        [
            AIMessage(content="", tool_calls=[_tool_call("get_building_profile", 1)]),
            AIMessage(content="Looks worth reviewing."),
        ],
    )

    result = investigate_interactively(repository, TARGET_ID, model=MOCK_MODEL_ID)

    assert result.fallback_reason == "live_ai_output_failed_validation"


def test_mocked_model_cannot_exceed_tool_call_limit(
    monkeypatch: pytest.MonkeyPatch, repository: AnalysisRepository, source_reference: str
) -> None:
    calls = [
        AIMessage(content="", tool_calls=[_tool_call("get_building_profile", index)])
        for index in range(9)
    ]
    _install(monkeypatch, [*calls, AIMessage(content=f"Evidence: {source_reference}.")])

    result = investigate_interactively(
        repository, TARGET_ID, model=MOCK_MODEL_ID, maximum_tool_calls=8
    )

    assert result.mode == "deterministic_fallback"
    assert result.fallback_reason == "live_ai_execution_failed"
    assert len(result.tool_trace) == 8
