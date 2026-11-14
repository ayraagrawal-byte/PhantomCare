from __future__ import annotations

import hashlib
import json
import os
import tempfile
from abc import ABC, abstractmethod
from base64 import b64encode
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class EnrichmentError(RuntimeError):
    """Base error for sponsor-data enrichment failures."""


class CacheMissError(EnrichmentError):
    """Raised when cache-only mode cannot find the requested record."""


class ProviderResponseError(EnrichmentError):
    """Raised when a provider returns an invalid or unusable response."""


class ProviderMode(StrEnum):
    LIVE = "live"
    CACHE_ONLY = "cache_only"
    FIXTURE = "fixture"


@dataclass(frozen=True)
class LookupRequest:
    address: str
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class EnrichmentRecord:
    provider: str
    mode: str
    retrieved_at: str
    request: dict[str, Any]
    payload: dict[str, Any]
    cache_key: str


class JsonCache:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def key(provider: str, request: LookupRequest) -> str:
        canonical = json.dumps(asdict(request), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(f"{provider}:{canonical}".encode()).hexdigest()
        return digest

    def path(self, provider: str, key: str) -> Path:
        return self.root / provider / f"{key}.json"

    def read(self, provider: str, request: LookupRequest) -> EnrichmentRecord | None:
        key = self.key(provider, request)
        path = self.path(provider, key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return EnrichmentRecord(**payload)
        except (OSError, TypeError, json.JSONDecodeError) as error:
            raise EnrichmentError(f"Invalid {provider} cache record {path}: {error}") from error

    def write(
        self,
        *,
        provider: str,
        mode: ProviderMode,
        request: LookupRequest,
        payload: dict[str, Any],
        retrieved_at: datetime | None = None,
    ) -> EnrichmentRecord:
        key = self.key(provider, request)
        record = EnrichmentRecord(
            provider=provider,
            mode=mode.value,
            retrieved_at=(retrieved_at or datetime.now(UTC)).isoformat(),
            request=asdict(request),
            payload=payload,
            cache_key=key,
        )
        path = self.path(provider, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{key}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(asdict(record), stream, indent=2, sort_keys=True)
                stream.write("\n")
            Path(temporary_name).replace(path)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise
        return record


class ProviderClient(ABC):
    provider: str
    mode: ProviderMode

    @abstractmethod
    def lookup(self, request: LookupRequest) -> dict[str, Any]:
        raise NotImplementedError


class FixtureClient(ProviderClient):
    def __init__(self, provider: str, fixtures: dict[str, dict[str, Any]]) -> None:
        self.provider = provider
        self.mode = ProviderMode.FIXTURE
        self.fixtures = fixtures

    def lookup(self, request: LookupRequest) -> dict[str, Any]:
        if request.address not in self.fixtures:
            raise ProviderResponseError(
                f"No {self.provider} fixture exists for address {request.address!r}"
            )
        return self.fixtures[request.address]


class HttpJsonClient(ProviderClient):
    """Configurable GET client for documented sponsor endpoints.

    Endpoint URLs and authorization header values must come from event-provided
    documentation and environment variables. No provider URL is guessed here.
    """

    def __init__(
        self,
        *,
        provider: str,
        endpoint: str,
        api_key: str,
        api_key_header: str = "Authorization",
        timeout_seconds: float = 15,
    ) -> None:
        if not endpoint.startswith("https://"):
            raise ValueError("live sponsor endpoints must use HTTPS")
        if not api_key:
            raise ValueError(f"{provider} API key is required for live mode")
        self.provider = provider
        self.mode = ProviderMode.LIVE
        self.endpoint = endpoint
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.timeout_seconds = timeout_seconds

    def lookup(self, request: LookupRequest) -> dict[str, Any]:
        params: dict[str, str | float] = {"address": request.address}
        if request.latitude is not None:
            params["latitude"] = request.latitude
        if request.longitude is not None:
            params["longitude"] = request.longitude
        separator = "&" if "?" in self.endpoint else "?"
        url = f"{self.endpoint}{separator}{urlencode(params)}"
        http_request = Request(
            url,
            headers={
                self.api_key_header: self.api_key,
                "Accept": "application/json",
                "User-Agent": "PhantomCare/0.1",
            },
        )
        try:
            with urlopen(http_request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            raise EnrichmentError(
                f"{self.provider} returned HTTP {error.code} for the configured endpoint"
            ) from error
        except (TimeoutError, URLError) as error:
            detail = getattr(error, "reason", str(error))
            raise EnrichmentError(f"{self.provider} lookup failed: {detail}") from error

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise ProviderResponseError(
                f"{self.provider} returned a non-JSON response"
            ) from error
        if not isinstance(payload, dict):
            raise ProviderResponseError(f"{self.provider} response must be a JSON object")
        return payload


class VexcelPropertyClient(ProviderClient):
    provider = "vexcel"
    mode = ProviderMode.LIVE
    endpoint = "https://api.vexcelgroup.com/v2/property/extract"
    layers = "urban,urban-r,wide-area,urban-g"

    def __init__(self, *, api_key: str, timeout_seconds: float = 120) -> None:
        if not api_key:
            raise ValueError("Vexcel API key is required for live mode")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def lookup(self, request: LookupRequest) -> dict[str, Any]:
        if request.latitude is None or request.longitude is None:
            raise ValueError("Vexcel property lookups require latitude and longitude")
        params = {
            "wkt": f"POINT({request.longitude} {request.latitude})",
            "srid": 4326,
            "layer": self.layers,
            "latest": "true",
            "include": "precomputed",
            "unit-system": "imperial",
        }
        http_request = Request(
            f"{self.endpoint}?{urlencode(params)}",
            headers={
                "X-API-KEY": self.api_key,
                "Accept": "application/json",
                "User-Agent": "PhantomCare/0.1",
            },
        )
        try:
            with urlopen(http_request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            if error.code == 404:
                return {"features": [], "context": {"no_property_at_point": True}}
            raise EnrichmentError(f"Vexcel returned HTTP {error.code}") from error
        except (TimeoutError, URLError) as error:
            detail = getattr(error, "reason", str(error))
            raise EnrichmentError(f"Vexcel lookup failed: {detail}") from error
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise ProviderResponseError("Vexcel returned a non-JSON response") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
            raise ProviderResponseError("Vexcel property response must be a GeoJSON object")
        return payload


class MatterportModelsClient(ProviderClient):
    provider = "matterport"
    mode = ProviderMode.LIVE
    endpoint = "https://api.matterport.com/api/models/graph"

    def __init__(
        self,
        *,
        token_id: str,
        token_secret: str,
        timeout_seconds: float = 30,
    ) -> None:
        if not token_id or not token_secret:
            raise ValueError("Matterport token ID and secret are required")
        self.token_id = token_id
        self.token_secret = token_secret
        self.timeout_seconds = timeout_seconds

    def lookup(self, request: LookupRequest) -> dict[str, Any]:
        query = """
        query SearchModels($query: String!) {
          models(query: $query) {
            totalResults
            results { id name created modified visibility }
          }
        }
        """
        body = json.dumps({"query": query, "variables": {"query": request.address}}).encode()
        credentials = b64encode(
            f"{self.token_id}:{self.token_secret}".encode()
        ).decode("ascii")
        http_request = Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "PhantomCare/0.1",
            },
        )
        try:
            with urlopen(http_request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise EnrichmentError(f"Matterport returned HTTP {error.code}") from error
        except (TimeoutError, URLError, json.JSONDecodeError) as error:
            detail = getattr(error, "reason", str(error))
            raise EnrichmentError(f"Matterport lookup failed: {detail}") from error
        if not isinstance(payload, dict):
            raise ProviderResponseError("Matterport response must be a JSON object")
        if payload.get("errors"):
            raise ProviderResponseError("Matterport returned GraphQL errors")
        return payload


class CachedEnrichmentProvider:
    def __init__(
        self,
        *,
        provider: str,
        cache: JsonCache,
        client: ProviderClient | None = None,
        cache_only: bool = False,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.client = client
        self.cache_only = cache_only
        if client is not None and client.provider != provider:
            raise ValueError("client provider does not match cache provider")

    def lookup(self, request: LookupRequest, *, refresh: bool = False) -> EnrichmentRecord:
        cached = None if refresh else self.cache.read(self.provider, request)
        if cached is not None:
            return cached
        if self.cache_only or self.client is None:
            raise CacheMissError(
                f"No cached {self.provider} record exists for {request.address!r}"
            )

        payload = self.client.lookup(request)
        return self.cache.write(
            provider=self.provider,
            mode=self.client.mode,
            request=request,
            payload=payload,
        )


def costar_provider(
    *,
    cache_dir: str | Path,
    client: ProviderClient | None = None,
    cache_only: bool = False,
) -> CachedEnrichmentProvider:
    return CachedEnrichmentProvider(
        provider="costar",
        cache=JsonCache(cache_dir),
        client=client,
        cache_only=cache_only,
    )


def vexcel_provider(
    *,
    cache_dir: str | Path,
    client: ProviderClient | None = None,
    cache_only: bool = False,
) -> CachedEnrichmentProvider:
    return CachedEnrichmentProvider(
        provider="vexcel",
        cache=JsonCache(cache_dir),
        client=client,
        cache_only=cache_only,
    )


def matterport_provider(
    *,
    cache_dir: str | Path,
    client: ProviderClient | None = None,
    cache_only: bool = False,
) -> CachedEnrichmentProvider:
    return CachedEnrichmentProvider(
        provider="matterport",
        cache=JsonCache(cache_dir),
        client=client,
        cache_only=cache_only,
    )

