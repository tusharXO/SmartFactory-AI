# SmartFactory AI

A portfolio project for exploring synthetic industrial equipment data and
classifying operating measurements with machine learning.

**Current progress:** Milestone 4 — working React dashboard. The local demo
connects dataset analytics, two charts, a validated prediction form, filtered
records, and measured model evaluation to FastAPI. The underlying SQLite data
and trained classifier are reproducible through offline ETL/training commands.
Final documentation and portfolio polish are the next milestone. See
[PROJECT_PLAN.md](PROJECT_PLAN.md) for the scope and build order.

## Local setup (VS Code + PowerShell)

Install Python and Node.js with npm before running setup. Verified on Windows
with Python 3.14.7, Node.js 24.21.0, and npm 12.2.0.

Open this repository in VS Code and use **Terminal > New Terminal** with
PowerShell selected. The backend and frontend each run in their own terminal.
Commands below start from the repository root.

**Already set up?** Skip steps 1–2 and use the startup instructions in steps
3–4. Creating `.venv` is a first-time setup step; do not recreate it while
your terminal is already using that environment (`(.venv)` in the prompt).

### 1. Install backend dependencies (first time only)

Create the environment only if `backend/.venv` does not already exist.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Install frontend dependencies (first time only)

Open a second terminal at the repository root:

```powershell
cd frontend
npm i
```

`npm i` is shorthand for `npm install`. You only need to install dependencies
on first setup or after they change. For a clean reinstall using the exact
lockfile without updating it, use `npm ci`.

### 3. Start the backend

In the backend terminal, with the virtual environment activated:

If you are already in `backend/` and your prompt shows `(.venv)`, this is the
only command needed:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

When opening a fresh backend terminal, first run `cd backend` and
`.\.venv\Scripts\Activate.ps1` from the repository root.

Open [API documentation](http://127.0.0.1:8000/docs) to try the six `/api`
endpoints. A request to `/` returns 404 because there is no root API route;
use `/docs` or `/api/health` to check the running server.

### 4. Start the frontend

In the frontend terminal:

```powershell
npm run dev
```

Open [the dashboard](http://127.0.0.1:5173). These two development servers
run separately; the React dashboard calls the FastAPI backend.
Press `Ctrl+C` in each terminal to stop its server.

## Dataset ETL (Milestone 1)

ETL means extract, transform, load: obtain the CSV, validate and normalize its
fields with Pandas, then store observations in SQLite.

Use a third terminal while the development servers are running. From the
repository root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python scripts/etl.py --download
```

If your terminal is already in `backend/` with `(.venv)` active, run only the
last command. No environment recreation or dependency installation is needed.

The script downloads the official UCI ZIP only when the local CSV is absent.
It reads only `ai4i2020.csv` from the archive and leaves an existing CSV alone.
The default paths are resolved relative to the script, not the terminal:

- Source: `backend/data/raw/ai4i2020.csv` (ignored by Git).
- Database: `backend/data/smartfactory.db` (generated and ignored by Git).
- SQLite table: `observations`.

After downloading once, rerun the local pipeline with:

```powershell
python scripts/etl.py
```

The JSON report contains persisted SQL counts. The verified UCI CSV has
10,000 rows and 14 source columns; the database stores nine selected columns.

| Type | Observations | Labeled failures |
| --- | ---: | ---: |
| H | 1,003 | 21 |
| L | 6,000 | 235 |
| M | 2,997 | 83 |
| **Total** | **10,000** | **339** |

There are 9,661 non-failure observations and a 3.39% failure rate. These are
dataset label counts, not model evaluation results. The source has no missing
values or duplicate observation IDs.

### Validation and repeat runs

Required columns, missing or blank required values, invalid type codes,
duplicate observation IDs, nonnumeric or infinite values, fractional integer
fields, and invalid numeric ranges are checked before the database is changed.
Errors identify the affected field; rows are not silently discarded or filled.
The loader trims product IDs, normalizes type codes to `L/M/H`, and converts
numeric fields without changing their units.

Each successful run refreshes the entire `observations` table in one
transaction. Identical input produces identical records without duplicates;
changed input replaces the previous snapshot, including removing stale rows.
A validation or database write failure preserves the previous observations.
Custom files and database locations can be supplied with `--csv PATH` and
`--db PATH`; use `python scripts/etl.py --help` for the command options.

### Column mapping

| Source CSV column | SQLite column |
| --- | --- |
| `UDI` | `udi` (primary key) |
| `Product ID` | `product_id` |
| `Type` | `type` |
| `Air temperature [K]` | `air_temperature_k` |
| `Process temperature [K]` | `process_temperature_k` |
| `Rotational speed [rpm]` | `rotational_speed_rpm` |
| `Torque [Nm]` | `torque_nm` |
| `Tool wear [min]` | `tool_wear_min` |
| `Machine failure` | `machine_failure` (target label) |

The supplied `Machine failure` label is preserved. `TWF`, `HDF`, `PWF`, `OSF`,
and `RNF` are omitted: they are failure-mode labels and would leak the answer
if used as prediction inputs. Observation and product identifiers are stored
for display, not as future model inputs.

### Dataset attribution

Source: [AI4I 2020 Predictive Maintenance Dataset, UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)
(2020), [DOI: 10.24432/C5HS5C](https://doi.org/10.24432/C5HS5C).
Licensed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
The data describes synthetic operating observations. Transformations are the
documented column selection, renaming, whitespace/category normalization, and
numeric conversion; the failure labels are not recomputed.

## ML baseline (Milestone 2)

After the ETL has populated SQLite, run this command from `backend/`, with
your existing virtual environment active:

```powershell
python -m scripts.train
```

Use the module form (`-m scripts.train`) so Python can resolve the shared
`app` imports. Training is an offline command. It prints the evaluation report
and writes:

- `backend/artifacts/model.joblib`: the fitted preprocessing and classifier
  pipeline together (generated and ignored by Git).
- `backend/artifacts/metrics.json`: measured held-out metrics, class counts,
  feature names, split settings, model parameters, data fingerprint, and library
  versions.

Use `python -m scripts.train --help` for custom `--db` and `--artifacts-dir`
locations. Training reads the database without modifying it. Invalid or
insufficient training data is rejected before existing artifacts are touched.

### Training choices

The only inputs are `type`, `air_temperature_k`, `process_temperature_k`,
`rotational_speed_rpm`, `torque_nm`, and `tool_wear_min`. Identifiers and
failure-mode labels are excluded; `machine_failure` is the target, not an input.

A fixed, stratified 80/20 split with seed 42 produces 8,000 training rows and
2,000 held-out test rows. Training includes 271 failures and 7,729 non-failures;
testing includes 68 failures and 1,932 non-failures. Within an sklearn Pipeline,
StandardScaler scales the five numeric inputs and OneHotEncoder encodes type.
Both preprocessing and logistic regression are fitted only on training rows.
There are no missing values to impute. This follows sklearn's
[guidance for avoiding data leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage).

Logistic regression uses `class_weight="balanced"` to give the rare failure
class more weight, calculated from the training labels. The fixed solver is
`lbfgs`, `C=1.0`, and `max_iter=1000`. The decision threshold is 0.5. No
classifier comparison, parameter search, threshold tuning, or refitting on the
test set is performed. Repeating training on the same data and installed
versions reproduced the report and saved-model prediction.

### Measured held-out results

| Metric (failure is the positive class) | Result |
| --- | ---: |
| Precision | 14.18% |
| Recall | 82.35% |
| F1 | 24.19% |
| Average precision | 0.3818 |

Confusion matrix, with true classes in rows and predicted classes in columns:

| Actual label | Predicted non-failure (0) | Predicted failure (1) |
| --- | ---: | ---: |
| Non-failure (0) | 1,593 | 339 |
| Failure (1) | 12 | 56 |

The model detects 56 of 68 labeled failures, misses 12, and produces 339 false
alarms. This baseline therefore has low precision. These are measurements on
held-out synthetic observations, not evidence of production reliability.

Average precision summarizes the precision-recall curve using recall-weighted
precision; it is not the trapezoidal area calculation. See
[sklearn's metric documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html).
Accuracy alone would hide the rare-class behavior.

### Saved-model predictions

`app/schemas.py` validates the six required inputs. It rejects unknown types,
missing or extra fields (including identifiers and target labels), non-finite
values, invalid ranges, and fractional RPM/tool-wear values. `app/predictor.py`
loads the saved pipeline once and reuses its preprocessing for each prediction.

The output contains `predicted_failure`, a class-1 `model_score`, and
`model_name`. The score is a model-generated estimate, not a calibrated
real-world failure probability. It describes a measurement snapshot and does
not estimate time until failure.

## FastAPI endpoints (Milestone 3)

With the backend running, the base URL is `http://127.0.0.1:8000/api`.
Interactive request/response schemas are available in `/docs`.

| Method | Endpoint | Returns |
| --- | --- | --- |
| GET | `/health` | Process status plus database, model, and metrics readiness |
| GET | `/overview` | Observation count, failure count/rate, type count |
| GET | `/charts` | Type distribution and failure rates by type |
| GET | `/observations` | Filtered records with pagination metadata |
| GET | `/model-metrics` | The saved held-out evaluation report |
| POST | `/predict` | Predicted class, class-1 model score, model name |

Try an analytics request from PowerShell:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/overview
```

`failure_rate` values are fractions: `0.0339` means 3.39%. Charts return
`type_distribution` and `failure_rates_by_type` arrays. All totals and chart
values come from SQLite queries.

Observation requests accept `limit` (1–100, default 20), `offset` (nonnegative,
default 0), optional `type` (`L`, `M`, or `H`), and optional `failure` (`0` or
`1`). Combined filters use AND. Results are ordered by `udi` and return
`items`, `total`, `limit`, and `offset`; `total` counts all matching rows,
not just the current page. An offset beyond the last row returns an empty page.

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/observations?limit=20&offset=0&type=M&failure=0'
```

Example prediction request using the six required measurements:

```powershell
$predictionBody = @{
    type = "M"
    air_temperature_k = 300.0
    process_temperature_k = 310.0
    rotational_speed_rpm = 1500
    torque_nm = 40.0
    tool_wear_min = 100
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/predict -ContentType application/json -Body $predictionBody
```

### Startup and error behavior

The model and evaluation report load once during FastAPI's
[lifespan startup](https://fastapi.tiangolo.com/advanced/events/). Training does
not run inside the API. Restart the API after generating or replacing model
artifacts. SQLite queries use a fresh, read-only connection per request.

- `/health` responds with HTTP 200 while the process is available. Its status
  is `ok` when all resources are ready, otherwise `degraded`, with separate
  `database_ready`, `model_ready`, and `metrics_ready` fields.
- Missing/unreadable database or table: analytics endpoints return HTTP 503
  with an ETL setup instruction. A missing database is not silently created.
- Existing empty table: counts are zero and records/chart arrays are empty.
- Missing/unusable model: predictions return HTTP 503, while dataset analytics
  remain available. Missing/invalid metrics return HTTP 503 for `/model-metrics`.
- Invalid measurement fields, filters, or pagination return HTTP 422 with
  field details. Numeric overflow is also reported as a validation error.

Browser requests are permitted from the local Vite development origins on
port 5173 and production-preview origins on port 4173 (both `127.0.0.1` and
`localhost`) through explicit local
[CORS configuration](https://fastapi.tiangolo.com/tutorial/cors/).

If updating an existing checkout, refresh the backend dependencies once:

```powershell
python -m pip install -r requirements.txt
```

The pinned test client dependency is [HTTPX2](https://pypi.org/project/httpx2/),
which the installed Starlette version supports without the older HTTPX
deprecation warning.

## React dashboard (Milestone 4)

With the database populated and model trained, start both development servers
as described above, then open `http://127.0.0.1:5173`.

- Four summary cards show API-backed observation/failure counts, failure rate,
  and quality-variant count. Loading or unavailable data is not shown as zero.
- Two Recharts bar charts show observations by quality type and actual labeled
  failure rates. Fractional API rates are formatted as percentages in the UI.
- The prediction form accepts all six operating measurements. Editable example
  inputs are identified as examples; a result appears only after inference.
  Submitting disables the controls, and editing measurements clears old output.
- The observations table combines quality-type and actual-label filters with
  ten-row server pagination. Changing a filter returns to the first page.
  The table scrolls horizontally on small screens without widening the page.
- Model evaluation displays the saved precision, recall, F1, average precision,
  confusion matrix, and actual false-alarm/missed-failure counts.

Sections have independent loading, error, retry, and empty states. The header
shows API readiness, and **Refresh data** reloads analytics, readiness, model
evaluation, and the current table query. Predictions are unavailable when the
API reports that the model is not ready. Dataset attribution, license, and
repository links are included in the footer.

### API address and production preview

The browser API base defaults to `http://127.0.0.1:8000/api`. To change it, copy
`frontend/.env.example` to `frontend/.env.local`, set `VITE_API_BASE_URL`, and
restart Vite. This is public browser configuration, not a place for secrets.
The production build includes the configured value at build time.

From `frontend/`, with the backend running, preview the built app locally:

```powershell
npm run build
npm run preview
```

Open `http://127.0.0.1:4173`. Chart code is loaded separately from the main
dashboard bundle. Development and built-preview browser checks both confirmed
the real dataset counts, chart rendering, and saved-model predictions.

## Setup checks

In the backend terminal, with the virtual environment activated:

```powershell
python -m pip check
python -m pytest tests -q
```

Tests use small invented fixtures, temporary databases, and temporary model
artifacts. They run offline without the downloaded dataset, and cover ETL
validation and rollback, strict prediction inputs, leakage prevention,
training-only preprocessing, held-out metrics, model reload, and reproducibility.
API tests use FastAPI TestClient with temporary SQLite/model resources to check
all six routes, filtered pagination, empty/missing resources, startup caching,
validation errors, and local development/preview CORS. All 144 backend tests pass.

In the frontend terminal:

```powershell
npm run build
npm run test:e2e
```

The seven Playwright browser checks use the real local API, database, and saved
model for counts, charts, predictions, filtering, and pagination. Controlled
test responses exercise only missing-model, error, and empty states. Desktop
and 390px-wide screenshots are captured in `frontend/test-results/` (ignored).

Browser checks expect the default local ports 8000 and 5173 and require ETL
and training to have been run. The test runner reuses existing development
servers or starts its own and stops only the servers it started. On Windows it
uses installed Microsoft Edge in headless mode. Other environments can install
Chromium using `npx playwright install chromium`; see
[Playwright browser setup](https://playwright.dev/docs/browsers).

The frontend build is written to `frontend/dist/`. Local environments,
dependencies, builds, raw data, databases, and trained models are ignored by Git.

## PowerShell troubleshooting

If PowerShell reports that `npm.ps1` or `Activate.ps1` cannot run because scripts
are disabled, you can allow local scripts for that terminal session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

This setting ends when the terminal closes. See
[Microsoft's execution-policy documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies).

Alternatively, `npm.cmd` runs the same installed npm through its Windows launcher.
For Python, you can use `.\.venv\Scripts\python.exe` directly from `backend/`
instead of activating the environment. Neither fallback requires changing the
execution policy.

## Planned stack

- Backend: Python, FastAPI, Pydantic, Pandas, scikit-learn, SQLite, joblib.
- Frontend: React, Vite, Tailwind CSS, Recharts.
- Tests: pytest for ETL and ML, FastAPI TestClient with HTTPX2, and Playwright browser checks.

## References

- [Vite guide](https://vite.dev/guide/)
- [Tailwind CSS with Vite](https://tailwindcss.com/docs/installation/using-vite)
- [Dataset: UCI AI4I 2020](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)

