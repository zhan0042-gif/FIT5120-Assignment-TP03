import os
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.dependencies import get_household_repository
from app.core.exceptions import PlanValidationError, TestResultNotFound as MissingTestResult
from app.main import app
from app.repositories.mysql import MySQLHouseholdRepository
from app.schemas.households import HouseholdLocation, HouseholdLocationContext, HouseholdPlan
from app.schemas.scenarios import FirstProblem, ScenarioCheck, ScenarioTestResult


MYSQL_TEST_URL = os.getenv("MYSQL_TEST_URL")
pytestmark = pytest.mark.skipif(
    not MYSQL_TEST_URL,
    reason="MYSQL_TEST_URL is required for isolated MySQL integration tests",
)


@pytest.fixture
def mysql_repository():
    assert MYSQL_TEST_URL is not None
    engine = create_engine(MYSQL_TEST_URL, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM household"))
    repository = MySQLHouseholdRepository(engine)
    yield repository, engine
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM household"))
    engine.dispose()


def test_household_and_complete_plan_round_trip_use_public_ids(
    mysql_repository, complete_plan: HouseholdPlan
) -> None:
    repository, engine = mysql_repository
    household_id = repository.create_household("Integration household")
    complete_plan.transports[0].driver_member_ids.append("m_002")

    repository.save_plan(household_id, complete_plan)

    assert household_id.startswith("hh_")
    assert repository.household_exists(household_id) is True
    assert repository.get_plan(household_id) == complete_plan
    repository.save_plan(household_id, repository.get_plan(household_id))
    assert repository.get_plan(household_id) == complete_plan
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT household_id, public_id FROM household "
                "WHERE public_id = :public_id"
            ),
            {"public_id": household_id},
        ).one()
        assert isinstance(row.household_id, int)
        assert row.public_id == household_id
        stored_member = connection.execute(
            text("SELECT member_id, public_id FROM household_member LIMIT 1")
        ).one()
        assert isinstance(stored_member.member_id, int)
        assert stored_member.public_id.startswith("m_")
        assert connection.execute(text("SELECT COUNT(*) FROM transport_driver")).scalar_one() == 3


def test_multiple_backup_arrangements_round_trip_in_priority_order(
    mysql_repository, complete_plan_data: dict
) -> None:
    repository, engine = mysql_repository
    plan_data = deepcopy(complete_plan_data)
    plan_data["arrangements"]["backup_arrangements"].insert(
        0, {"transport_id": "t_001", "destination": None}
    )
    plan = HouseholdPlan.model_validate(plan_data)
    household_id = repository.create_household()

    repository.save_plan(household_id, plan)

    assert repository.get_plan(household_id) == plan
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT role, priority FROM household_arrangement_option "
                "ORDER BY priority"
            )
        ).all()
    assert rows == [("primary", 0), ("backup", 1), ("backup", 2)]


@pytest.mark.parametrize("has_private_transport", [None, False, True])
def test_incomplete_plan_preserves_private_transport_tristate(
    mysql_repository, has_private_transport: bool | None
) -> None:
    repository, _ = mysql_repository
    household_id = repository.create_household()
    plan = HouseholdPlan(
        has_private_transport=has_private_transport,
        responsibilities=[
            {
                "responsibility_id": "r_unassigned",
                "task_name": "Collect documents",
                "primary_member_id": None,
                "backup_member_id": None,
            }
        ],
    )

    repository.save_plan(household_id, plan)

    assert repository.get_plan(household_id) == plan


def test_plan_update_replaces_the_aggregate_without_stale_children(
    mysql_repository, complete_plan: HouseholdPlan
) -> None:
    repository, engine = mysql_repository
    household_id = repository.create_household()
    repository.save_plan(household_id, complete_plan)
    replacement = HouseholdPlan(
        members=[
            {
                "member_id": "m_replacement",
                "display_name": "Replacement",
                "is_dependant": False,
                "mobility_support_required": False,
            }
        ],
        has_private_transport=False,
    )

    repository.save_plan(household_id, replacement)

    assert repository.get_plan(household_id) == replacement
    with engine.connect() as connection:
        counts = {
            table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            for table in (
                "household_member",
                "animal",
                "transport",
                "destination",
                "responsibility",
            )
        }
    assert counts == {
        "household_member": 1,
        "animal": 0,
        "transport": 0,
        "destination": 0,
        "responsibility": 0,
    }


def test_public_ids_cannot_be_reassigned_between_households(
    mysql_repository, complete_plan: HouseholdPlan
) -> None:
    repository, _ = mysql_repository
    first_household = repository.create_household()
    second_household = repository.create_household()
    repository.save_plan(first_household, complete_plan)

    with pytest.raises(PlanValidationError, match="another household") as error:
        repository.save_plan(second_household, complete_plan)

    assert any("household_member" in item for item in error.value.errors)
    assert any("transport" in item for item in error.value.errors)
    assert any("destination" in item for item in error.value.errors)
    assert repository.get_plan(first_household) == complete_plan


def test_api_returns_422_for_cross_household_public_ids(
    mysql_repository, complete_plan_data: dict
) -> None:
    repository, _ = mysql_repository
    first_household = repository.create_household()
    second_household = repository.create_household()
    repository.save_plan(
        first_household, HouseholdPlan.model_validate(complete_plan_data)
    )
    app.dependency_overrides[get_household_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            response = client.put(
                f"/api/v1/households/{second_household}/plan",
                json=complete_plan_data,
            )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["message"] == "The household plan is invalid."
        assert any("household_member" in item for item in detail["errors"])
        assert any("transport" in item for item in detail["errors"])
        assert any("destination" in item for item in detail["errors"])
    finally:
        app.dependency_overrides.clear()


def test_unknown_relationship_reference_rolls_back_the_plan(
    mysql_repository, complete_plan_data: dict
) -> None:
    repository, engine = mysql_repository
    household_id = repository.create_household()
    invalid_data = deepcopy(complete_plan_data)
    invalid_data["transports"][0]["driver_member_ids"] = ["m_unknown"]
    invalid_plan = HouseholdPlan.model_validate(invalid_data)

    with pytest.raises(PlanValidationError, match="does not belong"):
        repository.save_plan(household_id, invalid_plan)

    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM household_member")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM transport")).scalar_one() == 0


def test_location_upsert_round_trip(mysql_repository) -> None:
    repository, engine = mysql_repository
    household_id = repository.create_household()
    first = HouseholdLocation(
        address="4/84 WATTLE TRACK WARRANDYTE VIC 3113",
        unit_number="4",
        street_number="84",
        street_name="WATTLE TRACK",
        suburb_or_locality="Warrandyte",
        postcode="3113",
        latitude=-37.738,
        longitude=145.223,
    )
    updated = HouseholdLocation(
        address="12 HIGH STREET WARBURTON VIC 3799",
        street_number="12",
        street_name="HIGH STREET",
        suburb_or_locality="Warburton",
        postcode="3799",
        latitude=-37.753,
        longitude=145.69,
    )

    repository.save_location(household_id, first)
    repository.save_location(household_id, first)
    repository.save_location(household_id, updated)

    assert repository.get_location(household_id) == updated
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM household_location")).scalar_one() == 1


def test_location_context_round_trip_and_location_change_invalidates_it(
    mysql_repository,
) -> None:
    repository, _ = mysql_repository
    household_id = repository.create_household()
    location = HouseholdLocation(
        address="84 YARRA STREET WARRANDYTE VIC 3113",
        canonical_address="84 YARRA STREET WARRANDYTE VIC 3113",
        latitude=-37.74,
        longitude=145.216,
        verification_status="verified",
        verified_at=datetime.now(timezone.utc),
    )
    context = HouseholdLocationContext(
        is_bushfire_prone_area=True,
        fire_district="Central",
        fire_history_record_count=12,
        fire_history_latest_year=2025,
        fire_history_latest_date="2025-05-13",
        fire_history_radius_km=20,
        generated_at=datetime.now(timezone.utc),
    )

    repository.save_location(household_id, location)
    repository.save_location_context(household_id, context)

    stored = repository.get_location_context(household_id)
    assert stored is not None
    assert stored.fire_district == "Central"
    assert stored.fire_history_record_count == 12

    repository.save_location(household_id, location.model_copy(update={"address": "85 YARRA STREET WARRANDYTE VIC 3113"}))
    assert repository.get_location_context(household_id) is None


def test_scenario_result_round_trip_preserves_order_and_first_problem(
    mysql_repository,
) -> None:
    repository, engine = mysql_repository
    household_id = repository.create_household()
    result = ScenarioTestResult(
        test_run_id="test_persisted",
        scenario_id="vehicle_unavailable",
        overall_status="needs_attention",
        checks=[
            ScenarioCheck(
                check="backup_transport",
                status="fail",
                message="No backup transport is assigned.",
            ),
            ScenarioCheck(
                check="backup_driver",
                status="not_checked",
                message="A driver could not be checked.",
            ),
        ],
        first_problem=FirstProblem(
            section="backup_transport", message="Assign backup transport."
        ),
        result_reason="The plan needs attention.",
        tested_at=datetime(2026, 8, 31, 4, 5, 6, tzinfo=timezone.utc),
    )

    repository.save_test_result(household_id, result)

    assert repository.get_test_result(household_id, result.test_run_id) == result
    assert repository.get_test_results(household_id) == [result]
    with engine.connect() as connection:
        statuses = connection.execute(
            text("SELECT status FROM test_check_result ORDER BY check_order")
        ).scalars().all()
        assert statuses == ["fail", "not_checked"]
    with pytest.raises(MissingTestResult):
        repository.get_test_result(household_id, "test_missing")


def test_api_services_use_the_persisted_plan_without_mutating_it(
    mysql_repository, complete_plan_data: dict
) -> None:
    repository, engine = mysql_repository
    app.dependency_overrides[get_household_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            create_response = client.post("/api/v1/households")
            household_id = create_response.json()["household_id"]
            assert create_response.status_code == 201

            saved_plan_response = client.put(
                f"/api/v1/households/{household_id}/plan",
                json=complete_plan_data,
            )
            assert saved_plan_response.status_code == 200
            saved_plan = saved_plan_response.json()
            assert client.put(
                f"/api/v1/households/{household_id}/location",
                json={"address": "Warrandyte VIC 3113"},
            ).status_code == 200

            completion = client.get(
                f"/api/v1/households/{household_id}/completion"
            )
            scenarios = client.get(
                "/api/v1/scenarios/basic", params={"household_id": household_id}
            )
            test_response = client.post(
                f"/api/v1/households/{household_id}/tests",
                json={"scenario_id": "vehicle_unavailable"},
            )

            assert completion.json()["overall_status"] == "complete"
            assert completion.json()["immediate_checks"] == []
            vehicle_scenario = next(
                item
                for item in scenarios.json()
                if item["scenario_id"] == "vehicle_unavailable"
            )
            assert vehicle_scenario["enabled"] is True
            assert test_response.status_code == 201
            assert test_response.json()["overall_status"] == "pass"
            assert {item["status"] for item in test_response.json()["checks"]} <= {
                "pass",
                "fail",
                "not_checked",
            }
            assert client.get(
                f"/api/v1/households/{household_id}/plan"
            ).json() == saved_plan

        with engine.connect() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM test_run")).scalar_one() == 1
            assert connection.execute(
                text("SELECT COUNT(*) FROM test_check_result")
            ).scalar_one() >= 2
    finally:
        app.dependency_overrides.clear()
