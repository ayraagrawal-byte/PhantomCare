from pathlib import Path

import pytest
from fastapi import HTTPException

from api.analysis import AnalysisRepository
from api.investigations import run_investigation


def test_interactive_investigation_endpoint_returns_explicit_fallback() -> None:
    repository = AnalysisRepository(Path("data/runtime"))

    result = run_investigation("bldg_793ac00ed2ae2571", repository)

    assert result.mode == "deterministic_fallback"
    assert len(result.tool_trace) == 8
    assert result.fusion_layers


def test_interactive_investigation_endpoint_returns_404_for_unknown_target() -> None:
    repository = AnalysisRepository(Path("data/runtime"))

    with pytest.raises(HTTPException) as error:
        run_investigation("bldg_missing", repository)

    assert error.value.status_code == 404
    assert error.value.detail["code"] == "investigation_target_not_found"
