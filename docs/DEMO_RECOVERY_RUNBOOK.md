# Demo recovery runbook

Use this when something breaks within minutes of judging. Each step is independent.

## Standard local start (no network, no keys)

```bash
PHANTOMCARE_ANALYSIS_DIR=data/runtime PHANTOMCARE_AGENT_LIVE_ENABLED=false \
  python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

```bash
npm run dev
```

Open `http://localhost:3000`. Do **not** set `NEXT_PUBLIC_API_URL` locally; on a loopback
host the dashboard already uses `http://127.0.0.1:8000`.

PowerShell: `$env:PHANTOMCARE_ANALYSIS_DIR='data/runtime'` and
`$env:PHANTOMCARE_AGENT_LIVE_ENABLED='false'` before starting Uvicorn.

## Health checks (in order)

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/analysis/summary
curl -s "http://127.0.0.1:8000/analysis/buildings?limit=5"
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/
```

Expected: `{"status":"ok",...}`, `enrollment_count` 569 / `building_count` 468, a JSON
list, and `200`.

## Symptoms and fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Header says **Analysis unavailable** | API not running or wrong port | Start Uvicorn as above; rerun health checks. |
| Page stuck on **Loading analysis** at `127.0.0.1:3000` | Next.js dev-origin block | Use `http://localhost:3000`, or confirm `allowedDevOrigins` is in `dashboard/next.config.ts`, then restart `npm run dev`. |
| Map tiles grey | OpenStreetMap unreachable | Continue; markers, queue and evidence still work and the map reports the outage. |
| Vexcel image missing | Image endpoint failed | Use the provenance text in the Vexcel fusion layer; say imagery is context only. |
| Investigate button shows an error | API restarted mid-demo | Reselect the building and click again. |
| Port in use | Old server running | `lsof -i :8000` / `:3000`, stop it, restart. |
| Total failure | — | Use the production site https://phantomcare.vercel.app/ (read-only), or screenshots. |

## Offline synthetic dataset

If `data/runtime` is unusable, regenerate the synthetic demo and point the API at it:

```bash
python -m eval.offline_demo --output data/demo
PHANTOMCARE_ANALYSIS_DIR=data/demo python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

This shows one **synthetic** high-priority building. Say "synthetic" out loud.

## Proof points to have ready

```bash
python -m eval.scenarios --output eval/scenario_results.json
npm run test:e2e
```

The first prints `10/10 scenarios, 67/67 checks (synthetic data)`. The second starts
both servers itself if they are not already running (22 browser tests: 11 desktop,
11 mobile).

## Never during the demo

- Do not enable live AI or paste a model key.
- Do not call the deterministic fallback "AI".
- Do not present synthetic results as real-world accuracy.
