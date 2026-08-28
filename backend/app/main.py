"""FastAPI application entry point and expected error translation."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.router import router as api_router
from app.core.exceptions import (
    ExternalDataUnavailable,
    HouseholdNotFound,
    LocationNotFound,
    PlanNotFound,
    PlanValidationError,
    ScenarioNotApplicable,
    TestResultNotFound,
    UnsupportedScenario,
)


app = FastAPI(title="FIT5120 API")
app.include_router(api_router, prefix="/api")


@app.exception_handler(HouseholdNotFound)
@app.exception_handler(PlanNotFound)
@app.exception_handler(LocationNotFound)
@app.exception_handler(UnsupportedScenario)
@app.exception_handler(TestResultNotFound)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)}
    )


@app.exception_handler(ScenarioNotApplicable)
async def scenario_not_applicable_handler(
    request: Request, exc: ScenarioNotApplicable
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )


@app.exception_handler(PlanValidationError)
async def plan_validation_handler(
    request: Request, exc: PlanValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": {
                "message": "The household plan is invalid.",
                "errors": exc.errors,
            }
        },
    )


@app.exception_handler(ExternalDataUnavailable)
async def external_data_handler(
    request: Request, exc: ExternalDataUnavailable
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc)},
    )
