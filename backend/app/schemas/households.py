"""Household, plan, location, context, and completion API contracts."""

from datetime import datetime
from typing import Annotated

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


class Pet(BaseModel):
    pet_id: EntityId
    display_name: str = ""
    pet_type: str = ""
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
    pets: list[Pet] = Field(default_factory=list)
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
    latitude: float
    longitude: float


class CompletionSection(BaseModel):
    section: str
    status: str


class PlanCompletion(BaseModel):
    overall_status: str
    sections: list[CompletionSection]


class BushfireContext(BaseModel):
    is_bushfire_prone_area: bool
    fire_district: str


class FireDanger(BaseModel):
    today: str
    tomorrow: str
    day_3: str
    day_4: str
    source_updated_at: datetime


class Weather(BaseModel):
    temperature_c: float
    relative_humidity: int
    wind_speed_kmh: float
    wind_direction: str
    forecast_time: datetime


class EnvironmentalContext(BaseModel):
    vegetation: str | None = None
    terrain: str | None = None


class LocalContext(BaseModel):
    location: HouseholdLocation
    bushfire_context: BushfireContext
    fire_danger: FireDanger
    weather: Weather
    environmental_context: EnvironmentalContext


class PreparationSupport(BaseModel):
    status: str
    message: str
    sections_to_review: list[str]
