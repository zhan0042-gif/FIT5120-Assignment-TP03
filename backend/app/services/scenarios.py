"""Fixed basic scenario library and deterministic preparedness checks."""

from datetime import datetime, timezone
from uuid import uuid4

from app.core.exceptions import UnsupportedScenario
from app.repositories.households import HouseholdRepository
from app.schemas.households import HouseholdPlan
from app.schemas.scenarios import (
    BasicScenario,
    FirstProblem,
    ScenarioCheck,
    ScenarioTestResult,
)


BASIC_SCENARIOS = (
    BasicScenario(
        scenario_id="vehicle_unavailable",
        title="Main Vehicle Unavailable",
        description="Check whether another transport option is available.",
    ),
    BasicScenario(
        scenario_id="person_unavailable",
        title="Primary Responsible Person Unavailable",
        description="Check whether important responsibilities have backup people.",
    ),
    BasicScenario(
        scenario_id="destination_unavailable",
        title="Primary Destination Unavailable",
        description="Check whether another destination is available.",
    ),
)


class BasicScenarioService:
    def __init__(self, repository: HouseholdRepository | None = None) -> None:
        self.repository = repository

    def list_scenarios(self) -> list[BasicScenario]:
        return [scenario.model_copy(deep=True) for scenario in BASIC_SCENARIOS]

    def run_for_household(
        self, household_id: str, scenario_id: str
    ) -> ScenarioTestResult:
        if self.repository is None:
            raise RuntimeError("A repository is required to run a household test.")
        plan = self.repository.get_plan(household_id)
        result = self.run(plan, scenario_id)
        self.repository.save_test_result(household_id, result)
        return result

    def run(self, plan: HouseholdPlan, scenario_id: str) -> ScenarioTestResult:
        handlers = {
            "vehicle_unavailable": self._vehicle_unavailable,
            "person_unavailable": self._person_unavailable,
            "destination_unavailable": self._destination_unavailable,
        }
        try:
            checks, problem = handlers[scenario_id](plan)
        except KeyError as exc:
            raise UnsupportedScenario(
                f"Scenario '{scenario_id}' is not supported."
            ) from exc
        return ScenarioTestResult(
            test_run_id=f"test_{uuid4().hex}",
            scenario_id=scenario_id,
            overall_status=(
                "pass" if all(check.status == "pass" for check in checks) else "needs_attention"
            ),
            checks=checks,
            first_problem=problem,
            tested_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _vehicle_unavailable(
        plan: HouseholdPlan,
    ) -> tuple[list[ScenarioCheck], FirstProblem | None]:
        primary_id = plan.arrangements.primary_transport_id
        backup_id = plan.arrangements.backup_transport_id
        transports = {item.transport_id: item for item in plan.transports}
        if not backup_id or backup_id == primary_id or backup_id not in transports:
            return [
                ScenarioCheck(
                    check="backup_transport",
                    status="fail",
                    message="No different backup transport is set.",
                ),
                ScenarioCheck(
                    check="backup_driver",
                    status="not_checked",
                    message="A backup driver cannot be checked because no backup transport is set.",
                ),
            ], FirstProblem(
                section="transport",
                message="Your plan needs a backup transport arrangement.",
            )

        backup = transports[backup_id]
        member_ids = {member.member_id for member in plan.members}
        valid_backup_drivers = set(backup.driver_member_ids) & member_ids
        if not valid_backup_drivers:
            return [
                ScenarioCheck(
                    check="backup_transport",
                    status="pass",
                    message="A different backup transport is set.",
                ),
                ScenarioCheck(
                    check="backup_driver",
                    status="fail",
                    message="The backup transport has no valid driver.",
                ),
            ], FirstProblem(
                section="transport",
                message="Assign a valid driver to the backup transport.",
            )
        return [
            ScenarioCheck(
                check="backup_transport",
                status="pass",
                message="A different backup transport is set.",
            ),
            ScenarioCheck(
                check="backup_driver",
                status="pass",
                message="The backup transport has a valid driver.",
            ),
        ], None

    @staticmethod
    def _person_unavailable(
        plan: HouseholdPlan,
    ) -> tuple[list[ScenarioCheck], FirstProblem | None]:
        member_ids = {member.member_id for member in plan.members}
        invalid = [
            responsibility
            for responsibility in plan.responsibilities
            if not responsibility.backup_member_id
            or responsibility.backup_member_id == responsibility.primary_member_id
            or responsibility.backup_member_id not in member_ids
        ]
        if not plan.responsibilities or invalid:
            return [
                ScenarioCheck(
                    check="backup_person",
                    status="fail",
                    message="One or more responsibilities do not have a different backup person.",
                )
            ], FirstProblem(
                section="responsibilities",
                message="Assign a different backup person to every important responsibility.",
            )
        return [
            ScenarioCheck(
                check="backup_person",
                status="pass",
                message="Every responsibility has a different backup person.",
            )
        ], None

    @staticmethod
    def _destination_unavailable(
        plan: HouseholdPlan,
    ) -> tuple[list[ScenarioCheck], FirstProblem | None]:
        primary = plan.arrangements.primary_destination
        backup = plan.arrangements.backup_destination
        meaningfully_different = bool(
            primary
            and backup
            and backup.destination_id != primary.destination_id
            and (backup.address or "").strip().casefold()
            != (primary.address or "").strip().casefold()
        )
        if not meaningfully_different:
            return [
                ScenarioCheck(
                    check="backup_destination",
                    status="fail",
                    message="No meaningfully different backup destination is set.",
                )
            ], FirstProblem(
                section="backup_destination",
                message="Your plan needs a different backup destination.",
            )
        return [
            ScenarioCheck(
                check="backup_destination",
                status="pass",
                message="A different backup destination is set.",
            )
        ], None
