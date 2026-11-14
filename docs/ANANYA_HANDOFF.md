# PhantomCare laptop handoff for Ananya

This handoff uses branch `codex/phase-2-agentic-investigation`. It contains the complete Phase 2 agentic investigation work, Phase 3 security controls, offline demo data, tests, browser QA, and release/demo documents. It does not deploy or change production.

## 1. Clone the exact branch

```powershell
git clone --branch codex/phase-2-agentic-investigation --single-branch https://github.com/ayraagrawal-byte/PhantomCare.git
cd PhantomCare
git rev-parse --short HEAD
```

Compare the resulting commit with the handoff commit Ayra provides. Do not start from `main`, which still contains the previous production version.

## 2. Install prerequisites

- Git
- Python 3.11 or 3.12
- Node.js 20 or newer
- npm 10 or newer
- Google Chrome for the local Playwright suite

From PowerShell in the repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,agent]"
npm ci
```

The `agent` Python extra is optional for deterministic mode but useful for development. A model credential alone does not enable paid inference.

## 3. Create local configuration

```powershell
Copy-Item .env.example .env
```

Keep `.env` local and never commit it. The offline demo needs no sponsor or model credential. Use these local settings:

```text
PHANTOMCARE_ANALYSIS_DIR=./data/runtime
PHANTOMCARE_DASHBOARD_ORIGIN=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
PHANTOMCARE_AGENT_LIVE_ENABLED=false
```

All offline artifacts, including one Vexcel image, are already tracked under `data/runtime/`.

Secrets are intentionally absent. Ayra should share replacement sponsor credentials through a password manager or another secure channel—not GitHub, Discord history, or chat. Previously pasted credentials should be rotated before use.

## 4. Start the application

Open two PowerShell terminals in the repository.

Backend:

```powershell
$env:PHANTOMCARE_ANALYSIS_DIR='data/runtime'
$env:PHANTOMCARE_AGENT_LIVE_ENABLED='false'
$env:PHANTOMCARE_DASHBOARD_ORIGIN='http://localhost:3000'
.\.venv\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
$env:NEXT_PUBLIC_API_URL='http://localhost:8000'
npm run dev
```

Open `http://localhost:3000`, search for `12444 VICTORY`, select the building, and run the investigation. The expected mode is visibly labeled `Deterministic fallback` and contains eight genuine read-only tool records.

## 5. Validate the laptop

With the local servers stopped, run:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
npm test
npm run lint
npm run build
```

For real-browser QA, start both servers as above, then run in a third terminal:

```powershell
npm run test:e2e
```

Expected release-candidate results are 90 backend tests, 4 frontend unit tests, and 8 browser tests passing.

## 6. Continue development safely

```powershell
git switch codex/phase-2-agentic-investigation
git pull --ff-only origin codex/phase-2-agentic-investigation
git switch -c codex/ananya-next-work
```

Work on the new branch and open a pull request rather than pushing directly to `main`. Do not enable live AI or deploy production without team approval. Controlled live AI requires all server-side prerequisites documented in `docs/PHASE_3_RELEASE.md`, including a durable Redis limiter and explicit enablement.

## Key documents

- `README.md` — architecture and normal development commands
- `docs/PHASE_3_RELEASE.md` — security controls, environment names, risks, smoke tests, and rollback
- `docs/HACKPRINCETON_DEMO.md` — two-minute demo and claim guardrails
- `.env.example` — configuration names with no secret values

## Current known limitations

- Live AI has not been evaluated because no supported model credential and durable limiter were configured locally.
- The single exact CoStar match and single captured Vexcel target are different offline buildings.
- The UI shows request progress but does not stream each agent step.
- npm reports a moderate transitive development-tool advisory and no high or critical findings.
