"""Load the saved preprocessing pipeline and classify validated measurements."""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline

from app.schemas import FEATURE_COLUMNS, PredictionInput


DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "model.joblib"


class Predictor:
    """Keep one fitted pipeline in memory for repeated inference calls."""

    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH):
        model_path = Path(model_path)
        if not model_path.is_file():
            raise FileNotFoundError(
                f"Model not found: {model_path}. Run python -m scripts.train first."
            )
        pipeline = joblib.load(model_path)
        if not isinstance(pipeline, Pipeline):
            raise ValueError("The model artifact must contain a fitted sklearn Pipeline.")
        if list(getattr(pipeline, "feature_names_in_", [])) != FEATURE_COLUMNS:
            raise ValueError("The model artifact must use the six approved input features.")
        if list(getattr(pipeline, "classes_", [])) != [0, 1] or not hasattr(
            pipeline, "predict_proba"
        ):
            raise ValueError("The model artifact must support binary failure classification.")
        self.pipeline = pipeline
        self.model_name = type(pipeline.steps[-1][1]).__name__

    def predict(self, measurement: PredictionInput) -> dict:
        """Return a class and model score, not a calibrated real-world probability."""
        features = pd.DataFrame([measurement.model_dump()], columns=FEATURE_COLUMNS)
        return {
            "predicted_failure": int(self.pipeline.predict(features)[0]),
            "model_score": float(self.pipeline.predict_proba(features)[0, 1]),
            "model_name": self.model_name,
        }
