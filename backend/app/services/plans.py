"""Household plan validation and completion rules."""

from app.core.exceptions import PlanValidationError
from app.repositories.households import HouseholdRepository
from app.schemas.households import (
    CompletionSection,
    HouseholdPlan,
    ImmediateCheck,
    PlanCompletion,
)


class HouseholdPlanService:
    def __init__(self, repository: HouseholdRepository) -> None:
        self.repository = repository

    def save(self, household_id: str, plan: HouseholdPlan) -> HouseholdPlan:
        self.validate(plan)
        self.repository.save_plan(household_id, plan)
        return self.repository.get_plan(household_id)

    @staticmethod
    def validate(plan: HouseholdPlan) -> None:
        errors: list[str] = []
        member_ids = [member.member_id for member in plan.members]
        transport_ids = [transport.transport_id for transport in plan.transports]

        HouseholdPlanService._check_unique(member_ids, "member_id", errors)
        HouseholdPlanService._check_unique(transport_ids, "transport_id", errors)
        HouseholdPlanService._check_unique(
            [animal.animal_id for animal in plan.animals], "animal_id", errors
        )
        HouseholdPlanService._check_unique(
            [item.responsibility_id for item in plan.responsibilities],
            "responsibility_id",
            errors,
        )

        known_members = set(member_ids)
        known_transports = set(transport_ids)
        for transport in plan.transports:
            unknown = set(transport.driver_member_ids) - known_members
            if unknown:
                errors.append(
                    f"Transport '{transport.transport_id}' references unknown driver member IDs: "
                    + ", ".join(sorted(unknown))
                )

        arrangements = plan.arrangements
        if (
            arrangements.primary_transport_id is not None
            and arrangements.primary_transport_id not in known_transports
        ):
            errors.append("primary_transport_id must reference an existing transport")
        if (
            arrangements.backup_transport_id is not None
            and arrangements.backup_transport_id not in known_transports
        ):
            errors.append("backup_transport_id must reference an existing transport")
        destinations = [
            destination
            for destination in (
                arrangements.primary_destination,
                arrangements.backup_destination,
            )
            if destination is not None
        ]
        HouseholdPlanService._check_unique(
            [destination.destination_id for destination in destinations],
            "destination_id",
            errors,
        )

        for responsibility in plan.responsibilities:
            if (
                responsibility.primary_member_id is not None
                and responsibility.primary_member_id not in known_members
            ):
                errors.append(
                    f"Responsibility '{responsibility.responsibility_id}' references an "
                    "unknown primary member"
                )
            if (
                responsibility.backup_member_id is not None
                and responsibility.backup_member_id not in known_members
            ):
                errors.append(
                    f"Responsibility '{responsibility.responsibility_id}' references an "
                    "unknown backup member"
                )
            if (
                responsibility.backup_member_id is not None
                and responsibility.backup_member_id
                == responsibility.primary_member_id
            ):
                errors.append(
                    f"Responsibility '{responsibility.responsibility_id}' must assign a "
                    "different backup member"
                )

        if errors:
            raise PlanValidationError(errors)

    @staticmethod
    def _check_unique(values: list[str], label: str, errors: list[str]) -> None:
        if len(values) != len(set(values)):
            errors.append(f"{label} values must be unique")


class PlanCompletionService:
    """Determine completeness with explicit, non-scored section rules."""

    SECTION_ORDER = (
        "household_profile",
        "transport",
        "backup_transport",
        "primary_destination",
        "backup_destination",
        "responsibilities",
    )

    def __init__(
        self, immediate_check_service: "ImmediateCheckService | None" = None
    ) -> None:
        self.immediate_check_service = immediate_check_service or ImmediateCheckService()

    def evaluate(self, plan: HouseholdPlan) -> PlanCompletion:
        arrangements = plan.arrangements
        explicitly_no_private_transport = (
            plan.has_private_transport is False
            and arrangements.primary_transport_id is None
        )
        statuses = {
            "household_profile": bool(plan.members)
            and all(member.display_name.strip() for member in plan.members)
            and all(
                animal.display_name.strip() and animal.animal_type.strip()
                for animal in plan.animals
            ),
            "transport": explicitly_no_private_transport
            or bool(plan.transports and arrangements.primary_transport_id),
            "backup_transport": explicitly_no_private_transport
            or bool(arrangements.backup_transport_id),
            "primary_destination": bool(
                arrangements.primary_destination
                and arrangements.primary_destination.display_name.strip()
            ),
            "backup_destination": bool(
                arrangements.backup_destination
                and arrangements.backup_destination.display_name.strip()
            ),
            "responsibilities": bool(plan.responsibilities)
            and all(
                responsibility.task_name.strip()
                and responsibility.primary_member_id
                for responsibility in plan.responsibilities
            ),
        }
        sections = [
            CompletionSection(
                section=section,
                status="complete" if statuses[section] else "needs_information",
            )
            for section in self.SECTION_ORDER
        ]
        return PlanCompletion(
            overall_status=(
                "complete" if all(statuses.values()) else "needs_information"
            ),
            sections=sections,
            immediate_checks=self.immediate_check_service.evaluate(plan),
        )


class ImmediateCheckService:
    """Report simple deterministic issues in the latest saved plan."""

    def evaluate(self, plan: HouseholdPlan) -> list[ImmediateCheck]:
        arrangements = plan.arrangements
        checks: list[ImmediateCheck] = []

        if (
            arrangements.primary_transport_id is not None
            and arrangements.backup_transport_id is None
        ):
            checks.append(
                ImmediateCheck(
                    check="missing_backup_transport",
                    section="backup_transport",
                    message="No backup transport is set.",
                )
            )

        if (
            arrangements.primary_destination is not None
            and arrangements.backup_destination is None
        ):
            checks.append(
                ImmediateCheck(
                    check="missing_backup_destination",
                    section="backup_destination",
                    message="No backup destination is set.",
                )
            )

        for responsibility in plan.responsibilities:
            if (
                responsibility.primary_member_id is not None
                and responsibility.backup_member_id is None
            ):
                checks.append(
                    ImmediateCheck(
                        check="missing_backup_person",
                        section="responsibilities",
                        message=self._missing_backup_person_message(
                            responsibility.task_name
                        ),
                    )
                )

        if (
            arrangements.primary_transport_id is not None
            and arrangements.backup_transport_id
            == arrangements.primary_transport_id
        ):
            checks.append(
                ImmediateCheck(
                    check="shared_transport_resource",
                    section="backup_transport",
                    message="Primary and backup transport use the same resource.",
                )
            )

        return checks

    @staticmethod
    def _missing_backup_person_message(task_name: str) -> str:
        task = task_name.strip()
        if task:
            return f'No backup person is assigned for "{task}".'
        return "A responsibility has no backup person assigned."
