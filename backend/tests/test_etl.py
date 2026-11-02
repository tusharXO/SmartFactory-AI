"""Exercise ETL with invented rows; tests never download or modify the UCI data."""

import re
import sqlite3
from contextlib import closing

import pandas as pd
import pytest

from scripts.etl import load_observations, run_etl, validate_and_transform


EXPECTED_MAPPING = {
    "UDI": "udi",
    "Product ID": "product_id",
    "Type": "type",
    "Air temperature [K]": "air_temperature_k",
    "Process temperature [K]": "process_temperature_k",
    "Rotational speed [rpm]": "rotational_speed_rpm",
    "Torque [Nm]": "torque_nm",
    "Tool wear [min]": "tool_wear_min",
    "Machine failure": "machine_failure",
}


@pytest.fixture
def raw_rows():
    rows = pd.DataFrame(
        [
            [1, " M1001 ", " m ", "300.1", 310.2, "1500", 40.5, "0", "0"],
            [2, "L1002", "L", 301.2, 311.3, 1400, 55.0, 100, 1],
            [3, "H1003", "H", 302.0, 312.0, 1700, 30.0, 200, 0],
        ],
        columns=list(EXPECTED_MAPPING),
        dtype=object,
    )
    for column in ("TWF", "HDF", "PWF", "OSF", "RNF"):
        rows[column] = 0
    return rows


def field_pattern(column):
    return rf"{re.escape(column)}|{re.escape(EXPECTED_MAPPING[column])}"


def database_rows(database_path):
    with closing(sqlite3.connect(database_path)) as connection:
        return connection.execute(
            "SELECT * FROM observations ORDER BY udi"
        ).fetchall()


def test_transform_cleans_values_and_keeps_only_observation_columns(raw_rows):
    # Failure-mode labels are deliberately ignored, even if unused cells are null.
    raw_rows.loc[0, "TWF"] = None
    original = raw_rows.copy(deep=True)

    observations = validate_and_transform(raw_rows)

    assert observations.columns.tolist() == list(EXPECTED_MAPPING.values())
    assert observations.iloc[0].to_dict() == {
        "udi": 1,
        "product_id": "M1001",
        "type": "M",
        "air_temperature_k": 300.1,
        "process_temperature_k": 310.2,
        "rotational_speed_rpm": 1500,
        "torque_nm": 40.5,
        "tool_wear_min": 0,
        "machine_failure": 0,
    }
    assert observations["machine_failure"].tolist() == [0, 1, 0]
    pd.testing.assert_frame_equal(raw_rows, original)


def test_product_identifiers_are_display_values_not_unique_machine_ids(raw_rows):
    raw_rows.loc[0, "Product ID"] = " shared-product "
    raw_rows.loc[1, "Product ID"] = "shared-product"

    observations = validate_and_transform(raw_rows)

    assert observations["product_id"].tolist()[:2] == [
        "shared-product", "shared-product"
    ]
    assert len(observations) == 3


@pytest.mark.parametrize("column", list(EXPECTED_MAPPING))
def test_missing_required_column_is_rejected(raw_rows, column):
    with pytest.raises(ValueError, match=field_pattern(column)):
        validate_and_transform(raw_rows.drop(columns=column))


@pytest.mark.parametrize("column", list(EXPECTED_MAPPING))
def test_null_required_value_is_rejected(raw_rows, column):
    raw_rows.loc[0, column] = None

    with pytest.raises(ValueError, match=field_pattern(column)):
        validate_and_transform(raw_rows)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("UDI", 0),
        ("UDI", -1),
        ("UDI", 1.5),
        ("UDI", str(2**63)),
        ("UDI", "not-a-number"),
        ("Product ID", " \t "),
        ("Type", "X"),
        ("Type", " "),
        ("Air temperature [K]", 0),
        ("Air temperature [K]", -300),
        ("Air temperature [K]", " "),
        ("Air temperature [K]", "hot"),
        ("Air temperature [K]", float("inf")),
        ("Process temperature [K]", 0),
        ("Process temperature [K]", float("-inf")),
        ("Rotational speed [rpm]", 0),
        ("Rotational speed [rpm]", -1500),
        ("Rotational speed [rpm]", 1500.5),
        ("Torque [Nm]", -1),
        ("Torque [Nm]", float("inf")),
        ("Tool wear [min]", -1),
        ("Tool wear [min]", 0.5),
        ("Machine failure", -1),
        ("Machine failure", 2),
        ("Machine failure", 0.5),
    ],
)
def test_invalid_values_are_rejected_without_dropping_rows(raw_rows, column, value):
    raw_rows.loc[0, column] = value

    with pytest.raises(ValueError, match=field_pattern(column)):
        validate_and_transform(raw_rows)


def test_duplicate_ids_are_rejected_after_numeric_conversion(raw_rows):
    raw_rows.loc[1, "UDI"] = "1"

    with pytest.raises(ValueError, match=r"UDI|udi"):
        validate_and_transform(raw_rows)


def test_empty_dataset_is_rejected(raw_rows):
    with pytest.raises(ValueError):
        validate_and_transform(raw_rows.iloc[:0])


def test_duplicate_csv_header_is_rejected_before_database_creation(tmp_path):
    csv_path = tmp_path / "duplicate_headers.csv"
    database_path = tmp_path / "observations.db"
    csv_path.write_text(
        ",".join(["UDI", *EXPECTED_MAPPING])
        + "\n999,1,M1001,M,300,310,1500,40,0,0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"(?i)column|unique"):
        run_etl(csv_path, database_path)

    assert not database_path.exists()


def test_csv_load_reports_sql_counts_and_is_idempotent(raw_rows, tmp_path):
    csv_path = tmp_path / "observations.csv"
    database_path = tmp_path / "data" / "observations.db"
    raw_rows.to_csv(csv_path, index=False)

    report = run_etl(csv_path, database_path)
    first_rows = database_rows(database_path)
    run_etl(csv_path, database_path)

    assert len(first_rows) == 3
    assert first_rows[0] == (1, "M1001", "M", 300.1, 310.2, 1500, 40.5, 0, 0)
    assert database_rows(database_path) == first_rows
    assert report["source_rows"] == 3
    assert report["source_columns"] == 14
    assert report["total_observations"] == 3
    assert report["class_counts"] == {"0": 2, "1": 1}
    assert report["type_counts"] == {"H": 1, "L": 1, "M": 1}
    assert report["failure_rate"] == pytest.approx(1 / 3)


def test_rerun_reflects_changed_source_and_removes_stale_rows(raw_rows, tmp_path):
    csv_path = tmp_path / "observations.csv"
    database_path = tmp_path / "observations.db"
    raw_rows.to_csv(csv_path, index=False)
    run_etl(csv_path, database_path)

    changed_rows = raw_rows.iloc[:2].copy()
    changed_rows.loc[0, "Torque [Nm]"] = 99.5
    changed_rows.to_csv(csv_path, index=False)
    report = run_etl(csv_path, database_path)

    rows = database_rows(database_path)
    assert [(row[0], row[6]) for row in rows] == [(1, 99.5), (2, 55.0)]
    assert report["total_observations"] == 2


def test_invalid_csv_preserves_existing_database(raw_rows, tmp_path):
    csv_path = tmp_path / "observations.csv"
    database_path = tmp_path / "observations.db"
    raw_rows.to_csv(csv_path, index=False)
    run_etl(csv_path, database_path)
    saved_rows = database_rows(database_path)

    raw_rows.loc[0, "Type"] = "invalid"
    raw_rows.to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match=r"Type|type"):
        run_etl(csv_path, database_path)

    assert database_rows(database_path) == saved_rows


def test_load_failure_rolls_back_entire_refresh(raw_rows, tmp_path):
    database_path = tmp_path / "observations.db"
    observations = validate_and_transform(raw_rows)
    load_observations(observations, database_path)
    saved_rows = database_rows(database_path)

    # Bypass raw validation to provoke a real SQLite CHECK constraint failure.
    invalid_rows = observations.copy()
    invalid_rows.loc[1, "machine_failure"] = 2
    with pytest.raises(sqlite3.IntegrityError):
        load_observations(invalid_rows, database_path)

    assert database_rows(database_path) == saved_rows
