# Screenshot provenance

Captured on **2 November 2026** from the local React development dashboard,
using headless Microsoft Edge and real FastAPI responses backed by the UCI
SQLite observations and saved LogisticRegression pipeline.

| File | Capture |
| --- | --- |
| [dashboard-desktop.png](dashboard-desktop.png) | 1440 × 1100 viewport, after real example inference |
| [dashboard-mobile.png](dashboard-mobile.png) | 390 × 844 viewport, full page, same actual prediction |
| [model-evaluation.png](model-evaluation.png) | The rendered model evaluation section |

Example inputs: M, air 300 K, process 310 K, speed 1500 rpm, torque 40 Nm,
wear 100 min. Actual result: non-failure (0), score 0.09657064265880015,
displayed as 0.0966. Evaluation values come from
[the saved report](../../backend/artifacts/metrics.json).

These are browser screenshots, with no fabricated data or image editing.
The model score is an uncalibrated estimate for a synthetic snapshot.
