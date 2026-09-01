"""Fixed basic scenario library and deterministic preparedness checks."""

from datetime import datetime, timezone
from uuid import uuid4

from app.core.exceptions import ScenarioNotApplicable, UnsupportedScenario
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
        enabled=True,
        disabled_reason=None,
    ),
    BasicScenario(
        scenario_id="person_unavailable",
        title="Primary Responsible Person Unavailable",
        description="Check whether important responsibilities have backup people.",
        enabled=True,
        disabled_reason=None,
    ),
    BasicScenario(
        scenario_id="destination_unavailable",
        title="Primary Destination Unavailable",
        description="Check whether another destination is available.",
        enabled=True,
        disabled_reason=None,
    ),
)


class BasicScenarioService:
    def __init__(self, repository: HouseholdRepository | None = None) -> None:
        self.repository = repository

    def list_for_household(self, household_id: str) -> list[BasicScenario]:
        if self.repository is None:
            raise RuntimeError("A repository is required to list household scenarios.")
        return self.list_scenarios(self.repository.get_plan(household_id))

    def list_scenarios(self, plan: HouseholdPlan) -> list[BasicScenario]:
        scenarios: list[BasicScenario] = []
        for scenario in BASIC_SCENARIOS:
            enabled, disabled_reason = self._relevance(plan, scenario.scenario_id)
            scenarios.append(
                scenario.model_copy(
                    deep=True,
                    update={
                        "enabled": enabled,
                        "disabled_reason": disabled_reason,
                    },
                )
            )
        return scenarios

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
            handler = handlers[scenario_id]
        except KeyError as exc:
            raise UnsupportedScenario(
                f"Scenario '{scenario_id}' is not supported."
            ) from exc
        enabled, disabled_reason = self._relevance(plan, scenario_id)
        if not enabled:
            raise ScenarioNotApplicable(
                disabled_reason or f"Scenario '{scenario_id}' is not applicable."
            )
        checks, problem, result_reason = handler(plan)
        return ScenarioTestResult(
            test_run_id=f"test_{uuid4().hex}",
            scenario_id=scenario_id,
            overall_status=(
                "pass" if all(check.status == "pass" for check in checks) else "needs_attention"
            ),
            checks=checks,
            first_problem=problem,
            result_reason=result_reason,
            tested_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _relevance(plan: HouseholdPlan, scenario_id: str) -> tuple[bool, str | None]:
        if scenario_id == "vehicle_unavailable":
            enabled = plan.arrangements.primary_transport_id is not None
            return (
                enabled,
                None if enabled else "No primary transport is currently recorded.",
            )
        if scenario_id == "person_unavailable":
            enabled = any(
                responsibility.primary_member_id is not None
                for responsibility in plan.responsibilities
            )
            return (
                enabled,
                None
                if enabled
                else "No primary responsible person is currently recorded.",
            )
        if scenario_id == "destination_unavailable":
            enabled = plan.arrangements.primary_destination is not None
            return (
                enabled,
                None if enabled else "No primary destination is currently recorded.",
            )
        raise UnsupportedScenario(f"Scenario '{scenario_id}' is not supported.")

    @staticmethod
    def _vehicle_unavailable(
        plan: HouseholdPlan,
    ) -> tuple[list[ScenarioCheck], FirstProblem | None, str]:
        primary_id = plan.arrangements.primary_transport_id
        transports = {item.transport_id: item for item in plan.transports}
        eligible_backups = [
            transports[backup.transport_id]
            for backup in plan.arrangements.backup_arrangements
            if backup.transport_id
            and backup.transport_id != primary_id
            and backup.transport_id in transports
        ]
        if not eligible_backups:
            return [
                ScenarioCheck(
                    check="backup_transport",
                    status="fail",
                    message="No independent backup transport is set.",
                ),
                ScenarioCheck(
                    check="backup_driver",
                    status="not_checked",
                    message="A backup driver cannot be checked because no independent backup transport is set.",
                ),
            ], FirstProblem(
                section="transport",
                message="Your plan needs a usable backup transport arrangement.",
            ), "The primary transport is unavailable and no independent backup transport is recorded."

        member_ids = {member.member_id for member in plan.members}
        driver_capable_backup = next(
            (
                backup
                for backup in eligible_backups
                if set(backup.driver_member_ids) & member_ids
            ),
            None,
        )
        if driver_capable_backup is None:
            return [
                ScenarioCheck(
                    check="backup_transport",
                    status="pass",
                    message="A different backup transport is set.",
                ),
                ScenarioCheck(
                    check="backup_driver",
                    status="fail",
                message="No independent backup transport has a valid driver.",
                ),
            ], FirstProblem(
                section="transport",
                message="Assign a valid driver to the backup transport.",
            ), "Independent backup transport is recorded, but none has a valid recorded driver."
        return [
            ScenarioCheck(
                check="backup_transport",
                status="pass",
                message="A different backup transport is set.",
            ),
            ScenarioCheck(
                check="backup_driver",
                status="pass",
                message="An independent backup transport has a valid driver.",
            ),
        ], None, "An independent backup transport with a valid recorded driver is recorded."

    @staticmethod
    def _person_unavailable(
        plan: HouseholdPlan,
    ) -> tuple[list[ScenarioCheck], FirstProblem | None, str]:
        member_ids = {member.member_id for member in plan.members}
        relevant = [
            responsibility
            for responsibility in plan.responsibilities
            if responsibility.primary_member_id is not None
        ]
        invalid = [
            responsibility
            for responsibility in relevant
            if not responsibility.backup_member_id
            or responsibility.backup_member_id == responsibility.primary_member_id
            or responsibility.backup_member_id not in member_ids
        ]
        if invalid:
            return [
                ScenarioCheck(
                    check="backup_person",
                    status="fail",
                    message="One or more responsibilities do not have a different backup person.",
                )
            ], FirstProblem(
                section="responsibilities",
                message="Assign a different backup person to every important responsibility.",
            ), "At least one primary responsibility has no valid different backup person."
        return [
            ScenarioCheck(
                check="backup_person",
                status="pass",
                message="Every responsibility has a different backup person.",
            )
        ], None, "Every primary responsibility has a valid different backup person."

    @staticmethod
    def _destination_unavailable(
        plan: HouseholdPlan,
    ) -> tuple[list[ScenarioCheck], FirstProblem | None, str]:
        primary = plan.arrangements.primary_destination
        meaningfully_different = any(
            backup.destination
            and backup.destination.destination_id != primary.destination_id
            and (backup.destination.address or "").strip().casefold()
            != (primary.address or "").strip().casefold()
            for backup in plan.arrangements.backup_arrangements
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
            ), "The primary destination is unavailable and no independent backup destination is recorded."
        return [
            ScenarioCheck(
                check="backup_destination",
                status="pass",
                message="A different backup destination is set.",
            )
        ], None, "An independent backup destination is recorded."
