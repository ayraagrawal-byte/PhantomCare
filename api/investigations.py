import logging
from functools import partial
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from starlette.concurrency import run_in_threadpool

from agent.interactive import InteractiveInvestigation, investigate_interactively
from agent.safety import (
    DurableRateLimiter,
    UnavailableRateLimiter,
    UpstashRateLimiter,
    anonymized_client_key,
)
from api.analysis import AnalysisArtifactError, AnalysisRepository, get_analysis_repository
from api.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/investigations", tags=["investigations"])
AnalysisRepositoryDependency = Annotated[AnalysisRepository, Depends(get_analysis_repository)]
TargetId = Annotated[str, Path(pattern=r"^bldg_[a-f0-9]{16}$", max_length=21)]


def get_rate_limiter() -> DurableRateLimiter:
    if settings.agent_redis_url and settings.agent_redis_token:
        return UpstashRateLimiter(
            url=settings.agent_redis_url,
            token=settings.agent_redis_token,
            requests_per_window=settings.agent_requests_per_window,
            window_seconds=settings.agent_rate_window_seconds,
            maximum_concurrent=settings.agent_max_concurrent,
            lease_seconds=settings.agent_timeout_seconds + 10,
        )
    return UnavailableRateLimiter()


RateLimiterDependency = Annotated[DurableRateLimiter, Depends(get_rate_limiter)]


def _fallback_reason(limiter: DurableRateLimiter) -> str | None:
    if not settings.agent_live_enabled:
        return "live_ai_disabled"
    if not settings.agent_model:
        return "model_not_configured"
    if not settings.agent_client_hash_secret:
        return "client_hash_secret_not_configured"
    if not limiter.configured:
        return "durable_rate_limiter_not_configured"
    return None


def _client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", maxsplit=1)[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


@router.post("/{target_id}", response_model=InteractiveInvestigation)
async def run_investigation(
    target_id: TargetId,
    request: Request,
    repository: AnalysisRepositoryDependency,
    limiter: RateLimiterDependency,
) -> InteractiveInvestigation:
    if request.query_params:
        raise HTTPException(status_code=400, detail={"code": "unexpected_query_parameters"})
    try:
        content_length = int(request.headers.get("content-length", "0") or 0)
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"code": "invalid_content_length"}) from error
    if content_length > 1024:
        raise HTTPException(status_code=413, detail={"code": "request_body_too_large"})
    if content_length > 0 or request.headers.get("transfer-encoding"):
        raise HTTPException(status_code=400, detail={"code": "unexpected_request_body"})

    reason = _fallback_reason(limiter)
    lease = None
    model = settings.agent_model if reason is None else None
    if model:
        client_key = anonymized_client_key(
            _client_address(request), settings.agent_client_hash_secret or ""
        )
        lease = await run_in_threadpool(limiter.acquire, client_key)
        if not lease.allowed:
            if lease.reason in {"rate_limited", "concurrency_limited"}:
                raise HTTPException(status_code=429, detail={"code": lease.reason})
            reason = lease.reason or "durable_rate_limiter_unavailable"
            model = None
    try:
        result = await run_in_threadpool(
            partial(
                investigate_interactively,
                repository,
                target_id,
                model=model,
                maximum_tool_calls=settings.agent_max_tool_calls,
                maximum_tokens=settings.agent_max_tokens,
                timeout_seconds=settings.agent_timeout_seconds,
                maximum_retries=settings.agent_max_retries,
                fallback_reason=reason or "live_ai_execution_failed",
            )
        )
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "investigation_target_not_found", "target_id": target_id},
        ) from error
    except (AnalysisArtifactError, ValueError) as error:
        logger.warning("Investigation evidence unavailable: %s", type(error).__name__)
        raise HTTPException(
            status_code=503,
            detail={"code": "investigation_unavailable"},
        ) from error
    finally:
        if lease is not None:
            await run_in_threadpool(limiter.release, lease)
    if result.mode == "deterministic_fallback":
        logger.info("Deterministic investigation fallback: %s", result.fallback_reason)
    return result
