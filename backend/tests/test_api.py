"""Exercise the API with temporary synthetic observations and a real baseline."""

from contextlib import closing
import json
import sqlite3
from unittest.mock import patch

from fastapi.testclient import TestClient
import joblib
import pandas as pd
import pytest

import app.main as app_module
from app.main import create_app
from app.predictor import Predictor
from app.schemas import FEATURE_COLUMNS
from scripts.train import train_model


VALID_INPUT = {
    "type": "M",
    "air_temperature_k": 300.0,
    "process_temperature_k": 310.0,
    "rotational_speed_rpm": 1500,
    "torque_nm": 40.0,
    "tool_wear_min": 100,
}
OBSERVATION_COLUMNS = {
    "udi", "product_id", "type", "air_temperature_k", "process_temperature_k",
    "rotational_speed_rpm", "torque_nm", "tool_wear_min", "machine_failure",
}


@pytest.fixture(scope="module")
def resources(tmp_path_factory):
    directory = tmp_path_factory.mktemp("api_resources")
    database_path = directory / "observations.db"
    artifacts_dir = directory / "artifacts"
    rows = pd.DataFrame(
        [
            {
                "udi": index + 1,
                "product_id": f"test-product-{index}",
                "type": ["L", "M", "H"][index % 3],
                "air_temperature_k": 295.0 + index * 0.15,
                "process_temperature_k": 305.0 + index * 0.08,
                "rotational_speed_rpm": 1200 + (index * 37) % 900,
                "torque_nm": float(15 + (index * 11) % 70),
                "tool_wear_min": (index * 7) % 241,
                "machine_failure": int(index % 7 == 0),
            }
            for index in range(120)
        ]
    )
    with closing(sqlite3.connect(database_path)) as connection:
        rows.iloc[::-1].to_sql("observations", connection, index=False)
    report = train_model(database_path, artifacts_dir)
    return {
        "db_path": database_path,
        "model_path": artifacts_dir / "model.joblib",
        "metrics_path": artifacts_dir / "metrics.json",
        "rows": rows,
        "report": report,
        "pipeline": joblib.load(artifacts_dir / "model.joblib"),
    }


def configured_app(resources, **overrides):
    paths = {
        key: resources[key] for key in ("db_path", "model_path", "metrics_path")
    }
    return create_app(**{**paths, **overrides})


@pytest.fixture
def client(resources):
    with TestClient(configured_app(resources)) as api_client:
        yield api_client


def test_health_reports_ready_resources(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database_ready": True,
        "model_ready": True,
        "metrics_ready": True,
    }


def test_overview_uses_database_observations(client, resources):
    response = client.get("/api/overview")

    assert response.status_code == 200
    assert response.json() == {
        "total_observations": len(resources["rows"]),
        "failure_count": 18,
        "failure_rate": pytest.approx(18 / 120),
        "type_count": 3,
    }


def test_charts_use_per_type_counts_and_fractional_failure_rates(client, resources):
    response = client.get("/api/charts")

    assert response.status_code == 200
    body = response.json()
    assert {row["type"]: row["count"] for row in body["type_distribution"]} == {
        "L": 40, "M": 40, "H": 40
    }
    actual_rates = {row["type"]: row for row in body["failure_rates_by_type"]}
    for quality_type, group in resources["rows"].groupby("type"):
        failures = int(group["machine_failure"].sum())
        assert actual_rates[quality_type] == {
            "type": quality_type,
            "total_observations": len(group),
            "failure_count": failures,
            "failure_rate": pytest.approx(failures / len(group)),
        }


def test_observations_default_page_has_all_fields_and_stable_order(client):
    response = client.get("/api/observations")

    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["limit"], body["offset"]) == (120, 20, 0)
    assert [row["udi"] for row in body["items"]] == list(range(1, 21))
    assert set(body["items"][0]) == OBSERVATION_COLUMNS
    assert body["items"][0]["product_id"] == "test-product-0"
    assert body["items"][0]["machine_failure"] == 1


@pytest.mark.parametrize("filters", [{"type": "L"}, {"failure": 1}, {"type": "M", "failure": 0}])
def test_observation_filters_and_pagination_share_the_same_filtered_total(client, resources, filters):
    expected = resources["rows"]
    if "type" in filters:
        expected = expected[expected["type"] == filters["type"]]
    if "failure" in filters:
        expected = expected[expected["machine_failure"] == filters["failure"]]

    response = client.get("/api/observations", params={**filters, "limit": 7, "offset": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(expected)
    assert (body["limit"], body["offset"]) == (7, 3)
    assert [row["udi"] for row in body["items"]] == expected.iloc[3:10]["udi"].tolist()


def test_observation_offset_past_the_end_returns_an_empty_page(client):
    response = client.get("/api/observations", params={"limit": 5, "offset": 120})

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 120, "limit": 5, "offset": 120}


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0}, {"limit": -1}, {"limit": 101}, {"limit": "many"},
        {"offset": -1}, {"offset": 2**63}, {"offset": "1.5"},
        {"type": "X"}, {"type": "l"}, {"type": "L' OR 1=1 --"},
        {"failure": -1}, {"failure": 2}, {"failure": "true"},
    ],
)
def test_invalid_observation_filters_return_validation_errors(client, params):
    response = client.get("/api/observations", params=params)

    assert response.status_code == 422
    assert response.json()["detail"]


def test_model_metrics_returns_the_saved_evaluation_report(client, resources):
    response = client.get("/api/model-metrics")

    assert response.status_code == 200
    assert response.json() == resources["report"]


def test_prediction_uses_the_real_saved_pipeline(client, resources):
    response = client.post("/api/predict", json=VALID_INPUT)

    assert response.status_code == 200
    body = response.json()
    frame = pd.DataFrame([VALID_INPUT], columns=FEATURE_COLUMNS)
    assert type(body["predicted_failure"]) is int
    assert body["predicted_failure"] == int(resources["pipeline"].predict(frame)[0])
    assert body["model_score"] == pytest.approx(resources["pipeline"].predict_proba(frame)[0, 1])
    assert body["model_name"] == "LogisticRegression"


@pytest.mark.parametrize(
    "payload",
    [
        {key: value for key, value in VALID_INPUT.items() if key != "torque_nm"},
        {**VALID_INPUT, "type": "X"},
        {**VALID_INPUT, "rotational_speed_rpm": 1500.5},
        {**VALID_INPUT, "torque_nm": "40"},
        {**VALID_INPUT, "tool_wear_min": -1},
        {**VALID_INPUT, "machine_failure": 1},
    ],
)
def test_invalid_predictions_return_helpful_validation_errors(client, payload):
    response = client.post("/api/predict", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]


def test_numeric_overflow_in_json_returns_422_instead_of_server_error(client):
    payload = json.dumps(VALID_INPUT).replace('"air_temperature_k": 300.0', '"air_temperature_k": 1e309')

    response = client.post("/api/predict", content=payload, headers={"Content-Type": "application/json"})

    assert response.status_code == 422
    assert response.json()["detail"]


@pytest.mark.parametrize("case", ["missing", "invalid_file", "missing_table"])
def test_unavailable_database_returns_503_without_creating_a_phantom_database(resources, tmp_path, case):
    database_path = tmp_path / "unavailable.db"
    if case == "invalid_file":
        database_path.write_bytes(b"not a SQLite database")
    elif case == "missing_table":
        sqlite3.connect(database_path).close()

    with TestClient(configured_app(resources, db_path=database_path)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "degraded"
        assert health.json()["database_ready"] is False
        for endpoint in ("overview", "charts", "observations"):
            response = client.get(f"/api/{endpoint}")
            assert response.status_code == 503
            assert response.json()["detail"]
        assert client.post("/api/predict", json=VALID_INPUT).status_code == 200

    assert database_path.exists() is (case != "missing")


def test_empty_database_has_zero_counts_and_empty_collections(resources, tmp_path):
    database_path = tmp_path / "empty.db"
    with closing(sqlite3.connect(database_path)) as connection:
        resources["rows"].iloc[:0].to_sql("observations", connection, index=False)

    with TestClient(configured_app(resources, db_path=database_path)) as client:
        assert client.get("/api/health").json()["database_ready"] is True
        overview = client.get("/api/overview")
        assert overview.status_code == 200
        assert overview.json() == {
            "total_observations": 0, "failure_count": 0, "failure_rate": 0.0, "type_count": 0
        }
        charts = client.get("/api/charts")
        assert charts.status_code == 200
        assert charts.json() == {"type_distribution": [], "failure_rates_by_type": []}
        observations = client.get("/api/observations")
        assert observations.status_code == 200
        assert observations.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_missing_model_degrades_prediction_but_keeps_analytics_available(resources, tmp_path):
    model_path = tmp_path / "missing.joblib"

    with TestClient(configured_app(resources, model_path=model_path)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["model_ready"] is False
        assert health.json()["status"] == "degraded"
        response = client.post("/api/predict", json=VALID_INPUT)
        assert response.status_code == 503
        assert response.json()["detail"]
        assert client.get("/api/overview").status_code == 200

    assert not model_path.exists()


@pytest.mark.parametrize("case", ["missing", "invalid_json", "invalid_schema"])
def test_unavailable_metrics_return_503_without_blocking_prediction(resources, tmp_path, case):
    metrics_path = tmp_path / "metrics.json"
    if case == "invalid_json":
        metrics_path.write_text("not JSON", encoding="utf-8")
    elif case == "invalid_schema":
        metrics_path.write_text("{}", encoding="utf-8")

    with TestClient(configured_app(resources, metrics_path=metrics_path)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["metrics_ready"] is False
        assert health.json()["status"] == "degraded"
        response = client.get("/api/model-metrics")
        assert response.status_code == 503
        assert response.json()["detail"]
        assert client.post("/api/predict", json=VALID_INPUT).status_code == 200

    assert metrics_path.exists() is (case != "missing")


def test_model_and_metrics_are_loaded_once_at_startup(resources, tmp_path):
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_bytes(resources["metrics_path"].read_bytes())

    with patch.object(app_module, "Predictor", wraps=Predictor) as predictor_constructor:
        with TestClient(configured_app(resources, metrics_path=metrics_path)) as client:
            first = client.post("/api/predict", json=VALID_INPUT)
            second = client.post("/api/predict", json=VALID_INPUT)
            assert first.status_code == second.status_code == 200
            assert first.json() == second.json()
            assert client.get("/api/model-metrics").json() == resources["report"]
            metrics_path.write_text("invalid after startup", encoding="utf-8")
            assert client.get("/api/model-metrics").json() == resources["report"]
        assert predictor_constructor.call_count == 1


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_cors_allows_the_local_frontend_to_submit_predictions(client, origin):
    response = client.options(
        "/api/predict",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_cors_does_not_allow_an_unconfigured_origin(client):
    response = client.options(
        "/api/predict",
        headers={"Origin": "https://unconfigured.example", "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
