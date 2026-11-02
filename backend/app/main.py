"""Development entry point for the SmartFactory AI API."""

from fastapi import FastAPI

app = FastAPI(
    title="SmartFactory AI",
    description="API scaffold for the synthetic equipment analytics demo.",
    version="0.1.0",
)
