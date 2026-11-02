"""Validate the UCI AI4I CSV and refresh the local observations database."""

import argparse
from contextlib import closing
import csv
from io import BytesIO
import json
import math
from pathlib import Path
import sqlite3
from urllib.error import URLError
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = BACKEND_DIR / "data" / "raw" / "ai4i2020.csv"
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "smartfactory.db"
DATASET_URL = (
    "https://archive.ics.uci.edu/static/public/601/"
    "ai4i%2B2020%2Bpredictive%2Bmaintenance%2Bdataset.zip"
)

# Identifiers are stored for display only. Failure-mode labels are not loaded.
COLUMN_MAPPING = {
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
INTEGER_FIELDS = {"udi", "rotational_speed_rpm", "tool_wear_min", "machine_failure"}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS observations (
    udi INTEGER PRIMARY KEY CHECK (udi > 0),
    product_id TEXT NOT NULL CHECK (length(trim(product_id)) > 0),
    type TEXT NOT NULL CHECK (type IN ('L', 'M', 'H')),
    air_temperature_k REAL NOT NULL CHECK (air_temperature_k > 0),
    process_temperature_k REAL NOT NULL CHECK (process_temperature_k > 0),
    rotational_speed_rpm INTEGER NOT NULL CHECK (rotational_speed_rpm > 0),
    torque_nm REAL NOT NULL CHECK (torque_nm >= 0),
    tool_wear_min INTEGER NOT NULL CHECK (tool_wear_min >= 0),
    machine_failure INTEGER NOT NULL CHECK (machine_failure IN (0, 1))
)
"""
INSERT_SQL = """
INSERT INTO observations (
    udi, product_id, type, air_temperature_k, process_temperature_k,
    rotational_speed_rpm, torque_nm, tool_wear_min, machine_failure
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def download_dataset(csv_path: Path = DEFAULT_CSV_PATH) -> Path:
    """Cache the official CSV without overwriting an existing local source."""
    csv_path = Path(csv_path)
    if csv_path.is_file():
        return csv_path

    request = Request(DATASET_URL, headers={"User-Agent": "SmartFactory-AI/0.1"})
    with urlopen(request, timeout=30) as response:
        archive_bytes = response.read()
    with ZipFile(BytesIO(archive_bytes)) as archive:
        if "ai4i2020.csv" not in archive.namelist():
            raise ValueError("The UCI download does not contain ai4i2020.csv.")
        csv_bytes = archive.read("ai4i2020.csv")

    # Read just the expected member, and finish writing before caching the CSV.
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = csv_path.with_suffix(".csv.tmp")
    try:
        temporary_path.write_bytes(csv_bytes)
        temporary_path.replace(csv_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return csv_path


def validate_and_transform(raw: pd.DataFrame) -> pd.DataFrame:
    """Reject invalid input, select the nine stored fields, and normalize types."""
    if not raw.columns.is_unique:
        raise ValueError("CSV column names must be unique.")
    missing_columns = sorted(set(COLUMN_MAPPING) - set(raw.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
    if raw.empty:
        raise ValueError("The CSV must contain at least one observation.")

    clean = raw.loc[:, list(COLUMN_MAPPING)].rename(columns=COLUMN_MAPPING).copy()
    null_columns = clean.columns[clean.isna().any()].tolist()
    if null_columns:
        raise ValueError(f"Missing values in required fields: {', '.join(null_columns)}")

    clean["product_id"] = clean["product_id"].astype("string").str.strip()
    if clean["product_id"].eq("").any():
        raise ValueError("product_id must not be blank.")
    clean["type"] = clean["type"].astype("string").str.strip().str.upper()
    if not clean["type"].isin(["L", "M", "H"]).all():
        raise ValueError("type must be one of L, M, or H.")

    for field in COLUMN_MAPPING.values():
        if field in {"product_id", "type"}:
            continue
        try:
            numeric = pd.to_numeric(clean[field], errors="raise")
        except (ValueError, TypeError) as error:
            raise ValueError(f"{field} must contain numeric values.") from error
        if not numeric.map(math.isfinite).all():
            raise ValueError(f"{field} must contain finite numeric values.")

        if field in INTEGER_FIELDS:
            if (numeric % 1 != 0).any():
                raise ValueError(f"{field} must contain whole integers.")
            integers = numeric.map(int)
            if integers.map(lambda value: value < -(2**63) or value > 2**63 - 1).any():
                raise ValueError(f"{field} must fit within a signed 64-bit integer.")
            clean[field] = integers.astype("int64")
        else:
            clean[field] = numeric.astype("float64")

    for field in ("udi", "air_temperature_k", "process_temperature_k", "rotational_speed_rpm"):
        if (clean[field] <= 0).any():
            raise ValueError(f"{field} must be greater than zero.")
    for field in ("torque_nm", "tool_wear_min"):
        if (clean[field] < 0).any():
            raise ValueError(f"{field} must be nonnegative.")
    if not clean["machine_failure"].isin([0, 1]).all():
        raise ValueError("machine_failure must be 0 or 1.")
    if clean["udi"].duplicated().any():
        raise ValueError("udi must be unique; duplicate observation IDs were found.")

    return clean


def load_observations(observations: pd.DataFrame, db_path: Path) -> None:
    """Replace the demo dataset atomically, preserving old rows on any failure."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Explicit transaction control also covers table creation and full refresh.
    with closing(sqlite3.connect(db_path, autocommit=False)) as connection:
        with connection:
            connection.execute(CREATE_TABLE_SQL)
            connection.execute("DELETE FROM observations")
            connection.executemany(
                INSERT_SQL,
                observations.loc[:, list(COLUMN_MAPPING.values())].itertuples(
                    index=False, name=None
                ),
            )


def run_etl(
    csv_path: Path = DEFAULT_CSV_PATH, db_path: Path = DEFAULT_DB_PATH
) -> dict:
    """Read and validate the complete source before making database changes."""
    csv_path, db_path = Path(csv_path), Path(db_path)
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"CSV not found: {csv_path}. Run scripts/etl.py --download or pass --csv PATH."
        )
    # Pandas renames duplicate CSV headers, so check the original header first.
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        header = next(csv.reader(source), [])
    if len(header) != len(set(header)):
        raise ValueError("CSV column names must be unique.")
    raw = pd.read_csv(csv_path)
    observations = validate_and_transform(raw)
    load_observations(observations, db_path)

    # Report persisted SQL results rather than hardcoded dataset totals.
    with closing(sqlite3.connect(db_path)) as connection:
        total = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        counts = dict(
            connection.execute(
                "SELECT machine_failure, COUNT(*) FROM observations GROUP BY machine_failure"
            ).fetchall()
        )
        type_counts = dict(
            connection.execute(
                "SELECT type, COUNT(*) FROM observations GROUP BY type ORDER BY type"
            ).fetchall()
        )
    failures = counts.get(1, 0)
    return {
        "csv_path": str(csv_path.resolve()),
        "database_path": str(db_path.resolve()),
        "source_rows": len(raw),
        "source_columns": len(raw.columns),
        "total_observations": total,
        "class_counts": {"0": counts.get(0, 0), "1": failures},
        "failure_rate": failures / total,
        "type_counts": type_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH, help="Source CSV path")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Output SQLite path")
    parser.add_argument(
        "--download", action="store_true", help="Download the official CSV if not cached"
    )
    args = parser.parse_args()
    try:
        if args.download:
            download_dataset(args.csv)
        summary = run_etl(args.csv, args.db)
    except (OSError, URLError, ValueError, BadZipFile, sqlite3.Error) as error:
        parser.exit(1, f"ETL failed: {error}\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
