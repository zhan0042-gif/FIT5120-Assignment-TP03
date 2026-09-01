"""Transactional MySQL implementation of the Iteration 1 repository boundary."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import (
    DatabaseUnavailable,
    HouseholdNotFound,
    LocationNotFound,
    PlanNotFound,
    PlanValidationError,
    TestResultNotFound,
)
from app.schemas.households import (
    Animal,
    Arrangements,
    Destination,
    HouseholdLocation,
    HouseholdLocationContext,
    HouseholdMember,
    HouseholdPlan,
    Responsibility,
    Transport,
)
from app.schemas.scenarios import (
    FirstProblem,
    ScenarioCheck,
    ScenarioTestResult,
)


class MySQLHouseholdRepository:
    """Persist complete household aggregates while exposing only public IDs."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create_household(self, display_name: str | None = None) -> str:
        public_id = f"hh_{uuid4().hex}"
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO household (public_id, display_name) "
                        "VALUES (:public_id, :display_name)"
                    ),
                    {"public_id": public_id, "display_name": display_name},
                )
        except SQLAlchemyError as exc:
            self._raise_database_unavailable(exc)
        return public_id

    def household_exists(self, household_id: str) -> bool:
        try:
            with self.engine.connect() as connection:
                return (
                    connection.execute(
                        text(
                            "SELECT 1 FROM household WHERE public_id = :public_id"
                        ),
                        {"public_id": household_id},
                    ).first()
                    is not None
                )
        except SQLAlchemyError as exc:
            self._raise_database_unavailable(exc)

    def save_plan(self, household_id: str, plan: HouseholdPlan) -> None:
        try:
            with self.engine.begin() as connection:
                internal_household_id = self._household_internal_id(
                    connection, household_id
                )
                self._validate_public_id_ownership(
                    connection, internal_household_id, plan
                )
                self._delete_plan_rows(connection, internal_household_id)

                member_ids: dict[str, int] = {}
                for member in plan.members:
                    result = connection.execute(
                        text(
                            """
                            INSERT INTO household_member (
                                public_id, household_id, display_name,
                                is_dependant, mobility_support_required, support_notes,
                                relationship, relationship_other
                            ) VALUES (
                                :public_id, :household_id, :display_name,
                                :is_dependant, :mobility_support_required, :support_notes,
                                :relationship, :relationship_other
                            )
                            """
                        ),
                        {
                            "public_id": member.member_id,
                            "household_id": internal_household_id,
                            "display_name": member.display_name,
                            "is_dependant": member.is_dependant,
                            "mobility_support_required": member.mobility_support_required,
                            "support_notes": member.support_notes,
                            "relationship": member.relationship,
                            "relationship_other": member.relationship_other,
                        },
                    )
                    member_ids[member.member_id] = int(result.lastrowid)

                for animal in plan.animals:
                    connection.execute(
                        text(
                            """
                            INSERT INTO animal (
                                public_id, household_id, display_name,
                                category, animal_type, animal_type_other,
                                quantity, support_notes
                            ) VALUES (
                                :public_id, :household_id, :display_name,
                                :category, :animal_type, :animal_type_other,
                                :quantity, :support_notes
                            )
                            """
                        ),
                        {
                            "public_id": animal.animal_id,
                            "household_id": internal_household_id,
                            "display_name": animal.display_name,
                            "category": animal.category,
                            "animal_type": animal.animal_type,
                            "animal_type_other": animal.animal_type_other,
                            "quantity": animal.quantity,
                            "support_notes": animal.support_notes,
                        },
                    )

                transport_ids: dict[str, int] = {}
                for transport in plan.transports:
                    result = connection.execute(
                        text(
                            """
                            INSERT INTO transport (
                                public_id, household_id, transport_type,
                                transport_type_other, display_name
                            ) VALUES (
                                :public_id, :household_id, :transport_type,
                                :transport_type_other, :display_name
                            )
                            """
                        ),
                        {
                            "public_id": transport.transport_id,
                            "household_id": internal_household_id,
                            "transport_type": transport.transport_type,
                            "transport_type_other": transport.transport_type_other,
                            "display_name": transport.display_name,
                        },
                    )
                    internal_transport_id = int(result.lastrowid)
                    transport_ids[transport.transport_id] = internal_transport_id
                    for driver_public_id in transport.driver_member_ids:
                        connection.execute(
                            text(
                                """
                                INSERT INTO transport_driver (transport_id, member_id)
                                VALUES (:transport_id, :member_id)
                                """
                            ),
                            {
                                "transport_id": internal_transport_id,
                                "member_id": self._required_reference(
                                    member_ids,
                                    driver_public_id,
                                    "driver member",
                                ),
                            },
                        )

                destination_ids: dict[str, int] = {}
                for destination in self._plan_destinations(plan):
                    result = connection.execute(
                        text(
                            """
                            INSERT INTO destination (
                                public_id, household_id, display_name, address,
                                unit_number, street_number, street_name,
                                suburb_or_locality, state, postcode, country,
                                latitude, longitude
                            ) VALUES (
                                :public_id, :household_id, :display_name, :address,
                                :unit_number, :street_number, :street_name,
                                :suburb_or_locality, :state, :postcode, :country,
                                :latitude, :longitude
                            )
                            """
                        ),
                        {
                            "public_id": destination.destination_id,
                            "household_id": internal_household_id,
                            "display_name": destination.display_name,
                            "address": destination.address,
                            "unit_number": destination.unit_number,
                            "street_number": destination.street_number,
                            "street_name": destination.street_name,
                            "suburb_or_locality": destination.suburb_or_locality,
                            "state": destination.state,
                            "postcode": destination.postcode,
                            "country": destination.country,
                            "latitude": destination.latitude,
                            "longitude": destination.longitude,
                        },
                    )
                    destination_ids[destination.destination_id] = int(result.lastrowid)

                arrangements = plan.arrangements
                connection.execute(
                    text(
                        """
                        INSERT INTO household_arrangement (
                            household_id, has_private_transport,
                            primary_transport_id, backup_transport_id,
                            primary_destination_id, backup_destination_id,
                            meeting_point
                        ) VALUES (
                            :household_id, :has_private_transport,
                            :primary_transport_id, :backup_transport_id,
                            :primary_destination_id, :backup_destination_id,
                            :meeting_point
                        )
                        """
                    ),
                    {
                        "household_id": internal_household_id,
                        "has_private_transport": plan.has_private_transport,
                        "primary_transport_id": self._optional_reference(
                            transport_ids,
                            arrangements.primary_transport_id,
                            "primary transport",
                        ),
                        "backup_transport_id": self._optional_reference(
                            transport_ids,
                            arrangements.backup_transport_id,
                            "backup transport",
                        ),
                        "primary_destination_id": self._optional_destination_reference(
                            destination_ids,
                            arrangements.primary_destination,
                            "primary destination",
                        ),
                        "backup_destination_id": self._optional_destination_reference(
                            destination_ids,
                            arrangements.backup_destination,
                            "backup destination",
                        ),
                        "meeting_point": arrangements.meeting_point,
                    },
                )

                for responsibility in plan.responsibilities:
                    connection.execute(
                        text(
                            """
                            INSERT INTO responsibility (
                                public_id, household_id, task_name,
                                primary_member_id, backup_member_id
                            ) VALUES (
                                :public_id, :household_id, :task_name,
                                :primary_member_id, :backup_member_id
                            )
                            """
                        ),
                        {
                            "public_id": responsibility.responsibility_id,
                            "household_id": internal_household_id,
                            "task_name": responsibility.task_name,
                            "primary_member_id": self._optional_reference(
                                member_ids,
                                responsibility.primary_member_id,
                                "primary responsibility member",
                            ),
                            "backup_member_id": self._optional_reference(
                                member_ids,
                                responsibility.backup_member_id,
                                "backup responsibility member",
                            ),
                        },
                    )
        except SQLAlchemyError as exc:
            self._raise_database_unavailable(exc)

    def get_plan(self, household_id: str) -> HouseholdPlan:
        try:
            with self.engine.connect() as connection:
                internal_household_id = self._household_internal_id(
                    connection, household_id
                )
                arrangement = connection.execute(
                    text(
                        """
                        SELECT * FROM household_arrangement
                        WHERE household_id = :household_id
                        """
                    ),
                    {"household_id": internal_household_id},
                ).mappings().first()
                if arrangement is None:
                    raise PlanNotFound(
                        f"Household '{household_id}' does not have a plan."
                    )
                return self._load_plan(
                    connection, internal_household_id, arrangement
                )
        except SQLAlchemyError as exc:
            self._raise_database_unavailable(exc)

    def save_location(self, household_id: str, location: HouseholdLocation) -> None:
        try:
            with self.engine.begin() as connection:
                internal_household_id = self._household_internal_id(
                    connection, household_id
                )
                result = connection.execute(
                    text(
                        """
                        UPDATE household_location
                        SET address = :address, canonical_address = :canonical_address,
                            unit_number = :unit_number,
                            street_number = :street_number, street_name = :street_name,
                            suburb_or_locality = :suburb_or_locality, state = :state,
                            postcode = :postcode, country = :country,
                            latitude = :latitude, longitude = :longitude,
                            verification_status = :verification_status,
                            verified_at = :verified_at
                        WHERE household_id = :household_id
                        """
                    ),
                    {
                        "household_id": internal_household_id,
                        "address": location.address,
                        "canonical_address": location.canonical_address,
                        "unit_number": location.unit_number,
                        "street_number": location.street_number,
                        "street_name": location.street_name,
                        "suburb_or_locality": location.suburb_or_locality,
                        "state": location.state,
                        "postcode": location.postcode,
                        "country": location.country,
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                        "verification_status": location.verification_status,
                        "verified_at": self._mysql_datetime(location.verified_at),
                    },
                )
                if result.rowcount == 0:
                    connection.execute(
                        text(
                            """
                            INSERT INTO household_location (
                                household_id, address, canonical_address,
                                unit_number, street_number,
                                street_name, suburb_or_locality, state, postcode,
                                country, latitude, longitude, verification_status,
                                verified_at
                            ) VALUES (
                                :household_id, :address, :canonical_address,
                                :unit_number, :street_number,
                                :street_name, :suburb_or_locality, :state, :postcode,
                                :country, :latitude, :longitude, :verification_status,
                                :verified_at
                            )
                            """
                        ),
                        {
                            "household_id": internal_household_id,
                            "address": location.address,
                            "canonical_address": location.canonical_address,
                            "unit_number": location.unit_number,
                            "street_number": location.street_number,
                            "street_name": location.street_name,
                            "suburb_or_locality": location.suburb_or_locality,
                            "state": location.state,
                            "postcode": location.postcode,
                            "country": location.country,
                            "latitude": location.latitude,
                            "longitude": location.longitude,
                            "verification_status": location.verification_status,
                            "verified_at": self._mysql_datetime(location.verified_at),
                        },
                    )
                connection.execute(
                    text(
                        "DELETE FROM household_location_context "
                        "WHERE household_id = :household_id"
                    ),
                    {"household_id": internal_household_id},
                )
        except SQLAlchemyError as exc:
            self._raise_database_unavailable(exc)

    def get_location(self, household_id: str) -> HouseholdLocation:
        try:
            with self.engine.connect() as connection:
                internal_household_id = self._household_internal_id(
                    connection, household_id
                )
                row = connection.execute(
                    text(
                        """
                        SELECT address, canonical_address, unit_number, street_number, street_name,
                               suburb_or_locality, state, postcode, country,
                               latitude, longitude, verification_status, verified_at
                        FROM household_location
                        WHERE household_id = :household_id
                        """
                    ),
                    {"household_id": internal_household_id},
                ).mappings().first()
                if row is None:
                    raise LocationNotFound(
                        f"Household '{household_id}' does not have a location."
                    )
                return HouseholdLocation(
                    address=row["address"] or "",
                    canonical_address=row["canonical_address"],
                    unit_number=row["unit_number"],
                    street_number=row["street_number"],
                    street_name=row["street_name"],
                    suburb_or_locality=row["suburb_or_locality"],
                    state=row["state"] or "VIC",
                    postcode=row["postcode"],
                    country=row["country"] or "Australia",
                    latitude=(float(row["latitude"]) if row["latitude"] is not None else None),
                    longitude=(float(row["longitude"]) if row["longitude"] is not None else None),
                    verification_status=row["verification_status"] or "unverified",
                    verified_at=self._as_utc(row["verified_at"]),
                )
        except SQLAlchemyError as exc:
            self._raise_database_unavailable(exc)

    def save_location_context(
        self, household_id: str, context: HouseholdLocationContext
    ) -> None:
        try:
            with self.engine.begin() as connection:
                internal_household_id = self._household_internal_id(connection, household_id)
                connection.execute(
                    text(
                        """
                        INSERT INTO household_location_context (
                            household_id, is_bushfire_prone_area, fire_district,
                            fire_history_record_count, fire_history_latest_year,
                            fire_history_latest_date, fire_history_radius_km, generated_at
                        ) VALUES (
                            :household_id, :is_bushfire_prone_area, :fire_district,
                            :fire_history_record_count, :fire_history_latest_year,
                            :fire_history_latest_date, :fire_history_radius_km, :generated_at
                        ) ON DUPLICATE KEY UPDATE
                            is_bushfire_prone_area = VALUES(is_bushfire_prone_area),
                            fire_district = VALUES(fire_district),
                            fire_history_record_count = VALUES(fire_history_record_count),
                            fire_history_latest_year = VALUES(fire_history_latest_year),
                            fire_history_latest_date = VALUES(fire_history_latest_date),
                            fire_history_radius_km = VALUES(fire_history_radius_km),
                            generated_at = VALUES(generated_at)
                        """
                    ),
                    {
                        "household_id": internal_household_id,
                        "is_bushfire_prone_area": context.is_bushfire_prone_area,
                        "fire_district": context.fire_district,
                        "fire_history_record_count": context.fire_history_record_count,
                        "fire_history_latest_year": context.fire_history_latest_year,
                        "fire_history_latest_date": context.fire_history_latest_date,
                        "fire_history_radius_km": context.fire_history_radius_km,
                        "generated_at": self._mysql_datetime(context.generated_at),
                    },
                )
        except SQLAlchemyError as exc:
            self._raise_database_unavailable(exc)

    def get_location_context(self, household_id: str) -> HouseholdLocationContext | None:
        try:
            with self.engine.connect() as connection:
                internal_household_id = self._household_internal_id(connection, household_id)
                row = connection.execute(
                    text("SELECT * FROM household_location_context WHERE household_id = :household_id"),
                    {"household_id": internal_household_id},
                ).mappings().first()
                if row is None:
                    return None
                return HouseholdLocationContext(
                    is_bushfire_prone_area=bool(row["is_bushfire_prone_area"]),
                    fire_district=row["fire_district"],
                    fire_history_record_count=row["fire_history_record_count"],
                    fire_history_latest_year=row["fire_history_latest_year"],
                    fire_history_latest_date=(row["fire_history_latest_date"].isoformat() if row["fire_history_latest_date"] else None),
                    fire_history_radius_km=(float(row["fire_history_radius_km"]) if row["fire_history_radius_km"] is not None else None),
                    generated_at=self._as_utc(row["generated_at"]),
                )
        except SQLAlchemyError as exc:
            self._raise_database_unavailable(exc)

    def save_test_result(
        self, household_id: str, result: ScenarioTestResult
    ) -> None:
        try:
            with self.engine.begin() as connection:
                internal_household_id = self._household_internal_id(
                    connection, household_id
                )
                inserted = connection.execute(
                    text(
                        """
                        INSERT INTO test_run (
                            public_id, household_id, scenario_id, overall_status,
                            result_reason, first_problem_section,
                            first_problem_message, tested_at
                        ) VALUES (
                            :public_id, :household_id, :scenario_id, :overall_status,
                            :result_reason, :first_problem_section,
                            :first_problem_message, :tested_at
                        )
                        """
                    ),
                    {
                        "public_id": result.test_run_id,
                        "household_id": internal_household_id,
                        "scenario_id": result.scenario_id,
                        "overall_status": result.overall_status,
                        "result_reason": result.result_reason,
                        "first_problem_section": (
                            result.first_problem.section
                            if result.first_problem is not None
                            else None
                        ),
                        "first_problem_message": (
                            result.first_problem.message
                            if result.first_problem is not None
                            else None
                        ),
                        "tested_at": self._mysql_datetime(result.tested_at),
                    },
                )
                internal_test_run_id = int(inserted.lastrowid)
                for check_order, check in enumerate(result.checks):
                    connection.execute(
                        text(
                            """
                            INSERT INTO test_check_result (
                                test_run_id, check_order, check_code, status, message
                            ) VALUES (
                                :test_run_id, :check_order, :check_code,
                                :status, :message
                            )
                            """
                        ),
                        {
                            "test_run_id": internal_test_run_id,
                            "check_order": check_order,
                            "check_code": check.check,
                            "status": check.status,
                            "message": check.message,
                        },
                    )
        except SQLAlchemyError as exc:
            self._raise_database_unavailable(exc)

    def get_test_results(self, household_id: str) -> list[ScenarioTestResult]:
        try:
            with self.engine.connect() as connection:
                internal_household_id = self._household_internal_id(
                    connection, household_id
                )
                rows = connection.execute(
                    text(
                        """
                        SELECT * FROM test_run
                        WHERE household_id = :household_id
                        ORDER BY tested_at, test_run_id
                        """
                    ),
                    {"household_id": internal_household_id},
                ).mappings().all()
                return [self._test_result(connection, row) for row in rows]
        except SQLAlchemyError as exc:
            self._raise_database_unavailable(exc)

    def get_test_result(
        self, household_id: str, test_run_id: str
    ) -> ScenarioTestResult:
        try:
            with self.engine.connect() as connection:
                internal_household_id = self._household_internal_id(
                    connection, household_id
                )
                row = connection.execute(
                    text(
                        """
                        SELECT * FROM test_run
                        WHERE household_id = :household_id
                          AND public_id = :public_id
                        """
                    ),
                    {
                        "household_id": internal_household_id,
                        "public_id": test_run_id,
                    },
                ).mappings().first()
                if row is None:
                    raise TestResultNotFound(
                        f"Test result '{test_run_id}' was not found for household "
                        f"'{household_id}'."
                    )
                return self._test_result(connection, row)
        except SQLAlchemyError as exc:
            self._raise_database_unavailable(exc)

    @staticmethod
    def _household_internal_id(
        connection: Connection, household_public_id: str
    ) -> int:
        row = connection.execute(
            text("SELECT household_id FROM household WHERE public_id = :public_id"),
            {"public_id": household_public_id},
        ).first()
        if row is None:
            raise HouseholdNotFound(
                f"Household '{household_public_id}' was not found."
            )
        return int(row[0])

    @staticmethod
    def _plan_destinations(plan: HouseholdPlan) -> list[Destination]:
        return [
            item
            for item in (
                plan.arrangements.primary_destination,
                plan.arrangements.backup_destination,
            )
            if item is not None
        ]

    def _validate_public_id_ownership(
        self,
        connection: Connection,
        household_id: int,
        plan: HouseholdPlan,
    ) -> None:
        entities = {
            "household_member": [item.member_id for item in plan.members],
            "animal": [item.animal_id for item in plan.animals],
            "transport": [item.transport_id for item in plan.transports],
            "destination": [
                item.destination_id for item in self._plan_destinations(plan)
            ],
            "responsibility": [
                item.responsibility_id for item in plan.responsibilities
            ],
        }
        errors: list[str] = []
        for table, public_ids in entities.items():
            for public_id in public_ids:
                row = connection.execute(
                    text(
                        f"SELECT household_id FROM {table} "
                        "WHERE public_id = :public_id"
                    ),
                    {"public_id": public_id},
                ).first()
                if row is not None and int(row[0]) != household_id:
                    errors.append(
                        f"{table} public ID '{public_id}' belongs to another household"
                    )
        if errors:
            raise PlanValidationError(errors)

    @staticmethod
    def _delete_plan_rows(connection: Connection, household_id: int) -> None:
        parameters = {"household_id": household_id}
        for table in (
            "responsibility",
            "household_arrangement",
            "destination",
            "transport",
            "animal",
            "household_member",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE household_id = :household_id"),
                parameters,
            )

    def _load_plan(
        self,
        connection: Connection,
        household_id: int,
        arrangement: RowMapping,
    ) -> HouseholdPlan:
        member_rows = connection.execute(
            text(
                """
                SELECT * FROM household_member
                WHERE household_id = :household_id
                ORDER BY member_id
                """
            ),
            {"household_id": household_id},
        ).mappings().all()
        members = [
            HouseholdMember(
                member_id=row["public_id"],
                display_name=row["display_name"],
                is_dependant=bool(row["is_dependant"]),
                mobility_support_required=bool(row["mobility_support_required"]),
                support_notes=row["support_notes"],
                relationship=row["relationship"],
                relationship_other=row["relationship_other"],
            )
            for row in member_rows
        ]

        animal_rows = connection.execute(
            text(
                """
                SELECT * FROM animal
                WHERE household_id = :household_id
                ORDER BY animal_id
                """
            ),
            {"household_id": household_id},
        ).mappings().all()
        animals = [
            Animal(
                animal_id=row["public_id"],
                category=row["category"],
                animal_type=row["animal_type"],
                display_name=row["display_name"] or "",
                support_notes=row["support_notes"],
                animal_type_other=row["animal_type_other"],
                quantity=int(row["quantity"]),
            )
            for row in animal_rows
        ]

        transport_rows = connection.execute(
            text(
                """
                SELECT * FROM transport
                WHERE household_id = :household_id
                ORDER BY transport_id
                """
            ),
            {"household_id": household_id},
        ).mappings().all()
        drivers = connection.execute(
            text(
                """
                SELECT td.transport_id, hm.public_id
                FROM transport_driver td
                JOIN transport t ON t.transport_id = td.transport_id
                JOIN household_member hm ON hm.member_id = td.member_id
                WHERE t.household_id = :household_id
                ORDER BY td.transport_id, hm.member_id
                """
            ),
            {"household_id": household_id},
        ).all()
        driver_ids: dict[int, list[str]] = {}
        for transport_id, member_public_id in drivers:
            driver_ids.setdefault(int(transport_id), []).append(member_public_id)
        transports = [
            Transport(
                transport_id=row["public_id"],
                transport_type=row["transport_type"],
                display_name=row["display_name"],
                transport_type_other=row["transport_type_other"],
                driver_member_ids=driver_ids.get(int(row["transport_id"]), []),
            )
            for row in transport_rows
        ]
        transport_public_ids = {
            int(row["transport_id"]): row["public_id"] for row in transport_rows
        }

        destination_rows = connection.execute(
            text(
                """
                SELECT * FROM destination
                WHERE household_id = :household_id
                ORDER BY destination_id
                """
            ),
            {"household_id": household_id},
        ).mappings().all()
        destinations = {
            int(row["destination_id"]): Destination(
                destination_id=row["public_id"],
                display_name=row["display_name"],
                address=row["address"],
                unit_number=row["unit_number"],
                street_number=row["street_number"],
                street_name=row["street_name"],
                suburb_or_locality=row["suburb_or_locality"],
                state=row["state"],
                postcode=row["postcode"],
                country=row["country"],
                latitude=(float(row["latitude"]) if row["latitude"] is not None else None),
                longitude=(float(row["longitude"]) if row["longitude"] is not None else None),
            )
            for row in destination_rows
        }

        responsibility_rows = connection.execute(
            text(
                """
                SELECT r.*, primary_member.public_id AS primary_public_id,
                       backup_member.public_id AS backup_public_id
                FROM responsibility r
                LEFT JOIN household_member primary_member
                    ON primary_member.member_id = r.primary_member_id
                LEFT JOIN household_member backup_member
                    ON backup_member.member_id = r.backup_member_id
                WHERE r.household_id = :household_id
                ORDER BY r.responsibility_id
                """
            ),
            {"household_id": household_id},
        ).mappings().all()
        responsibilities = [
            Responsibility(
                responsibility_id=row["public_id"],
                task_name=row["task_name"],
                primary_member_id=row["primary_public_id"],
                backup_member_id=row["backup_public_id"],
            )
            for row in responsibility_rows
        ]

        return HouseholdPlan(
            members=members,
            animals=animals,
            has_private_transport=(
                None
                if arrangement["has_private_transport"] is None
                else bool(arrangement["has_private_transport"])
            ),
            transports=transports,
            arrangements=Arrangements(
                primary_transport_id=self._public_reference(
                    transport_public_ids, arrangement["primary_transport_id"]
                ),
                backup_transport_id=self._public_reference(
                    transport_public_ids, arrangement["backup_transport_id"]
                ),
                primary_destination=self._destination(
                    destinations, arrangement["primary_destination_id"]
                ),
                backup_destination=self._destination(
                    destinations, arrangement["backup_destination_id"]
                ),
                meeting_point=arrangement["meeting_point"],
            ),
            responsibilities=responsibilities,
        )

    @staticmethod
    def _required_reference(
        mapping: dict[str, int], public_id: str, label: str
    ) -> int:
        try:
            return mapping[public_id]
        except KeyError as exc:
            raise PlanValidationError(
                [f"{label} '{public_id}' does not belong to this household plan"]
            ) from exc

    @classmethod
    def _optional_reference(
        cls,
        mapping: dict[str, int],
        public_id: str | None,
        label: str,
    ) -> int | None:
        if public_id is None:
            return None
        return cls._required_reference(mapping, public_id, label)

    @classmethod
    def _optional_destination_reference(
        cls,
        mapping: dict[str, int],
        destination: Destination | None,
        label: str,
    ) -> int | None:
        if destination is None:
            return None
        return cls._required_reference(mapping, destination.destination_id, label)

    @staticmethod
    def _public_reference(
        mapping: dict[int, str], internal_id: int | None
    ) -> str | None:
        if internal_id is None:
            return None
        return mapping.get(int(internal_id))

    @staticmethod
    def _destination(
        mapping: dict[int, Destination], internal_id: int | None
    ) -> Destination | None:
        if internal_id is None:
            return None
        return mapping.get(int(internal_id))

    def _test_result(
        self, connection: Connection, row: RowMapping
    ) -> ScenarioTestResult:
        checks = connection.execute(
            text(
                """
                SELECT check_code, status, message
                FROM test_check_result
                WHERE test_run_id = :test_run_id
                ORDER BY check_order
                """
            ),
            {"test_run_id": row["test_run_id"]},
        ).mappings().all()
        first_problem = None
        if row["first_problem_section"] is not None:
            first_problem = FirstProblem(
                section=row["first_problem_section"],
                message=row["first_problem_message"] or "",
            )
        tested_at = row["tested_at"]
        if tested_at.tzinfo is None:
            tested_at = tested_at.replace(tzinfo=timezone.utc)
        return ScenarioTestResult(
            test_run_id=row["public_id"],
            scenario_id=row["scenario_id"],
            overall_status=row["overall_status"],
            checks=[
                ScenarioCheck(
                    check=check["check_code"],
                    status=check["status"],
                    message=check["message"] or "",
                )
                for check in checks
            ],
            first_problem=first_problem,
            result_reason=row["result_reason"] or "",
            tested_at=tested_at,
        )

    @staticmethod
    def _mysql_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)

    @staticmethod
    def _raise_database_unavailable(exc: SQLAlchemyError) -> None:
        raise DatabaseUnavailable("Application database is unavailable.") from exc
