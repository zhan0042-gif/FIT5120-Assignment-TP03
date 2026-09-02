"""Persistence boundary and in-memory Iteration 1 implementation."""

from copy import deepcopy
from typing import Protocol
from uuid import uuid4

from app.core.exceptions import (
    HouseholdNotFound,
    LocationNotFound,
    PlanNotFound,
    TestResultNotFound,
)
from app.schemas.households import HouseholdLocation, HouseholdLocationContext, HouseholdPlan
from app.schemas.scenarios import ScenarioTestResult


class HouseholdRepository(Protocol):
    """Persistence boundary used by services without exposing SQL details."""

    def create_household(self, display_name: str | None = None) -> str: ...

    def household_exists(self, household_id: str) -> bool: ...

    def save_plan(self, household_id: str, plan: HouseholdPlan) -> None: ...

    def get_plan(self, household_id: str) -> HouseholdPlan: ...

    def save_location(self, household_id: str, location: HouseholdLocation) -> None: ...

    def get_location(self, household_id: str) -> HouseholdLocation: ...

    def save_location_context(
        self, household_id: str, context: HouseholdLocationContext
    ) -> None: ...

    def get_location_context(self, household_id: str) -> HouseholdLocationContext | None: ...

    def save_test_result(self, household_id: str, result: ScenarioTestResult) -> None: ...

    def get_test_results(self, household_id: str) -> list[ScenarioTestResult]: ...

    def get_test_result(
        self, household_id: str, test_run_id: str
    ) -> ScenarioTestResult: ...


class InMemoryHouseholdRepository:
    """Process-local repository used by isolated service and API tests."""

    def __init__(self) -> None:
        self._households: dict[str, dict[str, object]] = {}

    def create_household(self, display_name: str | None = None) -> str:
        household_id = f"hh_{uuid4().hex}"
        self._households[household_id] = {
            "display_name": display_name,
            "plan": None,
            "location": None,
            "location_context": None,
            "test_results": [],
        }
        return household_id

    def household_exists(self, household_id: str) -> bool:
        return household_id in self._households

    def _household(self, household_id: str) -> dict[str, object]:
        try:
            return self._households[household_id]
        except KeyError as exc:
            raise HouseholdNotFound(f"Household '{household_id}' was not found.") from exc

    def save_plan(self, household_id: str, plan: HouseholdPlan) -> None:
        self._household(household_id)["plan"] = plan.model_copy(deep=True)

    def get_plan(self, household_id: str) -> HouseholdPlan:
        plan = self._household(household_id)["plan"]
        if plan is None:
            raise PlanNotFound(f"Household '{household_id}' does not have a plan.")
        return plan.model_copy(deep=True)  # type: ignore[union-attr]

    def save_location(self, household_id: str, location: HouseholdLocation) -> None:
        """Replace the location and invalidate context derived from old coordinates."""
        household = self._household(household_id)
        household["location"] = location.model_copy(deep=True)
        household["location_context"] = None

    def get_location(self, household_id: str) -> HouseholdLocation:
        location = self._household(household_id)["location"]
        if location is None:
            raise LocationNotFound(f"Household '{household_id}' does not have a location.")
        return location.model_copy(deep=True)  # type: ignore[union-attr]

    def save_location_context(
        self, household_id: str, context: HouseholdLocationContext
    ) -> None:
        self._household(household_id)["location_context"] = context.model_copy(
            deep=True
        )

    def get_location_context(self, household_id: str) -> HouseholdLocationContext | None:
        context = self._household(household_id)["location_context"]
        return context.model_copy(deep=True) if context is not None else None  # type: ignore[union-attr]

    def save_test_result(self, household_id: str, result: ScenarioTestResult) -> None:
        results = self._household(household_id)["test_results"]
        assert isinstance(results, list)
        results.append(result.model_copy(deep=True))

    def get_test_results(self, household_id: str) -> list[ScenarioTestResult]:
        results = self._household(household_id)["test_results"]
        assert isinstance(results, list)
        return deepcopy(results)

    def get_test_result(
        self, household_id: str, test_run_id: str
    ) -> ScenarioTestResult:
        for result in self.get_test_results(household_id):
            if result.test_run_id == test_run_id:
                return result
        raise TestResultNotFound(
            f"Test result '{test_run_id}' was not found for household '{household_id}'."
        )
