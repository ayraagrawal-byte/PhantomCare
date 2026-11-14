# Step 7 - CoStar and Vexcel Enrichment Adapters

Date: 2026-11-13

## Confirmed sponsor interfaces

- CoStar is an encrypted raw data extract, not a live API.
- Vexcel uses REST API 2.0 at `https://api.vexcelgroup.com/v2` with the `X-API-KEY` header.
- Matterport uses the server-side Model GraphQL endpoint with HTTP Basic authentication.

## Modes

- `fixture`: deterministic dictionaries for tests and development
- `live`: HTTPS JSON lookups using explicitly configured event endpoints and credentials
- `cache_only`: offline replay that fails clearly when a requested record is absent

Only endpoints confirmed by the sponsor documentation are embedded. API keys and tokens are supplied through ignored environment variables.

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

The Vexcel client now performs the documented `GET /property/extract` lookup with WKT longitude-first ordering, SRID 4326, all coverage layers, and precomputed imperial property attributes. The Matterport client searches available models through the documented Model GraphQL endpoint. Both preserve raw responses before field extraction.

The decrypted CoStar kit is read as a versioned raw-data extract. The importer joins commercial-property records to Matterport model IDs, counts occupancy records separately from unique tenant locations, decodes property enums, and performs exact normalized-address matching. Occupancy data explicitly remains labeled as current-or-past records rather than being presented as a current tenant count. Every property match retains its JSONL line number and SHA-256 source-row hash.

