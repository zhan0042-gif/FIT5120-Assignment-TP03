"""Household travel-disruption awareness."""

from datetime import datetime, timezone

from app.core.exceptions import ExternalDataUnavailable
from app.providers.interfaces import RoadDisruptionClient
from app.repositories.households import HouseholdRepository
from app.schemas.households import Destination, HouseholdPlan
from app.schemas.travel_disruptions import (
    DestinationDisruptions,
    TravelDisruptionResult,
)


DEFAULT_SEARCH_RADIUS_KM = 10.0


class TravelDisruptionService:
    """Report current road disruptions near saved evacuation destinations.

    This is destination-proximity context only. It does not determine whether
    the household's actual travel route is blocked.
    """

    def __init__(
        self,
        repository: HouseholdRepository,
        road_disruption_client: RoadDisruptionClient,
    ) -> None:
        self.repository = repository
        self.road_disruption_client = road_disruption_client

    def get(
        self,
        household_id: str,
        *,
        radius_km: float = DEFAULT_SEARCH_RADIUS_KM,
    ) -> TravelDisruptionResult:
        plan = self.repository.get_plan(household_id)
        checked_at = datetime.now(timezone.utc)

        primary = plan.arrangements.primary_destination

        backup_destinations = [
            arrangement.destination
            for arrangement in plan.arrangements.backup_arrangements
            if arrangement.destination is not None
        ]

        usable_primary = self._is_usable(primary)

        usable_backups = [
            destination
            for destination in backup_destinations
            if self._is_usable(destination)
        ]

        if not usable_primary and not usable_backups:
            return TravelDisruptionResult(
                status="not_applicable",
                checked_at=checked_at,
                unavailable_reason=(
                    "Add and verify an evacuation destination before checking "
                    "current road disruptions."
                ),
            )

        try:
            primary_result = (
                self._destination_result(primary, radius_km=radius_km)
                if usable_primary and primary is not None
                else None
            )

            backup_results = [
                self._destination_result(
                    destination,
                    radius_km=radius_km,
                )
                for destination in usable_backups
            ]

        except ExternalDataUnavailable as exc:
            return TravelDisruptionResult(
                status="unavailable",
                checked_at=checked_at,
                unavailable_reason=str(exc),
            )

        return TravelDisruptionResult(
            status="available",
            checked_at=checked_at,
            primary_destination=primary_result,
            backup_destinations=backup_results,
        )

    def _destination_result(
        self,
        destination: Destination,
        *,
        radius_km: float,
    ) -> DestinationDisruptions:
        assert destination.latitude is not None
        assert destination.longitude is not None

        disruptions = self.road_disruption_client.nearby_disruptions(
            destination.latitude,
            destination.longitude,
            radius_km=radius_km,
        )

        return DestinationDisruptions(
            destination_id=destination.destination_id,
            destination_name=(
                destination.display_name
                or destination.canonical_address
                or destination.address
                or "Saved destination"
            ),
            destination_address=destination.canonical_address or destination.address,
            latitude=destination.latitude,
            longitude=destination.longitude,
            search_radius_km=radius_km,
            active_disruption_count=len(disruptions),
            disruptions=disruptions,
        )

    @staticmethod
    def _is_usable(destination: Destination | None) -> bool:
        return (
            destination is not None
            and destination.verification_status == "verified"
            and destination.latitude is not None
            and destination.longitude is not None
        )
