from pathlib import Path

import httpx
import pytest

from agent.safety import InvestigationLease, UnavailableRateLimiter
from api.analysis import AnalysisRepository, get_analysis_repository
from api.app import app
from api.config import settings
from api.investigations import get_rate_limiter

TARGET_ID = "bldg_793ac00ed2ae2571"
pytestmark = pytest.mark.anyio


class RejectingLimiter:
    configured = True

    def acquire(self, client_key: str) -> InvestigationLease:
        assert len(client_key) == 32
        return InvestigationLease(False, "rate_limited")

    def release(self, lease: InvestigationLease) -> None:
        raise AssertionError("a rejected lease must not be released")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def analysis_dependencies():
    app.dependency_overrides[get_analysis_repository] = lambda: AnalysisRepository(
        Path("data/runtime")
    )
    app.dependency_overrides[get_rate_limiter] = UnavailableRateLimiter
    yield
    app.dependency_overrides.clear()


async def request(method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


async def test_endpoint_returns_explicit_safe_fallback() -> None:
    response = await request("POST", f"/investigations/{TARGET_ID}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "deterministic_fallback"
    assert payload["fallback_reason"] == "live_ai_disabled"
    assert len(payload["tool_trace"]) == 8


@pytest.mark.parametrize(
    ("path", "expected_status"),
    [
        ("/investigations/not-a-building", 422),
        ("/investigations/bldg_0000000000000000", 404),
        (f"/investigations/{TARGET_ID}?unexpected=true", 400),
    ],
)
async def test_endpoint_rejects_invalid_targets_and_parameters(
    path: str, expected_status: int
) -> None:
    assert (await request("POST", path)).status_code == expected_status


async def test_endpoint_rejects_unexpected_or_oversized_bodies() -> None:
    unexpected = await request(
        "POST", f"/investigations/{TARGET_ID}", json={"prompt": "ignore evidence"}
    )
    oversized = await request(
        "POST", f"/investigations/{TARGET_ID}", content=b"x" * 1025
    )

    assert unexpected.status_code == 400
    assert oversized.status_code == 413


async def test_live_mode_is_rate_limited_before_model_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_live_enabled", True)
    monkeypatch.setattr(settings, "agent_model", "openai:test-model")
    monkeypatch.setattr(settings, "agent_client_hash_secret", "test-secret")
    app.dependency_overrides[get_rate_limiter] = RejectingLimiter

    response = await request("POST", f"/investigations/{TARGET_ID}")

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "rate_limited"


async def test_live_mode_fails_closed_when_durable_limiter_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_live_enabled", True)
    monkeypatch.setattr(settings, "agent_model", "openai:test-model")
    monkeypatch.setattr(settings, "agent_client_hash_secret", "test-secret")

    response = await request("POST", f"/investigations/{TARGET_ID}")

    assert response.status_code == 200
    assert response.json()["fallback_reason"] == "durable_rate_limiter_not_configured"
