from agent.safety import InvestigationLease, UpstashRateLimiter, anonymized_client_key


class FixtureLimiter(UpstashRateLimiter):
    def __init__(self, result: object) -> None:
        super().__init__(
            url="https://redis.example.test",
            token="fixture-token",
            requests_per_window=5,
            window_seconds=60,
            maximum_concurrent=2,
            lease_seconds=35,
        )
        self.result = result
        self.commands: list[list[object]] = []

    def _command(self, payload: list[object]) -> object:
        self.commands.append(payload)
        return self.result


def test_client_keys_are_stable_anonymous_and_secret_scoped() -> None:
    first = anonymized_client_key("203.0.113.7", "secret-a")
    second = anonymized_client_key("203.0.113.7", "secret-a")
    changed = anonymized_client_key("203.0.113.7", "secret-b")

    assert first == second
    assert first != changed
    assert "203.0.113.7" not in first
    assert len(first) == 32


def test_durable_limiter_acquires_and_releases_concurrency_lease() -> None:
    limiter = FixtureLimiter([1, "allowed"])

    lease = limiter.acquire("anonymous-client")
    limiter.result = 0
    limiter.release(lease)

    assert lease.allowed
    assert lease.key == "phantomcare:investigation:active"
    assert len(limiter.commands) == 2


def test_durable_limiter_rejects_rate_and_concurrency_limits() -> None:
    rate_limiter = FixtureLimiter([0, "rate_limited"])
    concurrency_limiter = FixtureLimiter([0, "concurrency_limited"])

    assert rate_limiter.acquire("client") == InvestigationLease(False, "rate_limited")
    assert concurrency_limiter.acquire("client") == InvestigationLease(
        False, "concurrency_limited"
    )
