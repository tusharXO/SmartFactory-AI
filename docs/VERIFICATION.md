# Milestone 5 verification

Verified on **2 November 2026**. This records the local MVP's actual checks;
deployment is deferred.

## Environment and isolation

- Windows / PowerShell, Python 3.14.7, Node.js 24.21.0, npm 12.2.0.
- Headless Microsoft Edge through Playwright 1.64.1.
- A separate local Git clone of merged Milestone 4 (`ed72c26`) was created at
  ignored `.verification/milestone-5-clean/`. Final M5 frontend source,
  browser-test configuration/tests, and README were copied into that clone.
- The clone had its own Python virtual environment and frontend dependencies.
  No root dataset, SQLite database, fitted model, or node_modules was copied.
- Before setup, its raw CSV, SQLite database, and `model.joblib` were confirmed
  absent. The tracked `metrics.json` was present as an expected reference.

The README's dependency installation, data preparation, training, server, and
frontend build flow was exercised in this copy. The initial frontend dependency
install used `npm ci`; `npm i` was also checked successfully afterward.

## Results

Commands below are shown in the README's activated-environment form. Each is
run from its indicated directory.

| Location | Check | Actual result |
| --- | --- | --- |
| `backend/` | `python -m pip install -r requirements.txt` | Pinned dependencies installed in the separate environment; subsequent check satisfied |
| `frontend/` | `npm ci`, then `npm i` | Dependency installation successful |
| `backend/` | `python scripts/etl.py --download` | Downloaded the official UCI source; 10,000 rows and 339 failures |
| `backend/` | `python scripts/etl.py` | Repeated load retained 10,000 distinct IDs and 339 failures |
| `backend/` | `python -m scripts.train` | Trained a fresh pipeline; report byte-for-byte identical to the tracked report |
| `backend/` | `python -m pytest tests -q` | **144 passed** in 5.68 s |
| `backend/` | `python -m pip check` | No broken requirements found |
| `frontend/` | `npm run build` | Production build passed; separate main and chart bundles |
| Root checkout `frontend/` | `npm run test:e2e` | **9 passed** in 22.4 s, including automatic fresh-server startup and shutdown |

The final build produced approximately 248.47 kB of main JavaScript and
361.30 kB of separately loaded chart JavaScript, before gzip. Build timings and
file sizes can vary with the environment.

## Clean production-preview browser flow

To avoid accidentally querying a root-checkout server, the clean copy ran its
own Uvicorn API on port **8001**. Its production frontend was built with
`VITE_API_BASE_URL=http://127.0.0.1:8001/api` and served on local preview port
**4173**. This uses the existing explicit preview CORS origin.

The browser checked real API responses and rendered UI for:

- 10,000 observations, 339 labeled failures, 3.39% failure rate, and three types.
- Both charts and the actual held-out evaluation report/confusion matrix.
- Example prediction: type M, temperatures 300 K / 310 K, 1,500 rpm,
  torque 40 Nm, and tool wear 100 min. Result: class **0**, model score
  **0.09657064265880015** (displayed as **0.0966**).
- Type H plus actual failure label 1: **21** matching SQL records, with page
  IDs compared to the API response.
- Mobile widths **390px** and **320px**: document width matched viewport width;
  the 820px observations table scrolled inside its 358px / 288px container.
- All 18 visible mobile controls were at least **44px high**.
- At 1440 × 450, the desktop sidebar scrolled to reach its lower content.
- **No browser page errors**.

Both temporary clean-copy servers were stopped afterward. Connection probes
confirmed ports 8001 and 4173 were closed. Existing user servers were not stopped.

The nine automated development-browser checks additionally cover actual
pagination, invalid RPM, stale prediction clearing, direct section links,
browser back/forward, missing-model readiness, error retry, empty filters,
transport failure, and recovery. Only failure/empty cases use controlled
responses; successful counts and predictions come from the real backend.

## Reproduced data and evaluation

Raw CSV size: **522,048 bytes**. SQL counts after repeated ETL:
`count(*) = count(distinct udi) = 10000`, `sum(machine_failure) = 339`.

| Fingerprint | SHA256 |
| --- | --- |
| Raw UCI CSV | `dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e` |
| Normalized training-source content | `59df7016da4cc10bd706458025f640ba5561414ec28d373f7fe0cbbd4698f9dd` |
| Reproduced `metrics.json` bytes | `64356b4cfc392dbc5460c3b22023958fc8ae18d827637c31582aa8643183b635` |

Held-out precision **14.18%**, recall **82.35%**, F1 **24.19%**, average
precision **0.3818**; confusion matrix `[[1593, 339], [12, 56]]`, labels `[0, 1]`.
The full values and split metadata are in
[metrics.json](../backend/artifacts/metrics.json). These are synthetic-data
measurements with low precision, not evidence of real-factory reliability.

## Screenshots and scope

[Screenshot provenance](screenshots/README.md) documents the actual browser
captures used in the README. Screenshots were inspected at desktop and mobile
sizes; they were not edited or generated from a mockup.

The clean check exposed and fixed Windows quoting in the browser runner's
backend startup and overflow from visually hidden chart data tables at 320px.
The tables remain accessible as native tables inside clipped wrappers.

All required local Milestone 5 checks pass. Cloud deployment, authentication,
live telemetry, and new model experiments remain outside this milestone.
