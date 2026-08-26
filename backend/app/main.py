"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.router import router as api_router


app = FastAPI(title="FIT5120 API")
app.include_router(api_router, prefix="/api")
