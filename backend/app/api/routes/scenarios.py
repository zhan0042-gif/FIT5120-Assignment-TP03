"""Household-specific basic scenario library endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_household_repository
from app.repositories.households import HouseholdRepository
from app.schemas.scenarios import BasicScenario
from app.services.scenarios import BasicScenarioService


router = APIRouter(prefix="/scenarios", tags=["scenarios"])
RepositoryDependency = Annotated[HouseholdRepository, Depends(get_household_repository)]


@router.get("/basic", response_model=list[BasicScenario])
def list_basic_scenarios(
    household_id: str, repository: RepositoryDependency
) -> list[BasicScenario]:
    return BasicScenarioService(repository).list_for_household(household_id)
