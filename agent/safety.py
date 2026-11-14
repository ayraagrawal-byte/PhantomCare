from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class InvestigationLease:
    allowed: bool
    reason: str | None = None
    key: str | None = None


class DurableRateLimiter(Protocol):
    @property
    def configured(self) -> bool: ...

    def acquire(self, client_key: str) -> InvestigationLease: ...

    def release(self, lease: InvestigationLease) -> None: ...


class UnavailableRateLimiter:
    configured = False

    def acquire(self, client_key: str) -> InvestigationLease:
        del client_key
        return InvestigationLease(False, "durable_rate_limiter_unavailable")

    def release(self, lease: InvestigationLease) -> None:
        del lease


class UpstashRateLimiter:
    """Durable fixed-window rate and concurrency limits through Redis REST."""

    ACQUIRE_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
if count > tonumber(ARGV[2]) then return {0, 'rate_limited'} end
local active = redis.call('INCR', KEYS[2])
if active == 1 then redis.call('EXPIRE', KEYS[2], ARGV[3]) end
if active > tonumber(ARGV[4]) then
  redis.call('DECR', KEYS[2])
  return {0, 'concurrency_limited'}
end
return {1, 'allowed'}
""".strip()
    RELEASE_SCRIPT = """
local active = tonumber(redis.call('GET', KEYS[1]) or '0')
if active <= 1 then redis.call('DEL', KEYS[1]); return 0 end
return redis.call('DECR', KEYS[1])
""".strip()

    def __init__(
        self,
        *,
        url: str,
        token: str,
        requests_per_window: int,
        window_seconds: int,
        maximum_concurrent: int,
        lease_seconds: int,
    ) -> None:
        self.url = url.rstrip("/")
        self.token = token
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.maximum_concurrent = maximum_concurrent
        self.lease_seconds = lease_seconds

    @property
    def configured(self) -> bool:
        return bool(self.url and self.token)

    def _command(self, payload: list[object]) -> object:
        response = httpx.post(
            self.url,
            headers={"Authorization": f"Bearer {self.token}"},
            json=payload,
            timeout=3,
        )
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            raise RuntimeError("durable limiter command failed")
        return body.get("result")

    def acquire(self, client_key: str) -> InvestigationLease:
        rate_key = f"phantomcare:investigation:rate:{client_key}"
        concurrency_key = "phantomcare:investigation:active"
        try:
            result = self._command(
                [
                    "EVAL",
                    self.ACQUIRE_SCRIPT,
                    "2",
                    rate_key,
                    concurrency_key,
                    str(self.window_seconds),
                    str(self.requests_per_window),
                    str(self.lease_seconds),
                    str(self.maximum_concurrent),
                ]
            )
        except (httpx.HTTPError, RuntimeError, ValueError):
            return InvestigationLease(False, "durable_rate_limiter_unavailable")
        if not isinstance(result, list) or len(result) < 2 or int(result[0]) != 1:
            reason = (
                str(result[1])
                if isinstance(result, list) and len(result) > 1
                else "rate_limited"
            )
            return InvestigationLease(False, reason)
        return InvestigationLease(True, key=concurrency_key)

    def release(self, lease: InvestigationLease) -> None:
        if not lease.allowed or not lease.key:
            return
        try:
            self._command(["EVAL", self.RELEASE_SCRIPT, "1", lease.key])
        except (httpx.HTTPError, RuntimeError, ValueError):
            return


def anonymized_client_key(client_address: str, secret: str) -> str:
    return hashlib.sha256(f"{secret}:{client_address}".encode()).hexdigest()[:32]
