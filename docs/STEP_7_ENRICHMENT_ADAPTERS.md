# Step 7 - CoStar and Vexcel Enrichment Adapters

Date: 2026-11-13

## Modes

- `fixture`: deterministic dictionaries for tests and development
- `live`: HTTPS JSON lookups using explicitly configured event endpoints and credentials
- `cache_only`: offline replay that fails clearly when a requested record is absent

No sponsor endpoint is embedded or guessed. Live URLs and API keys must be supplied through environment variables based on the event documentation.

## Cache contract

Each cached record contains:

- Provider name
- Retrieval mode
- Timezone-aware retrieval timestamp
- Exact lookup address and optional coordinates
- Raw JSON provider payload
- Deterministic SHA-256 cache key

Cache writes are atomic. Corrupt cache records raise an error instead of falling through to a live request, preventing silent evidence replacement during a demo.

## Security and reliability

- Live endpoints must use HTTPS.
- API keys are required in live mode and are never written to cache.
- Provider requests have a configurable timeout.
- HTTP failures and invalid JSON produce provider-specific errors.
- A cached response is preferred unless an explicit refresh is requested.
- CoStar and Vexcel use separate cache namespaces and client identities.

## CLI

```bash
python -m pipeline.enrich_buildings \
  --provider costar \
  --buildings data/processed/buildings_ranked.csv \
  --cache-dir cache \
  --output data/processed/costar_enrichment.json \
  --limit 50
```

For judging or offline development, add `--cache-only`. A cache miss is then an explicit error rather than an attempted network request.

## Integration boundary

The adapters intentionally preserve raw payloads until the actual hackathon API/SDK schemas are available. Provider-specific field mapping should be added against captured fixtures from those documented schemas; it must not be inferred from marketing pages or invented field names.

