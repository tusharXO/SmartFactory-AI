"""The six local MVP endpoints, with explicit unavailable-resource errors."""

import sqlite3
from typing import Annotated, Callable, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from app.db import get_charts, get_observations, get_overview
from app.schemas import (
    ChartsResponse,
    HealthResponse,
    INT64_MAX,
    ModelMetricsResponse,
    ObservationsResponse,
    OverviewResponse,
    PredictionInput,
    PredictionResponse,
)


router = APIRouter(prefix="/api")


def query_dataset(request: Request, query: Callable, **parameters) -> dict:
    try:
        return query(request.app.state.db_path, **parameters)
    except (OSError, sqlite3.Error) as error:
        raise HTTPException(
            status_code=503,
            detail="Dataset unavailable. Run python scripts/etl.py --download from backend.",
        ) from error


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> dict:
    try:
        get_overview(request.app.state.db_path)
        database_ready = True
    except (OSError, sqlite3.Error):
        database_ready = False
    model_ready = request.app.state.predictor is not None
    metrics_ready = request.app.state.model_metrics is not None
    return {
        "status": "ok" if database_ready and model_ready and metrics_ready else "degraded",
        "database_ready": database_ready,
        "model_ready": model_ready,
        "metrics_ready": metrics_ready,
    }


@router.get("/overview", response_model=OverviewResponse)
def overview(request: Request) -> dict:
    return query_dataset(request, get_overview)


@router.get("/charts", response_model=ChartsResponse)
def charts(request: Request) -> dict:
    return query_dataset(request, get_charts)


@router.get("/observations", response_model=ObservationsResponse)
def observations(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=INT64_MAX)] = 0,
    product_type: Annotated[Literal["L", "M", "H"] | None, Query(alias="type")] = None,
    failure: Annotated[int | None, Query(ge=0, le=1)] = None,
) -> dict:
    return query_dataset(
        request,
        get_observations,
        limit=limit,
        offset=offset,
        type_filter=product_type,
        failure=failure,
    )


@router.get("/model-metrics", response_model=ModelMetricsResponse)
def model_metrics(request: Request) -> ModelMetricsResponse:
    report = request.app.state.model_metrics
    if report is None:
        raise HTTPException(
            status_code=503,
            detail="Evaluation report unavailable. Run python -m scripts.train and restart the API.",
        )
    return report


@router.post("/predict", response_model=PredictionResponse)
def predict(request: Request, measurement: PredictionInput) -> dict:
    predictor = request.app.state.predictor
    if predictor is None:
        raise HTTPException(
            status_code=503,
            detail="Model unavailable. Run python -m scripts.train and restart the API.",
        )
    return predictor.predict(measurement)
