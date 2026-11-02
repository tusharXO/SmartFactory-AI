# SmartFactory AI: portfolio and interview notes

SmartFactory AI is a local portfolio demo that turns synthetic operating
observations into SQL-backed analytics and snapshot failure classification.
Use the [README](../README.md) for setup and architecture; the
[saved evaluation report](../backend/artifacts/metrics.json) is the source for
the results below.

## Resume bullets

- Built a Python/Pandas ETL pipeline that validates 10,000 synthetic industrial
  observations, refreshes SQLite atomically, and serves SQL analytics and
  filtered, paginated records through FastAPI.
- Trained and saved a six-feature scikit-learn classification pipeline and
  integrated it with a responsive React/Recharts dashboard for predictions,
  dataset exploration, and held-out evaluation; measured 82.35% recall and
  14.18% precision on 2,000 test observations.

These describe implemented work. Add a repository link beside the project
title; make claims about business impact only after measuring that impact.

## A 90-second demo

Start both servers using the README, then open `http://127.0.0.1:5173`.
Have the dataset loaded and the saved model ready before presenting.

| Time | Action and talking point |
| --- | --- |
| 0–15 s | Open **Overview**. Point to 10,000 observations, 339 labeled failures, a 3.39% failure rate, and three quality variants. Explain that these are synthetic observations. |
| 15–30 s | Show the two charts: quality-type distribution and labeled failure rates by type. Explain that their values come from SQLite through FastAPI. |
| 30–50 s | Select **Prediction**, keep the labeled example measurements, and click **Run prediction**. Explain the returned class and class-1 model score. Edit one measurement to show the old result clears, then use **Reset example**. |
| 50–65 s | Select **Observations**. Choose quality type `L` and actual label **Failure (1)**, then click **Next**. Explain that filtering and ten-row pagination run on the server. |
| 65–90 s | Select **Model evaluation**. Explain 56 detected failures, 12 misses, and 339 false alarms. Close with the tradeoff: this baseline catches many failures but produces many false positives; further validation would be needed for operational use. |

The form classifies a measurement snapshot. Its score is an uncalibrated
model estimate; the app has no time-to-failure prediction or live sensor feed.

## Results to know

The stratified 80/20 split uses seed 42. Only training rows are used to fit
the preprocessing and class-balanced logistic regression.

| Split | Non-failure (0) | Failure (1) | Total |
| --- | ---: | ---: | ---: |
| Full dataset | 9,661 | 339 | 10,000 |
| Training | 7,729 | 271 | 8,000 |
| Held-out test | 1,932 | 68 | 2,000 |

| Held-out metric | Value |
| --- | ---: |
| Precision | 14.18% |
| Recall | 82.35% |
| F1 | 24.19% |
| Average precision | 0.3818 |

Confusion matrix: actual classes are rows, predicted classes are columns.

| Actual label | Predicted 0 | Predicted 1 |
| --- | ---: | ---: |
| Non-failure (0) | 1,593 | 339 |
| Failure (1) | 12 | 56 |

Of 395 predicted failures, 56 are actual failures: most alerts are false
positives. Recall is 56/68; precision is 56/395. The 339 false alarms in the
test set happen to equal the full dataset's 339 failures; they are different
counts with different meanings.

## Eight interview questions

**1. Why these six features? How did you prevent target leakage?**
The inputs are quality type, air and process temperatures, rotational speed,
torque, and tool wear. `UDI` and `Product ID` identify records and are excluded
from prediction. The five failure-mode flags describe failure outcomes, so
using them would leak the answer. `Machine failure` is the supplied target.

**2. How did you keep evaluation separate from training?**
I split the data before fitting. A single sklearn Pipeline fits numeric
StandardScaler, categorical OneHotEncoder, and logistic regression on 8,000
training rows. The 2,000 held-out rows are used for evaluation. There is no
test-set parameter search, threshold tuning, or final refit on the test set.

**3. Why is recall high while precision is low?**
Failures represent 3.39% of the dataset. `class_weight="balanced"` increases
the rare class's weight during fitting. At the fixed 0.5 threshold this model
detects 56 of 68 test failures while raising 339 false alarms. Accuracy alone
would obscure this tradeoff; operational alert costs would matter when
choosing a model and threshold.

**4. What does average precision measure?**
It summarizes precision across score thresholds, weighting each precision by
the increase in recall. The report uses sklearn's `average_precision_score`
on class-1 scores. Its 0.3818 value uses a stepwise sum rather than trapezoidal
integration; it is separate from precision at the 0.5 decision threshold.

**5. What makes the ETL idempotent and safe to rerun?**
It validates the full CSV before writing, including required fields, finite
numbers, categories, and unique observation IDs. It replaces the table's
contents within one SQLite transaction. Repeating the same input produces
the same records; changed input removes stale rows. Invalid input or a failed
write preserves the previous data.

**6. How do filtering and pagination work?**
The API opens read-only SQLite connections and binds filter values, limit,
and offset as SQL parameters. Combined filters use AND. Count and page queries
share a consistent snapshot; records are ordered by `udi`. The response
includes the filtered total, so the React table can navigate ten-row pages.

**7. How do training and API inference stay consistent?**
Offline training saves the fitted preprocessing and classifier together with
joblib. FastAPI loads the pipeline and evaluation report once at startup.
Pydantic validates the six inputs, and inference reuses that saved pipeline.
The API must restart after artifacts change; it never trains per request.

**8. What can you conclude from this dataset?**
The measured results describe held-out synthetic snapshots. There is no
timestamp sequence, demonstrated real-factory generalization, remaining-life
estimate, or calibrated real-world failure probability. The project proves
the local ETL-to-dashboard flow and makes its baseline's limitations visible.

## Possible future work

These are proposals, not completed features: compare a second classifier,
choose thresholds using training/validation data and explicit alert costs,
then evaluate a locked choice on untouched data. Calibration and validation
on representative real operating data would require additional evidence.
