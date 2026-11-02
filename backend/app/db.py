"""Read-only SQL queries for equipment analytics and observation browsing."""

from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "smartfactory.db"
OBSERVATION_COLUMNS = (
    "udi, product_id, type, air_temperature_k, process_temperature_k, "
    "rotational_speed_rpm, torque_nm, tool_wear_min, machine_failure"
)


@contextmanager
def _connection(db_path: Path):
    """Open one read-only connection and close it after a consistent snapshot."""
    db_path = Path(db_path).resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}. Run the ETL script first.")
    with closing(
        sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, autocommit=False)
    ) as connection:
        connection.row_factory = sqlite3.Row
        yield connection


def get_overview(db_path: Path = DEFAULT_DB_PATH) -> dict:
    with _connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total_observations,
                   COALESCE(SUM(machine_failure), 0) AS failure_count,
                   COUNT(DISTINCT type) AS type_count
            FROM observations
            """
        ).fetchone()
    total = row["total_observations"]
    return {
        "total_observations": total,
        "failure_count": row["failure_count"],
        "failure_rate": row["failure_count"] / total if total else 0.0,
        "type_count": row["type_count"],
    }


def get_charts(db_path: Path = DEFAULT_DB_PATH) -> dict:
    with _connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT type, COUNT(*) AS total_observations,
                   SUM(machine_failure) AS failure_count
            FROM observations
            GROUP BY type
            ORDER BY type
            """
        ).fetchall()
    return {
        "type_distribution": [
            {"type": row["type"], "count": row["total_observations"]}
            for row in rows
        ],
        "failure_rates_by_type": [
            {
                "type": row["type"],
                "total_observations": row["total_observations"],
                "failure_count": row["failure_count"],
                "failure_rate": row["failure_count"] / row["total_observations"],
            }
            for row in rows
        ],
    }


def get_observations(
    db_path: Path = DEFAULT_DB_PATH,
    limit: int = 20,
    offset: int = 0,
    type_filter: str | None = None,
    failure: int | None = None,
) -> dict:
    filters, parameters = [], []
    if type_filter is not None:
        filters.append("type = ?")
        parameters.append(type_filter)
    if failure is not None:
        filters.append("machine_failure = ?")
        parameters.append(failure)
    where = " WHERE " + " AND ".join(filters) if filters else ""

    with _connection(db_path) as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM observations" + where, parameters
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT {OBSERVATION_COLUMNS} FROM observations{where} "
            "ORDER BY udi LIMIT ? OFFSET ?",
            [*parameters, limit, offset],
        ).fetchall()
    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
