"""Validate training and inference with invented data, never portfolio metrics."""

from contextlib import closing
import json
import sqlite3

import joblib
import numpy as np
import pandas as pd
from pydantic import ValidationError
import pytest
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from app.predictor import Predictor
from app.schemas import FEATURE_COLUMNS, NUMERIC_FEATURES, PredictionInput
from scripts.train import read_training_data, train_model


EXPECTED_FEATURES = [
    "type",
    "air_temperature_k",
    "process_temperature_k",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_min",
]
VALID_INPUT = {
    "type": "M",
    "air_temperature_k": 300.0,
    "process_temperature_k": 310.0,
    "rotational_speed_rpm": 1500,
    "torque_nm": 40.0,
    "tool_wear_min": 100,
}


def synthetic_observations():
    """Return varied test rows with identifier and target-leakage decoys."""
    rows = []
    for index in range(120):
        failure = int(index % 7 == 0)
        rows.append(
            {
                "udi": index + 1,
                "product_id": f"display-only-{index}",
                "type": ["L", "M", "H"][index % 3],
                "air_temperature_k": 295.0 + index * 0.15,
                "process_temperature_k": 305.0 + index * 0.08,
                "rotational_speed_rpm": 1200 + (index * 37) % 900,
                "torque_nm": float(15 + (index * 11) % 70),
                "tool_wear_min": (index * 7) % 241,
                "machine_failure": failure,
                "TWF": failure,
                "HDF": failure,
                "PWF": failure,
                "OSF": failure,
                "RNF": failure,
            }
        )
    return pd.DataFrame(rows)


def write_database(observations, database_path):
    # Reverse physical insertion order to exercise the ORDER BY udi contract.
    with closing(sqlite3.connect(database_path)) as connection:
        observations.iloc[::-1].to_sql("observations", connection, index=False)


@pytest.fixture(scope="module")
def trained_demo(tmp_path_factory):
    directory = tmp_path_factory.mktemp("synthetic_training")
    database_path = directory / "observations.db"
    artifacts_dir = directory / "artifacts"
    observations = synthetic_observations()
    write_database(observations, database_path)
    report = train_model(database_path, artifacts_dir)
    pipeline = joblib.load(artifacts_dir / "model.joblib")
    x_train, x_test, y_train, y_test = train_test_split(
        observations[EXPECTED_FEATURES],
        observations["machine_failure"],
        test_size=0.2,
        stratify=observations["machine_failure"],
        random_state=42,
    )
    return {
        "database": database_path,
        "artifacts": artifacts_dir,
        "observations": observations,
        "report": report,
        "pipeline": pipeline,
        "x_train": x_train,
        "x_test": x_test,
        "y_train": y_train,
        "y_test": y_test,
    }


def test_prediction_input_accepts_the_six_operating_measurements():
    measurement = PredictionInput.model_validate(VALID_INPUT)

    assert measurement.model_dump() == VALID_INPUT
    assert FEATURE_COLUMNS == EXPECTED_FEATURES


@pytest.mark.parametrize("field", EXPECTED_FEATURES)
def test_prediction_input_requires_every_feature(field):
    payload = {key: value for key, value in VALID_INPUT.items() if key != field}

    with pytest.raises(ValidationError):
        PredictionInput.model_validate(payload)


@pytest.mark.parametrize(
    "field", ["udi", "product_id", "machine_failure", "TWF", "HDF", "PWF", "OSF", "RNF"]
)
def test_prediction_input_rejects_identifiers_and_target_labels(field):
    with pytest.raises(ValidationError):
        PredictionInput.model_validate({**VALID_INPUT, field: 1})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "X"),
        ("type", "m"),
        ("type", None),
        ("air_temperature_k", "300"),
        ("air_temperature_k", "hot"),
        ("air_temperature_k", True),
        ("air_temperature_k", 0),
        ("air_temperature_k", float("nan")),
        ("process_temperature_k", -1),
        ("process_temperature_k", float("inf")),
        ("rotational_speed_rpm", "1500"),
        ("rotational_speed_rpm", True),
        ("rotational_speed_rpm", 1500.0),
        ("rotational_speed_rpm", 0),
        ("rotational_speed_rpm", 2**63),
        ("torque_nm", -1),
        ("torque_nm", float("-inf")),
        ("tool_wear_min", -1),
        ("tool_wear_min", 0.5),
        ("tool_wear_min", 2**63),
    ],
)
def test_prediction_input_rejects_invalid_measurements(field, value):
    with pytest.raises(ValidationError):
        PredictionInput.model_validate({**VALID_INPUT, field: value})


def test_training_reads_only_sorted_features_and_target(trained_demo):
    observations = read_training_data(trained_demo["database"])

    assert observations.columns.tolist() == [*EXPECTED_FEATURES, "machine_failure"]
    pd.testing.assert_frame_equal(
        observations,
        trained_demo["observations"][[*EXPECTED_FEATURES, "machine_failure"]],
        check_dtype=False,
    )
    pipeline = trained_demo["pipeline"]
    assert isinstance(pipeline, Pipeline)
    assert pipeline.feature_names_in_.tolist() == EXPECTED_FEATURES


def test_preprocessing_is_fitted_only_on_training_rows(trained_demo):
    scaler = trained_demo["pipeline"]["preprocessor"].named_transformers_["numeric"]
    expected_means = trained_demo["x_train"][NUMERIC_FEATURES].mean().to_numpy()
    full_dataset_means = trained_demo["observations"][NUMERIC_FEATURES].mean().to_numpy()

    np.testing.assert_allclose(scaler.mean_, expected_means)
    assert scaler.n_samples_seen_ == len(trained_demo["x_train"])
    assert not np.allclose(scaler.mean_, full_dataset_means)


def test_saved_metrics_describe_the_actual_held_out_evaluation(trained_demo):
    report = trained_demo["report"]
    saved_report = json.loads(
        (trained_demo["artifacts"] / "metrics.json").read_text(encoding="utf-8")
    )
    assert saved_report == report
    assert report["features"] == EXPECTED_FEATURES
    assert report["source"]["rows"] == 120
    assert report["split"]["train_rows"] == 96
    assert report["split"]["test_rows"] == 24
    assert report["confusion_matrix_labels"] == [0, 1]

    y_test = trained_demo["y_test"]
    predictions = trained_demo["pipeline"].predict(trained_demo["x_test"])
    scores = trained_demo["pipeline"].predict_proba(trained_demo["x_test"])[:, 1]
    metrics = report["metrics"]
    assert metrics["precision"] == pytest.approx(
        precision_score(y_test, predictions, zero_division=0)
    )
    assert metrics["recall"] == pytest.approx(
        recall_score(y_test, predictions, zero_division=0)
    )
    assert metrics["f1"] == pytest.approx(f1_score(y_test, predictions, zero_division=0))
    assert metrics["average_precision"] == pytest.approx(
        average_precision_score(y_test, scores)
    )
    assert metrics["confusion_matrix"] == confusion_matrix(
        y_test, predictions, labels=[0, 1]
    ).tolist()
    assert sum(map(sum, metrics["confusion_matrix"])) == len(y_test)

    for split_name, labels in (
        ("overall", trained_demo["observations"]["machine_failure"]),
        ("train", trained_demo["y_train"]),
        ("test", y_test),
    ):
        assert report["class_counts"][split_name] == {
            "0": int((labels == 0).sum()),
            "1": int((labels == 1).sum()),
        }


def test_predictor_matches_the_saved_full_pipeline(trained_demo):
    measurement = PredictionInput.model_validate(VALID_INPUT)
    predictor = Predictor(trained_demo["artifacts"] / "model.joblib")

    result = predictor.predict(measurement)

    frame = pd.DataFrame([VALID_INPUT], columns=EXPECTED_FEATURES)
    assert type(result["predicted_failure"]) is int
    assert result["predicted_failure"] == int(trained_demo["pipeline"].predict(frame)[0])
    assert type(result["model_score"]) is float
    assert 0 <= result["model_score"] <= 1
    assert result["model_score"] == pytest.approx(
        trained_demo["pipeline"].predict_proba(frame)[0, 1]
    )
    assert result["model_name"] == "LogisticRegression"


def test_training_is_reproducible_for_the_same_source(trained_demo, tmp_path):
    report = train_model(trained_demo["database"], tmp_path)
    pipeline = joblib.load(tmp_path / "model.joblib")

    assert report == trained_demo["report"]
    np.testing.assert_allclose(
        pipeline.predict_proba(trained_demo["x_test"]),
        trained_demo["pipeline"].predict_proba(trained_demo["x_test"]),
        rtol=0,
        atol=1e-12,
    )


@pytest.mark.parametrize(
    "case",
    ["missing", "empty", "single_class", "one_minority_row", "one_class_in_test", "bad_target", "bad_feature"],
)
def test_invalid_training_source_preserves_previous_artifacts(case, tmp_path):
    database_path = tmp_path / "observations.db"
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    old_model = b"previous model sentinel"
    old_report = '{"previous": true}\n'
    (artifacts_dir / "model.joblib").write_bytes(old_model)
    (artifacts_dir / "metrics.json").write_text(old_report, encoding="utf-8")

    if case != "missing":
        observations = synthetic_observations()
        if case == "empty":
            observations = observations.iloc[:0]
        elif case == "single_class":
            observations["machine_failure"] = 0
        elif case == "one_minority_row":
            observations["machine_failure"] = 0
            observations.loc[0, "machine_failure"] = 1
        elif case == "one_class_in_test":
            observations = observations.iloc[:10].copy()
            observations["machine_failure"] = [0] * 8 + [1] * 2
        elif case == "bad_target":
            observations.loc[0, "machine_failure"] = 2
        elif case == "bad_feature":
            observations.loc[0, "torque_nm"] = -1
        write_database(observations, database_path)

    expected_error = FileNotFoundError if case == "missing" else ValueError
    with pytest.raises(expected_error):
        train_model(database_path, artifacts_dir)

    assert (artifacts_dir / "model.joblib").read_bytes() == old_model
    assert (artifacts_dir / "metrics.json").read_text(encoding="utf-8") == old_report
    assert database_path.exists() is (case != "missing")


def test_missing_model_has_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Model not found"):
        Predictor(tmp_path / "model.joblib")
