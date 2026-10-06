"""Historical Fire Danger Rating machine-learning endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.schemas.fdr_prediction import FdrPredictionResponse
from app.services.fdr_prediction import (
    FdrPredictionService,
    VALID_DISTRICTS,
)


router = APIRouter(
    prefix="/fdr",
    tags=["fdr"],
)


@router.get(
    "/prediction",
    response_model=FdrPredictionResponse,
)
def predict_fdr_pattern(
    district: Annotated[
        str,
        Query(
            min_length=1,
            max_length=100,
            description="Victorian fire weather district.",
        ),
    ],
    target_date: Annotated[
        date,
        Query(
            alias="date",
            description="Date to evaluate.",
        ),
    ],
) -> FdrPredictionResponse:
    """
    Return a historical-pattern FDR classification.

    This endpoint does not provide an official forecast.
    """
    district = district.strip()

    if district not in VALID_DISTRICTS:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported fire district.",
                "valid_districts": sorted(VALID_DISTRICTS),
            },
        )

    try:
        return FdrPredictionService().predict(
            district=district,
            target_date=target_date,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc