# SmartFactory AI — Project Blueprint

> **Status:** Milestone 2 complete. The dataset is loaded into SQLite and a reproducible baseline classifier is trained and evaluated; application APIs and dashboard features remain planned.  
> **Working style:** We will build this together, one milestone at a time, in VS Code with Codex.  
> **Primary goal:** A small, finished, explainable project aligned with Magna's **Intern, Smart Factory Solutions** role: Python, ETL, data analysis, ML, SQL, APIs, React, and visualizations.

---

## 1. Product in one paragraph

**SmartFactory AI** is a responsive, single-page dashboard for exploring a synthetic industrial equipment dataset and estimating whether a set of operating measurements belongs to the **machine-failure** class. A Python pipeline loads and validates the dataset, stores observations in SQLite, and trains a scikit-learn model. A FastAPI backend exposes analytics, paginated observations, model evaluation metrics, and a prediction endpoint. A React frontend displays charts, records, and a prediction form.

This is a **portfolio/demo application**, not real-time factory monitoring or a production safety system. Predictions classify a measurement snapshot; they **do not predict when** a machine will fail.

### Success criteria

- Demonstrate a real **extract → transform → load (ETL)** process.
- Train and evaluate an actual **supervised ML classifier** (not just call an LLM API).
- Use **SQL** to query the loaded dataset.
- Deliver well-structured **Python APIs** and an attractive **React dashboard**.
- Make the project easy to demo, explain in an interview, and add to a one-page resume.
- Keep implementation intentionally simple. **Finishing matters more than adding features.**

## 2. Stack — fixed for MVP

| Layer | Choice | Reason |
|---|---|---|
| Frontend | React + Vite (JavaScript) | Fast setup; familiar stack |
| Styling | Tailwind CSS | Responsive, tidy dashboard |
| Charts | Recharts | Lightweight React visualizations |
| Backend | Python + FastAPI + Pydantic | Python APIs and input validation |
| ETL | Pandas | CSV validation, cleaning, transformation |
| ML | scikit-learn | Real classification and metrics |
| Database | SQLite (`sqlite3`) | SQL without database-server setup |
| Model persistence | joblib | Load trained preprocessing + model pipeline |
| Tests | pytest + FastAPI TestClient | Test data handling and endpoints |

**Not in MVP:** auth, roles, sockets/live streaming, IoT integration, microservices, Kafka, Redis, Docker, cloud infrastructure, LLMs, notifications, scheduling, multiple dashboards, complex design systems, or a Node.js service. We can revisit deployment after the local app works.

## 3. Dataset and safe ML framing

**Source:** [UCI AI4I 2020 Predictive Maintenance Dataset](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)  
**Dataset DOI:** https://doi.org/10.24432/C5HS5C  
**License:** CC BY 4.0 — attribute the dataset in README and UI.  
**Scale:** 10,000 **synthetic observations**, not 10,000 unique machines.

### Six input features

| Original CSV column | Application field | Type |
|---|---|---|
| `Type` | `type` | category `L`, `M`, `H` (product-quality variant) |
| `Air temperature [K]` | `air_temperature_k` | number |
| `Process temperature [K]` | `process_temperature_k` | number |
| `Rotational speed [rpm]` | `rotational_speed_rpm` | number |
| `Torque [Nm]` | `torque_nm` | number |
| `Tool wear [min]` | `tool_wear_min` | number |

**Prediction target:** `Machine failure` → `machine_failure` (`0`/`1`).

**Never pass these into the model:**

- `UDI` and `Product ID`: row/product identifiers, not appropriate predictive inputs for this demo.
- `TWF`, `HDF`, `PWF`, `OSF`, `RNF`: failure-mode **target labels**. Including them would create target leakage and misleadingly good performance.
- `Machine failure`: the answer we are trying to predict.

The five failure-mode flags can be ignored in the MVP. No synthetic timestamps, fake sensor streams, fake machine counts, or invented accuracy claims.

### Evaluation approach

1. Validate the raw dataset and the binary target distribution.
2. Create a **stratified** train/test split with a fixed random seed, keeping the held-out test set separate.
3. Fit any imputers/encoders/scalers **only on training data**, within an sklearn `Pipeline` / `ColumnTransformer`.
4. Start with **one simple baseline classifier**, e.g. logistic regression with an appropriate imbalance strategy. No hyperparameter hunt for the MVP.
5. Record **precision, recall, F1, confusion matrix, and average precision (PR-AUC)** on held-out data. Show class counts as context; accuracy alone is misleading when failures are rare.
6. Save the fitted full preprocessing + model pipeline and a JSON metrics report. Use the same pipeline at inference.
7. If displaying `predict_proba`, label it a **model-generated score/estimate**, not a calibrated real-world failure probability. Do not claim calibration unless separately tested.

This dataset represents operating snapshots and associated labels; it does **not** justify a 'failure in X days' feature.

## 4. MVP user experience

A **single dashboard route** (`/`) with these sections, from top to bottom:

1. **Header:** `SmartFactory AI`, subtitle `Predictive Maintenance Analytics`, `Synthetic dataset demo` label.
2. **KPI cards:** total observations, observations labeled failure, failure rate, number of quality variants.
3. **Analytics:**
   - Observation distribution by product type (`L/M/H`).
   - Failure rate by product type (clearly labeled percentages).
   - Optionally one sensor chart after MVP works (e.g. torque distribution).
4. **Prediction panel:** a form for all six inputs, `Run Prediction` button, model output (predicted class and model score), explanatory disclaimer. No fake 'real-time health' claims.
5. **Observations table:** compact paginated rows with type, temperature, RPM, torque, tool wear, and actual labeled failure; filters for type and failure label.
6. **Model summary:** read-only held-out evaluation metrics and short explanation that the data is synthetic.
7. **Footer:** attribution link to UCI and link to GitHub repository when created.

### Visual style

- Clean, minimal industrial SaaS aesthetic; charcoal/navy or light neutral surface with one accent color.
- Responsive: widescreen two-column analytics/prediction layout; single-column on mobile.
- Clear spacing, restrained colors, readable typography, simple icons if needed.
- Data loading, empty states, API error messages, and disabled submit while predicting.
- Avoid unnecessary animation, giant hero sections, and decorative charts.

## 5. Architecture

```text
UCI dataset (ai4i2020.csv)
          |
          v
Python ETL (validate + rename + clean)
          |
          v
      SQLite database ---------> FastAPI /analytics + /observations
          |
          v
Train/test split (no leakage)
          |
          v
scikit-learn preprocessing + classifier
          |
          +------> saved model artifact ------> FastAPI /predict
          |
          +------> saved evaluation JSON -----> FastAPI /model-metrics
                                                     |
                                                     v
                                           React + Recharts dashboard
```

The model-training script is an **offline command**, not something the server reruns on every request. The API reads the saved artifact when it starts.

## 6. Planned repository structure

> This is the target layout. Files are added incrementally as their milestones are implemented. Keep the file count small.

```text
smartfactory-ai/
├── PROJECT_PLAN.md                 # This document
├── README.md                       # Create at final documentation milestone
├── .gitignore
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app, CORS, route registration
│   │   ├── routes.py                # Health, summary, charts, table, prediction
│   │   ├── schemas.py               # Pydantic input/output models
│   │   ├── db.py                    # SQLite connection and SQL queries
│   │   └── predictor.py             # Load trained model and run inference
│   ├── scripts/
│   │   ├── etl.py                   # CSV → validation/transform → SQLite
│   │   └── train.py                 # Training, evaluation, saved artifacts
│   ├── data/
│   │   ├── raw/                     # Downloaded UCI CSV (not committed by default)
│   │   └── smartfactory.db          # Generated local database (gitignored)
│   ├── artifacts/
│   │   ├── model.joblib             # Generated trained model (gitignored)
│   │   └── metrics.json             # Generated model evaluation summary
│   └── tests/
│       ├── test_etl.py
│       ├── test_api.py
│       └── test_prediction.py
└── frontend/
    ├── package.json
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx                  # One-page dashboard composition
        ├── index.css
        ├── api.js                   # API base URL and fetch helpers
        └── components/
            ├── MetricCard.jsx
            ├── AnalyticsCharts.jsx
            ├── PredictionForm.jsx
            ├── ObservationsTable.jsx
            └── ModelMetrics.jsx
```

We may simplify individual modules further during implementation, but should avoid unnecessary architectural layers.

## 7. Data storage plan

One core SQLite table: **`observations`**.

| Column | Meaning |
|---|---|
| `udi` | Source observation ID / primary key |
| `product_id` | Source product ID (display only, not ML feature) |
| `type` | L, M, H category |
| `air_temperature_k` | Sensor input |
| `process_temperature_k` | Sensor input |
| `rotational_speed_rpm` | Sensor input |
| `torque_nm` | Sensor input |
| `tool_wear_min` | Sensor input |
| `machine_failure` | Ground-truth class label |

ETL must be **idempotent**: rerunning it should not duplicate observations. Keep raw names-to-schema mapping documented. No need for accounts, users, prediction-history tables, or migrations in this MVP.

## 8. API contract (planning, not implementation)

Base: `http://localhost:8000/api`

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | API running and model ready/not ready |
| GET | `/overview` | Total observations, failure count/rate, type count |
| GET | `/charts` | Type distribution and failure rates by type |
| GET | `/observations?limit=20&offset=0&type=M&failure=0` | Paginated/filterable observation table; filters optional |
| GET | `/model-metrics` | Held-out evaluation metrics and model information |
| POST | `/predict` | Validate six features and return predicted class + model score |

**Example prediction request** (illustrative values, not a test result):

```json
{
  "type": "M",
  "air_temperature_k": 300.0,
  "process_temperature_k": 310.0,
  "rotational_speed_rpm": 1500,
  "torque_nm": 40.0,
  "tool_wear_min": 100
}
```

**Example response shape** (deliberately no invented numeric prediction):

```json
{
  "predicted_failure": "0 or 1, returned by model",
  "model_score": "numeric value returned by model",
  "model_name": "trained classifier name"
}
```

In actual code, `predicted_failure` will be an integer and `model_score` a number, not the explanatory placeholders above. Use Pydantic validation, helpful 422 errors, safe pagination limits, and explicit 503 responses when the model artifact is missing. All frontend analytics should come from real SQLite queries, not hardcoded totals.

## 9. Milestones — build one at a time

### Milestone 0 — Repository setup

- [x] Create repository structure only when we start together.
- [x] Initialize Python virtual environment and frontend Vite project.
- [x] Confirm dependencies and commands run locally.
- [x] Create useful `.gitignore` entries for venv, node_modules, database, and artifacts.

**Done when:** both minimal development servers can start; no product features yet.

**Verified:** Python dependency imports and `pip check` pass; FastAPI `/docs` and `/openapi.json` return HTTP 200. The frontend production build passes, and the Vite server returns HTTP 200 for the starter page, compiled React component, and Tailwind stylesheet. Setup and run commands are in README.

### Milestone 1 — ETL + SQLite

- [x] Obtain the dataset from its official UCI source and document attribution.
- [x] Inspect columns and class balance.
- [x] Validate required columns, nulls, type codes, duplicate IDs, and numeric values.
- [x] Rename columns and create/load `observations` in SQLite.
- [x] Confirm counts and repeat-run idempotency with tests.

**Done when:** SQL queries return real dataset records and rerunning ETL does not duplicate them.

**Verified:** Official CSV has 10,000 rows and 14 columns, no missing values or duplicate observation IDs, and 339 failures / 9,661 non-failures (3.39% failure rate). The database stores nine mapped columns and remains at 10,000 rows after a repeated ETL run. A fresh download/load also passed. All 52 ETL tests pass, including invalid-input preservation and database transaction rollback. The loader validates first, then replaces the dataset in one transaction; README documents commands, mapping, and CC BY 4.0 attribution.

### Milestone 2 — ML baseline

- [x] Train a leakage-free classifier using the six feature inputs.
- [x] Use stratified train/test splitting and an sklearn preprocessing pipeline.
- [x] Compute/record precision, recall, F1, confusion matrix, PR-AUC and class counts.
- [x] Save model artifact and metrics JSON.
- [x] Check one valid prediction and one invalid input case.

**Done when:** an offline script reproducibly trains, evaluates, and saves a usable model. No claimed score until measured.

**Verified:** Class-balanced logistic regression uses only the six approved features. With seed 42 and a stratified 80/20 split, preprocessing and classification fit 8,000 training observations; 2,000 test observations include 68 failures. Held-out precision is 14.18%, recall 82.35%, F1 24.19%, and average precision 0.3818. Confusion matrix is `[[1593, 339], [12, 56]]` with labels `[0, 1]`: 56 detected failures, 12 missed failures, and 339 false alarms. This is a low-precision baseline, with no test-set tuning. The fitted full pipeline and report are saved to `backend/artifacts/`; retraining reproduced the report and a saved-model prediction. Strict input validation rejects invalid measurements and extra fields. All 100 backend tests pass (52 ETL + 48 ML/prediction). Run `python -m scripts.train` from `backend/` with the existing virtual environment active.

### Milestone 3 — FastAPI

- [ ] Implement the six API endpoints in the contract.
- [ ] Query overview/charts/table data from SQLite.
- [ ] Load the trained model once; validate prediction inputs.
- [ ] Handle empty database, missing model, bad inputs, and pagination.
- [ ] Add a few pytest/TestClient checks.

**Done when:** all endpoints return real data and can be tested in FastAPI's `/docs` UI.

### Milestone 4 — React dashboard

- [ ] Build responsive header + KPI cards.
- [ ] Build two useful charts.
- [ ] Build prediction form and result state.
- [ ] Build filterable, paginated observations table.
- [ ] Display model metrics, loading/error/empty states, and attribution.

**Done when:** the entire demo works in a browser, with real backend data and no fabricated dashboard numbers.

### Milestone 5 — Polish + portfolio proof

- [ ] Test the full flow after a clean setup from the README.
- [ ] Improve layout, mobile responsiveness, form usability, and error messages.
- [ ] Add README: problem, architecture, setup, dataset license, evaluation, screenshots, limitations.
- [ ] Record real metrics and screenshots for GitHub and interview discussion.
- [ ] Optional deployment **only after** the local experience is stable.

**Done when:** another developer can reproduce the app using README instructions.

## 10. Scope guardrails

**Must have:** ETL, actual SQL storage, one real trained model, honest evaluation, FastAPI endpoints, React dashboard, charts, working prediction, and README.

**Nice to have later:** downloadable CSV, feature-importance chart, second classifier comparison, deployment, an optional advanced sensor chart.

**Never add just to impress recruiters:** fake live telemetry, unsupported future-failure time estimates, LLM chat, complex infrastructure, fake accuracy numbers, or unverified resume claims.

## 11. Resume and interview outcome

Only **after the app is working**, derive two concise resume bullets from verified facts. Candidate structures:

- `Built a Python/Pandas ETL pipeline to process 10,000 synthetic industrial equipment observations, persist normalized records in SQLite, and expose analytics through FastAPI.`
- `Trained and evaluated a scikit-learn failure classifier using six equipment features; integrated inference with a React dashboard featuring visualizations and filtering (report measured precision/recall/F1 only after testing).`

Be able to answer: Why these six features? What is data leakage? Why use a stratified split? What does precision vs recall mean for failures? How does the ETL stay idempotent? What SQL queries drive the charts? Why isn't this real predictive maintenance in a production factory?

## 12. Instructions for Codex (read before coding)

**Project collaboration rules:**

1. Treat this file as the source of truth for scope and goals.
2. **Do not generate the entire application at once.** Implement only the milestone we explicitly select.
3. Before each milestone, briefly describe the files you will create/change and the acceptance checks.
4. Make small, understandable changes; prefer simple code to unnecessary abstractions.
5. Explain critical ML/ETL choices, especially leakage prevention and class imbalance.
6. Use actual dataset queries and test results. Never fabricate metrics, predictions, or screenshots.
7. After each milestone, report what changed, which commands/tests ran, and any unresolved issues.
8. Stop at the milestone boundary and let us review before moving forward.
9. Do not deploy, publish, connect cloud services, or push a remote repository without explicit approval.
10. Keep this planning file updated if we jointly change a significant design choice.
11. Use standard VS Code PowerShell commands in instructions (`npm` and activated-environment `python`). Prefer current stable tooling, and explain platform-specific fallbacks only when needed.

### First prompt to paste into Codex when ready

> Read `PROJECT_PLAN.md` thoroughly. We are building **SmartFactory AI** together as a learning and resume project. Do not scaffold or write code yet. First, summarize the MVP architecture, the planned milestones, and any implementation risks you notice. Then propose the exact small set of actions for **Milestone 0** and wait for my approval before changing files. Follow the collaboration rules in Section 12 throughout this project.

---

**Official dataset:** https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset  
**Target job context:** Magna — Intern, Smart Factory Solutions (R00244571).  
**Reminder:** This document is a blueprint. Checked milestones record verified progress; unchecked features remain planned.
