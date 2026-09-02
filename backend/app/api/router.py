"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.locations import router as locations_router
from app.api.routes.households import router as households_router
from app.api.routes.scenarios import router as scenarios_router


router = APIRouter()
router.include_router(health_router)
router.include_router(locations_router, prefix="/v1")
router.include_router(households_router, prefix="/v1")
router.include_router(scenarios_router, prefix="/v1")
