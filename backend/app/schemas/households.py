"""Household, plan, location, context, and completion API contracts."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


EntityId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
]
NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
CompletionSectionName = Literal[
    "household_profile",
    "transport",
    "backup_transport",
    "primary_destination",
    "backup_destination",
    "responsibilities",
]
FireDangerLevel = Literal[
    "No Rating", "Moderate", "High", "Extreme", "Catastrophic"
]


class HouseholdCreate(BaseModel):
    """Optional metadata accepted when creating a household."""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class HouseholdCreated(BaseModel):
    household_id: str


class HouseholdMember(BaseModel):
    member_id: EntityId
    display_name: str = ""
    is_dependant: bool
    mobility_support_required: bool
    support_notes: str | None = None


class Animal(BaseModel):
    animal_id: EntityId
    category: Literal["pet", "livestock"]
    animal_type: str = ""
    display_name: str = ""
    support_notes: str | None = None


class Transport(BaseModel):
    transport_id: EntityId
    transport_type: NonBlankText
    display_name: str | None = None
    driver_member_ids: list[EntityId] = Field(default_factory=list)


class Destination(BaseModel):
    destination_id: EntityId
    display_name: str = ""
    address: str | None = None


class Arrangements(BaseModel):
    primary_transport_id: EntityId | None = None
    backup_transport_id: EntityId | None = None
    primary_destination: Destination | None = None
    backup_destination: Destination | None = None
    meeting_point: str | None = None


class Responsibility(BaseModel):
    responsibility_id: EntityId
    task_name: str = ""
    primary_member_id: EntityId | None = None
    backup_member_id: EntityId | None = None


class HouseholdPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    members: list[HouseholdMember] = Field(default_factory=list)
    animals: list[Animal] = Field(default_factory=list)
    transports: list[Transport] = Field(default_factory=list)
    arrangements: Arrangements = Field(default_factory=Arrangements)
    responsibilities: list[Responsibility] = Field(default_factory=list)


class LocationRequest(BaseModel):
    address: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
    ]


class HouseholdLocation(BaseModel):
    address: str
    latitude: Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
    longitude: Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


class CompletionSection(BaseModel):
    section: CompletionSectionName
    status: Literal["complete", "needs_information"]


class ImmediateCheck(BaseModel):
    check: Literal[
        "missing_backup_transport",
        "missing_backup_destination",
        "missing_backup_person",
        "shared_transport_resource",
    ]
    section: Literal[
        "backup_transport",
        "backup_destination",
        "responsibilities",
    ]
    status: Literal["warning"] = "warning"
    message: str


class PlanCompletion(BaseModel):
    overall_status: Literal["complete", "needs_information"]
    sections: list[CompletionSection]
    immediate_checks: list[ImmediateCheck] = Field(default_factory=list)


class BushfireContext(BaseModel):
    is_bushfire_prone_area: bool
    fire_district: NonBlankText


class FireDanger(BaseModel):
    today: FireDangerLevel
    tomorrow: FireDangerLevel
    day_3: FireDangerLevel
    day_4: FireDangerLevel
    source_updated_at: datetime


class Weather(BaseModel):
    temperature_c: float
    relative_humidity: int
    wind_speed_kmh: float
    wind_direction: str
    forecast_time: datetime


class EnvironmentalContext(BaseModel):
    fire_history_summary: str | None = None
    vegetation_context: str | None = None
    terrain_context: str | None = None


class LocalContext(BaseModel):
    location: HouseholdLocation
    bushfire_context: BushfireContext
    fire_danger: FireDanger
    weather: Weather
    environmental_context: EnvironmentalContext


class PreparationSupport(BaseModel):
    status: Literal["up_to_date", "review_recommended"]
    message: str
    sections_to_review: list[CompletionSectionName]
