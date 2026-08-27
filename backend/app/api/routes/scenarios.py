"""Basic scenario library endpoint."""

from fastapi import APIRouter

from app.schemas.scenarios import BasicScenario
from app.services.scenarios import BasicScenarioService


router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("/basic", response_model=list[BasicScenario])
def list_basic_scenarios() -> list[BasicScenario]:
    return BasicScenarioService().list_scenarios()

