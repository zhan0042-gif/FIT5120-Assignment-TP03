from copy import deepcopy

import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.providers.interfaces import RouteLeg
from app.providers.mock import MockRoutingClient
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import HouseholdLocation, HouseholdPlan
from app.services.rendezvous import RendezvousSimulationService

HOME = (-37.8136, 144.9631)


class StubRoutingClient:
    """Fixed travel times so arithmetic and rules can be asserted exactly."""

    def __init__(self, seconds: list[int]) -> None:
        self.seconds = seconds
        self.calls = 0

    def travel_times(self, origins, destination):
        self.calls += 1
        return [
            RouteLeg(
                origin_index=index,
                travel_seconds=self.seconds[index],
                distance_meters=self.seconds[index] * 10,
                traffic_delay_seconds=0,
            )
            for index in range(len(origins))
        ]


class UnavailableRoutingClient:
    def travel_times(self, origins, destination):
        raise ExternalDataUnavailable("Travel time estimates are unavailable.")


def _ready_plan_data(complete_plan_data: dict) -> dict:
    """The shared fixture, made simulation-ready: a placed destination."""
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {"kind": "home"}
    data["members"][1]["usual_location"] = {
        "kind": "work",
        "address": "200 Bourke Street, Melbourne VIC 3000",
        "latitude": -37.8125,
        "longitude": 144.9665,
        "verification_status": "verified",
    }
    destination = data["arrangements"]["primary_destination"]
    destination["latitude"] = -37.8100
    destination["longitude"] = 144.9700
    return data


def _household_with_location() -> tuple[InMemoryHouseholdRepository, str]:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_location(
        household_id,
        HouseholdLocation(
            address="1 Home Street, Melbourne VIC 3000",
            latitude=HOME[0],
            longitude=HOME[1],
            verification_status="verified",
        ),
    )
    return repository, household_id


@pytest.fixture
def ready_household(complete_plan_data: dict):
    repository, household_id = _household_with_location()
    repository.save_plan(
        household_id, HouseholdPlan.model_validate(_ready_plan_data(complete_plan_data))
    )
    return repository, household_id


def test_slowest_member_sets_the_household_time(ready_household) -> None:
    repository, household_id = ready_household
    routing = StubRoutingClient([720, 2820])

    result = RendezvousSimulationService(repository, routing).simulate(household_id)

    assert result.status == "ready"
    assert result.everyone_together_seconds == 2820
    assert result.slowest_member_id == "m_002"
    assert routing.calls == 1


def test_waiting_time_is_the_gap_to_the_slowest(ready_household) -> None:
    repository, household_id = ready_household

    result = RendezvousSimulationService(
        repository, StubRoutingClient([720, 2820])
    ).simulate(household_id)

    etas = {eta.member_id: eta for eta in result.member_etas}
    assert etas["m_001"].waiting_seconds == 2100
    assert etas["m_002"].waiting_seconds == 0


def test_home_members_start_from_the_household_location(ready_household) -> None:
    repository, household_id = ready_household
    seen: dict = {}

    class RecordingRoutingClient(StubRoutingClient):
        def travel_times(self, origins, destination):
            seen["origins"] = origins
            seen["destination"] = destination
            return super().travel_times(origins, destination)

    RendezvousSimulationService(
        repository, RecordingRoutingClient([720, 2820])
    ).simulate(household_id)

    assert seen["origins"][0] == HOME
    assert seen["origins"][1] == (-37.8125, 144.9665)
    assert seen["destination"] == (-37.8100, 144.9700)


def test_incomplete_plan_is_not_applicable_and_names_the_gaps(
    complete_plan_data: dict,
) -> None:
    repository, household_id = _household_with_location()
    data = deepcopy(complete_plan_data)
    for member in data["members"]:
        member.pop("usual_location", None)
    repository.save_plan(household_id, HouseholdPlan.model_validate(data))

    result = RendezvousSimulationService(
        repository, StubRoutingClient([100, 200])
    ).simulate(household_id)

    assert result.status == "not_applicable"
    assert "member_locations" in result.missing_sections
    assert result.member_etas == []


def test_destination_without_coordinates_is_not_applicable(
    complete_plan_data: dict,
) -> None:
    repository, household_id = _household_with_location()
    data = _ready_plan_data(complete_plan_data)
    data["arrangements"]["primary_destination"]["latitude"] = None
    data["arrangements"]["primary_destination"]["longitude"] = None
    repository.save_plan(household_id, HouseholdPlan.model_validate(data))

    result = RendezvousSimulationService(
        repository, StubRoutingClient([100, 200])
    ).simulate(household_id)

    assert result.status == "not_applicable"
    assert "destination" in (result.unavailable_reason or "").lower()


def test_home_member_without_a_verified_household_location_is_not_applicable(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_plan(
        household_id,
        HouseholdPlan.model_validate(_ready_plan_data(complete_plan_data)),
    )

    result = RendezvousSimulationService(
        repository, StubRoutingClient([100, 200])
    ).simulate(household_id)

    assert result.status == "not_applicable"
    assert "home address" in (result.unavailable_reason or "").lower()


def test_routing_failure_is_unavailable_and_carries_no_figures(ready_household) -> None:
    repository, household_id = ready_household

    result = RendezvousSimulationService(
        repository, UnavailableRoutingClient()
    ).simulate(household_id)

    assert result.status == "unavailable"
    assert result.everyone_together_seconds is None
    assert result.member_etas == []


def test_dependant_member_raises_a_collection_warning(complete_plan_data: dict) -> None:
    repository, household_id = _household_with_location()
    data = _ready_plan_data(complete_plan_data)
    data["members"][1]["is_dependant"] = True
    repository.save_plan(household_id, HouseholdPlan.model_validate(data))

    result = RendezvousSimulationService(
        repository, StubRoutingClient([720, 2820])
    ).simulate(household_id)

    assert any("Alex" in warning and "collect" in warning for warning in result.warnings)


def test_member_who_drives_nothing_raises_a_car_assumption_warning(
    complete_plan_data: dict,
) -> None:
    repository, household_id = _household_with_location()
    data = _ready_plan_data(complete_plan_data)
    for transport in data["transports"]:
        transport["driver_member_ids"] = ["m_001"]
    repository.save_plan(household_id, HouseholdPlan.model_validate(data))

    result = RendezvousSimulationService(
        repository, StubRoutingClient([720, 2820])
    ).simulate(household_id)

    assert any("Alex" in warning and "car" in warning.lower() for warning in result.warnings)


def test_bottleneck_warning_names_the_slowest_member(ready_household) -> None:
    repository, household_id = ready_household

    result = RendezvousSimulationService(
        repository, StubRoutingClient([720, 2820])
    ).simulate(household_id)

    assert any("Alex" in warning and "47" in warning for warning in result.warnings)


def test_mock_routing_client_satisfies_the_service(ready_household) -> None:
    repository, household_id = ready_household

    result = RendezvousSimulationService(repository, MockRoutingClient()).simulate(
        household_id
    )

    assert result.status == "ready"
    assert len(result.member_etas) == 2


def test_warning_minutes_round_the_way_the_browser_does(ready_household) -> None:
    """3295s is 54.9 minutes: the heading rounds to 55, so the warning must too."""
    repository, household_id = ready_household

    result = RendezvousSimulationService(
        repository, StubRoutingClient([1602, 3295])
    ).simulate(household_id)

    assert any("55 minutes" in warning for warning in result.warnings)
    assert not any("54 minutes" in warning for warning in result.warnings)
