"""Estimate when a scattered household is finally together."""

from datetime import datetime, timezone

from app.core.exceptions import ExternalDataUnavailable, LocationNotFound
from app.providers.interfaces import RoutingClient
from app.repositories.households import HouseholdRepository
from app.schemas.households import HouseholdMember, HouseholdPlan
from app.schemas.rendezvous import MemberEta, RendezvousResult
from app.services.plans import PlanCompletionService


def _minutes(seconds: float) -> int:
    """Round to the nearest minute, as the browser does.

    Truncating here instead would print 54 beside a heading that reads 55 for
    the same journey.
    """
    return round(seconds / 60)


class _MemberLocationUnusable(Exception):
    """A member's declared location cannot be turned into coordinates."""


class RendezvousSimulationService:
    """Estimate the moment every member reaches the primary destination.

    Reads the saved plan and mutates nothing, like BasicScenarioService. Travel
    figures come from the routing provider; this service never estimates a
    distance itself, and reports "unavailable" rather than guessing.
    """

    def __init__(
        self, repository: HouseholdRepository, routing_client: RoutingClient
    ) -> None:
        self.repository = repository
        self.routing_client = routing_client

    def simulate(self, household_id: str) -> RendezvousResult:
        plan = self.repository.get_plan(household_id)

        completion = PlanCompletionService().evaluate(plan)
        if completion.overall_status != "complete":
            return self._not_applicable(
                "Finish your plan before running this simulation.",
                missing_sections=[
                    section.section
                    for section in completion.sections
                    if section.status != "complete"
                ],
            )

        destination = plan.arrangements.primary_destination
        if (
            destination is None
            or destination.latitude is None
            or destination.longitude is None
        ):
            return self._not_applicable(
                "Add a verified primary destination before running this simulation."
            )

        try:
            origins = self._origins(household_id, plan.members)
        except LocationNotFound:
            return self._not_applicable(
                "Verify your home address before running this simulation."
            )
        except _MemberLocationUnusable as exc:
            return self._not_applicable(str(exc))

        try:
            legs = self.routing_client.travel_times(
                origins=[point for _, point in origins],
                destination=(destination.latitude, destination.longitude),
            )
        except ExternalDataUnavailable as exc:
            return RendezvousResult(
                status="unavailable",
                unavailable_reason=str(exc),
                destination_name=destination.display_name,
                simulated_at=datetime.now(timezone.utc),
            )

        slowest_seconds = max(leg.travel_seconds for leg in legs)
        etas = [
            MemberEta(
                member_id=origins[leg.origin_index][0].member_id,
                display_name=origins[leg.origin_index][0].display_name,
                origin_kind=origins[leg.origin_index][0].usual_location.kind,
                travel_seconds=leg.travel_seconds,
                distance_meters=leg.distance_meters,
                waiting_seconds=slowest_seconds - leg.travel_seconds,
            )
            for leg in legs
        ]
        slowest = max(etas, key=lambda eta: eta.travel_seconds)

        return RendezvousResult(
            status="ready",
            destination_name=destination.display_name,
            member_etas=etas,
            everyone_together_seconds=slowest_seconds,
            slowest_member_id=slowest.member_id,
            warnings=self._warnings(plan, etas, slowest),
            simulated_at=datetime.now(timezone.utc),
        )

    def _origins(
        self, household_id: str, members: list[HouseholdMember]
    ) -> list[tuple[HouseholdMember, tuple[float, float]]]:
        """Pair each member with the coordinates they start from."""
        household_point: tuple[float, float] | None = None
        origins: list[tuple[HouseholdMember, tuple[float, float]]] = []

        for member in members:
            location = member.usual_location
            if location is None:
                raise _MemberLocationUnusable(
                    f"{member.display_name or 'A member'} has no usual location recorded."
                )
            if location.kind == "home":
                if household_point is None:
                    household_point = self._household_point(household_id)
                origins.append((member, household_point))
                continue
            if location.latitude is None or location.longitude is None:
                raise _MemberLocationUnusable(
                    f"{member.display_name or 'A member'} has an unverified usual address."
                )
            origins.append((member, (location.latitude, location.longitude)))
        return origins

    def _household_point(self, household_id: str) -> tuple[float, float]:
        location = self.repository.get_location(household_id)
        if location.latitude is None or location.longitude is None:
            raise LocationNotFound("The household location is not verified.")
        return (location.latitude, location.longitude)

    @staticmethod
    def _warnings(
        plan: HouseholdPlan, etas: list[MemberEta], slowest: MemberEta
    ) -> list[str]:
        """Deterministic rules over data the plan already holds. No AI."""
        warnings: list[str] = []
        members = {member.member_id: member for member in plan.members}
        drivers = {
            member_id
            for transport in plan.transports
            for member_id in transport.driver_member_ids
        }

        for eta in etas:
            member = members[eta.member_id]
            name = member.display_name or "A member"
            if member.is_dependant or member.mobility_support_required:
                warnings.append(
                    f"{name} cannot travel independently. Assign an adult to collect them."
                )
            if member.member_id not in drivers:
                warnings.append(
                    f"{name} cannot drive any transport in your plan. "
                    "These estimates assume car travel."
                )

        waiting = [
            eta.waiting_seconds for eta in etas if eta.member_id != slowest.member_id
        ]
        if waiting:
            average_wait = sum(waiting) / len(waiting)
            warnings.append(
                f"{slowest.display_name or 'One member'} takes the longest at "
                f"{_minutes(slowest.travel_seconds)} minutes. The others wait about "
                f"{_minutes(average_wait)} minutes at the destination."
            )
        return warnings

    @staticmethod
    def _not_applicable(
        reason: str, missing_sections: list[str] | None = None
    ) -> RendezvousResult:
        return RendezvousResult(
            status="not_applicable",
            unavailable_reason=reason,
            missing_sections=missing_sections or [],
            simulated_at=datetime.now(timezone.utc),
        )
