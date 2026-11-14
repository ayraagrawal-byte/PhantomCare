from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pipeline.enrichment import (
    CachedEnrichmentProvider,
    CacheMissError,
    EnrichmentError,
    FixtureClient,
    HttpJsonClient,
    JsonCache,
    LookupRequest,
    costar_provider,
    vexcel_provider,
)

ADDRESS = "14545 FRIAR ST VAN NUYS CA 91411"


def test_fixture_lookup_is_cached_with_provenance(tmp_path: Path) -> None:
    request = LookupRequest(address=ADDRESS, latitude=34.187, longitude=-118.45)
    client = FixtureClient(
        "costar",
        {
            ADDRESS: {
                "building_type": "Office",
                "size_sqft": 32000,
                "tenant_count": 300,
                "min_suite_sqft": 140,
            }
        },
    )
    provider = costar_provider(cache_dir=tmp_path, client=client)

    record = provider.lookup(request)

    assert record.provider == "costar"
    assert record.mode == "fixture"
    assert record.payload["size_sqft"] == 32000
    assert datetime.fromisoformat(record.retrieved_at).tzinfo is not None
    assert (tmp_path / "costar" / f"{record.cache_key}.json").exists()


def test_cached_lookup_does_not_call_provider_again(tmp_path: Path) -> None:
    request = LookupRequest(address=ADDRESS)
    first = costar_provider(
        cache_dir=tmp_path,
        client=FixtureClient("costar", {ADDRESS: {"version": 1}}),
    ).lookup(request)
    second = costar_provider(
        cache_dir=tmp_path,
        client=FixtureClient("costar", {ADDRESS: {"version": 2}}),
    ).lookup(request)

    assert second == first
    assert second.payload == {"version": 1}


def test_refresh_replaces_cached_payload(tmp_path: Path) -> None:
    request = LookupRequest(address=ADDRESS)
    provider = vexcel_provider(
        cache_dir=tmp_path,
        client=FixtureClient("vexcel", {ADDRESS: {"image_url": "fixture://first"}}),
    )
    provider.lookup(request)
    refreshed = vexcel_provider(
        cache_dir=tmp_path,
        client=FixtureClient("vexcel", {ADDRESS: {"image_url": "fixture://second"}}),
    ).lookup(request, refresh=True)

    assert refreshed.payload["image_url"] == "fixture://second"


def test_cache_only_mode_fails_clearly_on_miss(tmp_path: Path) -> None:
    provider = costar_provider(cache_dir=tmp_path, cache_only=True)

    with pytest.raises(CacheMissError, match="No cached costar record"):
        provider.lookup(LookupRequest(address=ADDRESS))


def test_corrupt_cache_is_not_silently_ignored(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    request = LookupRequest(address=ADDRESS)
    path = cache.path("costar", cache.key("costar", request))
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(EnrichmentError, match="Invalid costar cache record"):
        cache.read("costar", request)


def test_cache_key_is_independent_of_dictionary_order(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    request = LookupRequest(address=ADDRESS, latitude=34.0, longitude=-118.0)
    first = cache.write(
        provider="costar",
        mode=FixtureClient("costar", {}).mode,
        request=request,
        payload={"b": 2, "a": 1},
        retrieved_at=datetime(2026, 11, 13, tzinfo=UTC),
    )
    payload = json.loads(cache.path("costar", first.cache_key).read_text(encoding="utf-8"))

    assert payload["cache_key"] == JsonCache.key("costar", request)


def test_live_client_requires_https_and_key() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        HttpJsonClient(provider="costar", endpoint="http://example.com", api_key="secret")
    with pytest.raises(ValueError, match="API key"):
        HttpJsonClient(provider="costar", endpoint="https://example.com", api_key="")


def test_provider_identity_must_match_client(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not match"):
        CachedEnrichmentProvider(
            provider="costar",
            cache=JsonCache(tmp_path),
            client=FixtureClient("vexcel", {}),
        )

