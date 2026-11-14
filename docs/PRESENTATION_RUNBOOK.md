# Presentation Runbook

## Reliable offline setup

```bash
python -m eval.offline_demo --output data/demo
```

Point the API at those generated artifacts:

```bash
PHANTOMCARE_ANALYSIS_DIR=data/demo uvicorn api.app:app --port 8000
npm run dev
```

On Windows PowerShell, set `$env:PHANTOMCARE_ANALYSIS_DIR = "data/demo"` before starting Uvicorn. Open `http://localhost:3000`.

## Five-minute story

1. Explain the problem: many hospice registrations can share an address, but a count alone is not a conclusion.
2. Show the ranked building queue and the one synthetic high-priority building.
3. Filter the queue, select the hotspot, and explain the four independent signals.
4. Point out exact source evidence, missing-data behavior, and limitations.
5. Show the neutral case findings, skeptical-review trace, and non-fraud disclaimer.
6. End with the reproducible offline evaluation: one expected hotspot, one case, two early stops, and no exposed individual owner data.

## Pre-demo checklist

- Run `python scripts/secret_scan.py`.
- Run `ruff check .` and `pytest`.
- Run `npm run test`, `npm run lint`, and `npm run build`.
- Regenerate `data/demo` and confirm `evaluation_results.json` says `passed`.
- Keep sponsor credentials and licensed extracts outside the presentation folder.
- Use the offline synthetic demo if venue Wi-Fi or sponsor APIs are unavailable.
