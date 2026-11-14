# PhantomCare Phase 3 release candidate

## Release identity

- Branch: `codex/phase-2-agentic-investigation`
- Phase 2 base: `c9bc72a`
- Production status: unchanged; this candidate has not been pushed or deployed.
- Architecture: Next.js dashboard in `dashboard/`; FastAPI application exposed through `api/index.py`.

## Operating modes

Safe deterministic mode is the release default. It makes no model request, runs the eight read-only evidence tools, produces cited deterministic findings, and labels the result and fallback reason in the UI.

Controlled live mode additionally requires all of the following on the server: agent extras installed, a model provider credential, a model name, `PHANTOMCARE_AGENT_LIVE_ENABLED=true`, a client-key hashing secret, and a working durable Redis REST limiter. Missing or failed prerequisites fall back safely. A configured model credential alone never enables inference.

## Security and cost controls

- Strict building ID syntax plus lookup against analysis artifacts.
- No query parameters or request body; declared bodies over 1 KiB are rejected.
- Durable per-client fixed-window limits and global concurrency leases for serverless execution.
- Fail-closed paid inference when the limiter is missing; fail-safe deterministic output when it is unavailable.
- Client addresses are keyed with a server secret and are not logged.
- 8–12 tool-call cap (default 8), bounded recursion, 25-second default model timeout, 1,200-token default, zero retries, and two concurrent live investigations by default.
- Read-only, allowlisted evidence tools; no arbitrary filesystem or URL tool.
- Server-side credentials only, neutral external errors, masked-owner handling, and evidence-grounded language that does not assert fraud.
- Blocking model and limiter I/O runs off the async request loop.

## Configuration names

No values belong in source control. Live mode uses:

- `PHANTOMCARE_AGENT_LIVE_ENABLED`
- `PHANTOMCARE_AGENT_MODEL`
- `PHANTOMCARE_AGENT_MAX_TOOL_CALLS`
- `PHANTOMCARE_AGENT_MAX_TOKENS`
- `PHANTOMCARE_AGENT_TIMEOUT_SECONDS`
- `PHANTOMCARE_AGENT_MAX_RETRIES`
- `PHANTOMCARE_AGENT_REQUESTS_PER_WINDOW`
- `PHANTOMCARE_AGENT_RATE_WINDOW_SECONDS`
- `PHANTOMCARE_AGENT_MAX_CONCURRENT`
- `PHANTOMCARE_AGENT_CLIENT_HASH_SECRET`
- `PHANTOMCARE_AGENT_REDIS_URL`
- `PHANTOMCARE_AGENT_REDIS_TOKEN`
- Provider credential such as `OPENAI_API_KEY`

Deployment routing still uses `NEXT_PUBLIC_API_URL` and `PHANTOMCARE_DASHBOARD_ORIGIN`.

## Validation evidence

- Backend: 90 tests passed.
- Frontend unit tests: 4 passed.
- Browser: 8 Playwright tests passed in real Chrome across desktop and Pixel 7 profiles.
- Ruff: passed.
- ESLint: passed.
- TypeScript and Next.js production build: passed.
- Secret scan: included in the 90-test backend suite and passed.
- Browser coverage: summary, priority filter, search, selection, CMS/CoStar/Vexcel evidence, deterministic investigation, eight tool records, citations, recommended action, case download, rapid selection, failed detail response, missing target, fallback disclosure, keyboard interaction, responsive layout, console errors, and transport failures.
- Dependency audit: zero critical/high findings. Seven moderate findings share one transitive `minimatch` development-tool advisory under TypeScript ESLint; `npm audit fix` currently reports no applicable update and leaves it unresolved.

## Agent evaluation

No supported model credential or durable limiter is configured locally. A live paid-model evaluation was therefore not run. Deterministic mode and live-mode gating, limiter behavior, bounds, fallback reasons, and API failure paths are covered by automated tests. No live latency, tokens, cost, or citation benchmark is claimed.

## Sponsor-data fusion

The browser scenario uses `bldg_793ac00ed2ae2571` (`12444 VICTORY BLVD N HOLLYWOOD CA 91606`). It combines CMS registration indicators, an explicit CoStar `no_exact_match` state, Vexcel ortho imagery and provenance, and ownership-network evidence. Together these support prioritizing a records investigation; they do not establish occupancy, healthcare delivery, ownership control, misconduct, or fraud. The recommended next step is source-record verification and relationship confirmation.

The offline artifact has 468 analyzed buildings, one exact CoStar match, and one captured Vexcel target; they are not the same building. This is a material demo limitation: the candidate demonstrates honest missing-data handling rather than claiming three-source confirmation on one property. Deterministic scoring was not changed.

## Known limitations and release risks

1. Live AI remains disabled until a provider credential and durable limiter are securely configured and evaluated.
2. The dashboard shows request state but does not stream step-by-step model progress.
3. CoStar and Vexcel exact evidence do not overlap on one offline target.
4. The moderate development-only audit advisory remains upstream/transitive.
5. Rate limits depend on the production Redis REST service; its URL, token, latency, and operational limits need a preview deployment check.

## Controlled release and rollback

1. Review this branch and its diff; push only after approval.
2. Deploy previews with live AI disabled.
3. Run the smoke checklist below against preview URLs.
4. Promote backend, then frontend, and repeat the checks.
5. If checks fail, immediately promote the previous known-good Vercel deployments for both projects. Revert the release commit before the next attempt; do not try to repair production in place.

Production smoke checklist:

- `/health` returns 200 without sensitive configuration.
- Dashboard loads with no console errors and shows expected summary counts.
- One building detail, aerial state, and ownership network load.
- Investigation returns `deterministic_fallback` with eight genuine tool records while live mode is disabled.
- Missing and malformed IDs return neutral 404/422 responses; an unexpected body is rejected.
- JSON case download works.
- Frontend origin/CORS and `NEXT_PUBLIC_API_URL` point only to the intended production pair.
- No secret appears in browser bundles, responses, or logs.

