# SmartFactory AI

A portfolio project for exploring synthetic industrial equipment data and
classifying operating measurements with machine learning.

**Current progress:** Milestone 2 — trained ML baseline. The equipment CSV is
validated and stored in SQLite, and an offline command trains and evaluates a
failure classifier with saved preprocessing. The frontend is a starter page
and the backend is a FastAPI scaffold. Application endpoints and dashboard
features come in later milestones. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for
the scope and build order.

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

Open [API documentation](http://127.0.0.1:8000/docs). Through Milestone 2 this page
has no application endpoints yet. A request to `/` returns 404 until a route is
added; the server can still be running correctly.

### 4. Start the frontend

In the frontend terminal:

```powershell
npm run dev
```

Open [the starter page](http://127.0.0.1:5173). These two development servers
run separately; the frontend will call the backend when we build the dashboard.
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
not estimate time until failure. The prediction API is the next milestone.

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

In the frontend terminal:

```powershell
npm run build
```

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
- Tests: pytest for ETL and ML; FastAPI TestClient checks are planned with the API.

## References

- [Vite guide](https://vite.dev/guide/)
- [Tailwind CSS with Vite](https://tailwindcss.com/docs/installation/using-vite)
- [Dataset: UCI AI4I 2020](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)

