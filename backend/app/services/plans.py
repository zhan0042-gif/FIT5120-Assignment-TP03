"""Household plan validation and completion rules."""

from app.core.exceptions import PlanValidationError
from app.repositories.households import HouseholdRepository
from app.schemas.households import (
    CompletionSection,
    HouseholdPlan,
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
            [pet.pet_id for pet in plan.pets], "pet_id", errors
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
        if arrangements.primary_transport_id not in known_transports:
            errors.append("primary_transport_id must reference an existing transport")
        if (
            arrangements.backup_transport_id is not None
            and arrangements.backup_transport_id not in known_transports
        ):
            errors.append("backup_transport_id must reference an existing transport")
        if arrangements.backup_transport_id == arrangements.primary_transport_id:
            errors.append("backup_transport_id must differ from primary_transport_id")

        for responsibility in plan.responsibilities:
            if responsibility.primary_member_id not in known_members:
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
            if responsibility.backup_member_id == responsibility.primary_member_id:
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

    def evaluate(self, plan: HouseholdPlan) -> PlanCompletion:
        arrangements = plan.arrangements
        statuses = {
            "household_profile": bool(plan.members),
            "transport": bool(plan.transports and arrangements.primary_transport_id),
            "backup_transport": bool(arrangements.backup_transport_id),
            "primary_destination": arrangements.primary_destination is not None,
            "backup_destination": arrangements.backup_destination is not None,
            "responsibilities": bool(plan.responsibilities),
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
        )

