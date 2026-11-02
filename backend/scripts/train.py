"""Train and evaluate one failure-classification baseline from SQLite."""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
from uuid import uuid4
import warnings

import joblib
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.schemas import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    PredictionInput,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "smartfactory.db"
DEFAULT_ARTIFACTS_DIR = BACKEND_DIR / "artifacts"
TARGET = "machine_failure"
RANDOM_STATE = 42
TEST_SIZE = 0.2


def read_training_data(db_path: Path) -> pd.DataFrame:
    """Read only the allowlisted features and target, without modifying SQLite."""
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(
            f"Database not found: {db_path}. Run python scripts/etl.py --download first."
        )
    # Column names are code-owned constants; no user input is inserted into SQL.
    columns = [*FEATURE_COLUMNS, TARGET]
    query = f"SELECT {', '.join(columns)} FROM observations ORDER BY udi"
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        cursor = connection.execute(query)
        observations = pd.DataFrame(cursor.fetchall(), columns=columns)

    if observations.empty:
        raise ValueError("The observations table is empty. Run the ETL first.")
    if not observations[TARGET].isin([0, 1]).all():
        raise ValueError("machine_failure must contain only binary labels 0 and 1.")
    observations[TARGET] = observations[TARGET].astype("int64")
    counts = observations[TARGET].value_counts()
    if set(counts.index) != {0, 1} or counts.min() < 2:
        raise ValueError("Training requires both classes 0 and 1, with at least two rows each.")

    for row in observations[FEATURE_COLUMNS].to_dict(orient="records"):
        PredictionInput.model_validate(row)
    return observations


def build_pipeline() -> Pipeline:
    """Keep scaling, category encoding, and classification in one saved object."""
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
            (
                "type",
                OneHotEncoder(
                    categories=[["L", "M", "H"]],
                    handle_unknown="error",
                    sparse_output=False,
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                LogisticRegression(class_weight="balanced", solver="lbfgs", max_iter=1000),
            ),
        ]
    )


def class_counts(labels: pd.Series) -> dict:
    return {str(label): int((labels == label).sum()) for label in (0, 1)}


def train_model(
    db_path: Path = DEFAULT_DB_PATH, artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR
) -> dict:
    """Fit on training rows, evaluate held-out rows, and persist the full pipeline."""
    db_path, artifacts_dir = Path(db_path), Path(artifacts_dir)
    observations = read_training_data(db_path)
    features, labels = observations[FEATURE_COLUMNS], observations[TARGET]
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=TEST_SIZE,
        stratify=labels,
        random_state=RANDOM_STATE,
    )
    if y_train.nunique() != 2 or y_test.nunique() != 2:
        raise ValueError("Both train and test splits must contain classes 0 and 1; more rows are needed.")

    pipeline = build_pipeline()
    with warnings.catch_warnings():
        # Do not save a baseline that failed to converge within its fixed budget.
        warnings.simplefilter("error", ConvergenceWarning)
        pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    scores = pipeline.predict_proba(x_test)[:, 1]
    report = {
        "model_name": "LogisticRegression",
        "features": FEATURE_COLUMNS,
        "target": TARGET,
        "source": {
            "database": db_path.name,
            "table": "observations",
            "rows": len(observations),
            "sha256": hashlib.sha256(
                observations.to_csv(index=False).encode("utf-8")
            ).hexdigest(),
        },
        "split": {
            "strategy": "stratified",
            "random_state": RANDOM_STATE,
            "test_size": TEST_SIZE,
            "train_rows": len(x_train),
            "test_rows": len(x_test),
        },
        "class_counts": {
            "overall": class_counts(labels),
            "train": class_counts(y_train),
            "test": class_counts(y_test),
        },
        "metrics": {
            "precision": float(precision_score(y_test, predictions, zero_division=0)),
            "recall": float(recall_score(y_test, predictions, zero_division=0)),
            "f1": float(f1_score(y_test, predictions, zero_division=0)),
            "average_precision": float(average_precision_score(y_test, scores)),
            "confusion_matrix": confusion_matrix(y_test, predictions, labels=[0, 1]).tolist(),
        },
        "confusion_matrix_labels": [0, 1],
        "decision_threshold": 0.5,
        "model_parameters": {
            "class_weight": "balanced",
            "solver": "lbfgs",
            "max_iter": 1000,
            "C": 1.0,
        },
        "library_versions": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "pandas": pd.__version__,
            "joblib": joblib.__version__,
        },
        "score_note": (
            "Class-1 model-generated score, not a calibrated real-world failure probability. "
            "Evaluation uses held-out observation labels and does not predict time to failure."
        ),
    }

    # Stage in the destination directory so files inherit its Windows permissions.
    # TemporaryDirectory gives children an owner-only ACL that survives a move.
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    staging_name = f".training-{uuid4().hex}"
    staged_model = artifacts_dir / f"{staging_name}.joblib"
    staged_report = artifacts_dir / f"{staging_name}.json"
    try:
        joblib.dump(pipeline, staged_model)
        staged_report.write_text(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        staged_model.replace(artifacts_dir / "model.joblib")
        staged_report.replace(artifacts_dir / "metrics.json")
    finally:
        staged_model.unlink(missing_ok=True)
        staged_report.unlink(missing_ok=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Source SQLite path")
    parser.add_argument(
        "--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR, help="Model/report directory"
    )
    args = parser.parse_args()
    try:
        report = train_model(args.db, args.artifacts_dir)
    except (OSError, ValueError, sqlite3.Error, ConvergenceWarning) as error:
        parser.exit(1, f"Training failed: {error}\n")
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
