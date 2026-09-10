"""Household plan validation and completion rules."""

from app.core.exceptions import PlanValidationError
from app.providers.interfaces import AddressClient
from app.repositories.households import HouseholdRepository
from app.schemas.households import (
    CompletionSection,
    Destination,
    HouseholdPlan,
    ImmediateCheck,
    PlanCompletion,
)
from app.services.context import AddressVerificationService


class HouseholdPlanService:
    """Validate and persist the household plan aggregate.

    HTTP routes and repositories delegate business consistency to this service.
    Plans may remain incomplete; validation protects references and aggregate
    structure, while completion services report missing preparedness details.
    """

    def __init__(
        self, repository: HouseholdRepository, address_client: AddressClient | None = None
    ) -> None:
        self.repository = repository
        self.address_verifier = (
            AddressVerificationService(address_client) if address_client else None
        )

    def save(self, household_id: str, plan: HouseholdPlan) -> HouseholdPlan:
        """Save one primary and zero-to-many ordered backup arrangements."""
        self.validate(plan)
        plan = self._enrich_member_locations(plan)
        plan = self._enrich_destinations(plan)
        self.repository.save_plan(household_id, plan)
        return self.repository.get_plan(household_id)

    def _enrich_member_locations(self, plan: HouseholdPlan) -> HouseholdPlan:
        """Resolve coordinates for declared member locations that still need them.

        Suggestions carry no coordinates, so an address typed in the browser can
        only become a point here. Unlike destinations, an already verified
        location is left alone: re-resolving every member on every save would
        multiply the provider calls a save already makes. Editing the address
        clears the flag in the browser, so a changed address is resolved again.
        """
        if self.address_verifier is None:
            return plan
        members = []
        for member in plan.members:
            location = member.usual_location
            if location is None or location.kind == "home" or not location.address.strip():
                members.append(member)
                continue
            if (
                location.verification_status == "verified"
                and location.latitude is not None
                and location.longitude is not None
            ):
                members.append(member.model_copy(
                    update={"usual_location": location.model_copy(
                        update={"selected_address": None}
                    )}
                ))
                continue
            verification = self.address_verifier.verify(
                location.address, location.selected_address
            )
            members.append(
                member.model_copy(
                    update={
                        "usual_location": location.model_copy(
                            update={
                                "latitude": verification.latitude,
                                "longitude": verification.longitude,
                                "verification_status": verification.verification_status,
                                "selected_address": None,
                            }
                        )
                    }
                )
            )
        return plan.model_copy(update={"members": members})

    def _enrich_destinations(self, plan: HouseholdPlan) -> HouseholdPlan:
        """Verify destination addresses without making verification a save prerequisite."""
        if self.address_verifier is None:
            return plan
        arrangements = plan.arrangements.model_copy(deep=True)
        arrangements.primary_destination = self._enrich_destination(
            arrangements.primary_destination
        )
        for backup in arrangements.backup_arrangements:
            backup.destination = self._enrich_destination(backup.destination)
        return plan.model_copy(update={"arrangements": arrangements})

    def _enrich_destination(self, destination: Destination | None) -> Destination | None:
        if destination is None:
            return None
        verification = self.address_verifier.verify(
            destination.address, destination.selected_address
        )
        return destination.model_copy(
            update={
                **verification.model_dump(exclude={"verification_message"}),
                "selected_address": None,
            }
        )

    @staticmethod
    def validate(plan: HouseholdPlan) -> None:
        """Reject broken cross-references while allowing a partially built plan."""
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
        for index, backup in enumerate(arrangements.backup_arrangements, start=1):
            if backup.transport_id is not None and backup.transport_id not in known_transports:
                errors.append(
                    f"backup_arrangements[{index}].transport_id must reference an existing transport"
                )
        destinations = [
            destination
            for destination in (
                arrangements.primary_destination,
                *(backup.destination for backup in arrangements.backup_arrangements),
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
    """Derive the six section statuses from the latest saved plan.

    Completion is not a stored or manually checked to-do list. Backup sections
    become complete when at least one applicable backup arrangement is present.
    """

    SECTION_ORDER = (
        "household_profile",
        "member_locations",
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
            and all(animal.animal_type for animal in plan.animals),
            # The simulation needs a starting point for every member, so a plan
            # is only complete once each of them has one declared.
            "member_locations": bool(plan.members)
            and all(member.usual_location is not None for member in plan.members),
            "transport": explicitly_no_private_transport
            or bool(plan.transports and arrangements.primary_transport_id),
            "backup_transport": explicitly_no_private_transport
            or any(backup.transport_id for backup in arrangements.backup_arrangements),
            "primary_destination": bool(
                arrangements.primary_destination
                and arrangements.primary_destination.display_name.strip()
            ),
            "backup_destination": any(
                backup.destination and backup.destination.display_name.strip()
                for backup in arrangements.backup_arrangements
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
    """Warn about practical weaknesses without blocking plan persistence.

    These checks highlight missing or non-independent backup resources and
    people. They are advisory results derived from the same saved aggregate.
    """

    def evaluate(self, plan: HouseholdPlan) -> list[ImmediateCheck]:
        arrangements = plan.arrangements
        checks: list[ImmediateCheck] = []

        backup_transport_ids = [
            backup.transport_id
            for backup in arrangements.backup_arrangements
            if backup.transport_id is not None
        ]
        independent_backup_transport = any(
            transport_id != arrangements.primary_transport_id
            for transport_id in backup_transport_ids
        )
        if (
            arrangements.primary_transport_id is not None
            and not backup_transport_ids
        ):
            checks.append(
                ImmediateCheck(
                    check="missing_backup_transport",
                    section="backup_transport",
                    message="No independent backup transport is set.",
                )
            )

        if (
            arrangements.primary_destination is not None
            and not any(
                self._meaningfully_different_destination(
                    arrangements.primary_destination, backup.destination
                )
                for backup in arrangements.backup_arrangements
            )
        ):
            checks.append(
                ImmediateCheck(
                    check="missing_backup_destination",
                    section="backup_destination",
                    message="No independent backup destination is set.",
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
            and backup_transport_ids
            and not independent_backup_transport
        ):
            checks.append(
                ImmediateCheck(
                    check="shared_transport_resource",
                    section="backup_transport",
                    message="All backup arrangements use the primary transport.",
                )
            )

        return checks

    @staticmethod
    def _missing_backup_person_message(task_name: str) -> str:
        task = task_name.strip()
        if task:
            return f'No backup person is assigned for "{task}".'
        return "A responsibility has no backup person assigned."

    @staticmethod
    def _meaningfully_different_destination(primary, backup) -> bool:
        return bool(
            backup
            and backup.destination_id != primary.destination_id
            and (backup.address or "").strip().casefold()
            != (primary.address or "").strip().casefold()
        )
