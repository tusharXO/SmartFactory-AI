"""The six validated operating measurements accepted by the failure classifier."""

from typing import Literal

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
