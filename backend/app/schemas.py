"""The six validated operating measurements accepted by the failure classifier."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


NUMERIC_FEATURES = [
    "air_temperature_k",
    "process_temperature_k",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_min",
]
CATEGORICAL_FEATURES = ["type"]
FEATURE_COLUMNS = [*CATEGORICAL_FEATURES, *NUMERIC_FEATURES]
INT64_MAX = 2**63 - 1


class PredictionInput(BaseModel):
    """A measurement snapshot; identifiers and target labels are forbidden."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    type: Literal["L", "M", "H"]
    air_temperature_k: float = Field(gt=0)
    process_temperature_k: float = Field(gt=0)
    rotational_speed_rpm: StrictInt = Field(gt=0, le=INT64_MAX)
    torque_nm: float = Field(ge=0)
    tool_wear_min: StrictInt = Field(ge=0, le=INT64_MAX)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database_ready: bool
    model_ready: bool
    metrics_ready: bool


class OverviewResponse(BaseModel):
    total_observations: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    failure_rate: float = Field(ge=0, le=1)
    type_count: int = Field(ge=0)


class TypeCount(BaseModel):
    type: Literal["L", "M", "H"]
    count: int = Field(ge=0)


class TypeFailureRate(BaseModel):
    type: Literal["L", "M", "H"]
    total_observations: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    failure_rate: float = Field(ge=0, le=1)


class ChartsResponse(BaseModel):
    type_distribution: list[TypeCount]
    failure_rates_by_type: list[TypeFailureRate]


class ObservationResponse(PredictionInput):
    udi: StrictInt = Field(gt=0, le=INT64_MAX)
    product_id: str = Field(min_length=1)
    machine_failure: Literal[0, 1]


class ObservationsResponse(BaseModel):
    items: list[ObservationResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0, le=INT64_MAX)


class PredictionResponse(BaseModel):
    predicted_failure: Literal[0, 1]
    model_score: float = Field(ge=0, le=1)
    model_name: str


class EvaluationMetrics(BaseModel):
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1: float = Field(ge=0, le=1)
    average_precision: float = Field(ge=0, le=1)
    confusion_matrix: list[list[int]]


class ModelMetricsResponse(BaseModel):
    model_name: str
    features: list[str]
    target: str
    source: dict[str, Any]
    split: dict[str, Any]
    class_counts: dict[str, dict[str, int]]
    metrics: EvaluationMetrics
    confusion_matrix_labels: list[int]
    decision_threshold: float = Field(ge=0, le=1)
    model_parameters: dict[str, Any]
    library_versions: dict[str, str]
    score_note: str
