"""FastAPI application with local data access and startup model loading."""

from contextlib import asynccontextmanager
import logging
import math
from pathlib import Path

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db import DEFAULT_DB_PATH
from app.predictor import DEFAULT_MODEL_PATH, Predictor
from app.routes import router
from app.schemas import FEATURE_COLUMNS, ModelMetricsResponse


DEFAULT_METRICS_PATH = DEFAULT_MODEL_PATH.parent / "metrics.json"
logger = logging.getLogger(__name__)


def create_app(
    db_path: Path = DEFAULT_DB_PATH,
    model_path: Path = DEFAULT_MODEL_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> FastAPI:
    """Allow isolated data paths in tests while retaining simple local defaults."""

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        # A missing artifact leaves health and dataset analytics available.
        try:
            application.state.predictor = Predictor(model_path)
        except Exception as error:
            logger.warning("Saved model unavailable; run python -m scripts.train: %s", error)

        try:
            report = ModelMetricsResponse.model_validate_json(
                Path(metrics_path).read_text(encoding="utf-8")
            )
            if (
                report.features != FEATURE_COLUMNS
                or report.target != "machine_failure"
                or report.confusion_matrix_labels != [0, 1]
            ):
                raise ValueError("The metrics report must describe the approved binary classifier.")
            predictor = application.state.predictor
            if predictor is not None and report.model_name != predictor.model_name:
                raise ValueError("The metrics report and saved model must describe the same classifier.")
            application.state.model_metrics = report
        except (OSError, ValueError) as error:
            logger.warning("Evaluation report unavailable; run python -m scripts.train: %s", error)

        yield
        application.state.predictor = None
        application.state.model_metrics = None

    application = FastAPI(
        title="SmartFactory AI",
        description="Analytics and snapshot classification for synthetic equipment observations.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.db_path = Path(db_path)
    application.state.predictor = None
    application.state.model_metrics = None

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_request, error: RequestValidationError):
        # JSON numbers such as 1e309 can overflow to inf. Keep their validation
        # details serializable instead of turning an input error into HTTP 500.
        details = jsonable_encoder(
            error.errors(),
            custom_encoder={float: lambda value: value if math.isfinite(value) else str(value)},
        )
        return JSONResponse(status_code=422, content={"detail": details})

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    application.include_router(router)
    return application


app = create_app()
