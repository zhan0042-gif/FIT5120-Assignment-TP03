"""Household, plan, location, context, and completion API contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HouseholdCreate(BaseModel):
    """Optional metadata accepted when creating a household."""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class HouseholdCreated(BaseModel):
    household_id: str


class HouseholdMember(BaseModel):
    member_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    is_dependant: bool
    mobility_support_required: bool
    support_notes: str | None = None


class Pet(BaseModel):
    pet_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    pet_type: str = Field(min_length=1)
    support_notes: str | None = None


class Transport(BaseModel):
    transport_id: str = Field(min_length=1)
    transport_type: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    driver_member_ids: list[str] = Field(default_factory=list)


class Destination(BaseModel):
    destination_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    address: str = Field(min_length=1)


class Arrangements(BaseModel):
    primary_transport_id: str
    backup_transport_id: str | None = None
    primary_destination: Destination
    backup_destination: Destination | None = None
    meeting_point: str = Field(min_length=1)


class Responsibility(BaseModel):
    responsibility_id: str = Field(min_length=1)
    task_name: str = Field(min_length=1)
    primary_member_id: str
    backup_member_id: str | None = None


class HouseholdPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    members: list[HouseholdMember] = Field(min_length=1)
    pets: list[Pet] = Field(default_factory=list)
    transports: list[Transport] = Field(min_length=1)
    arrangements: Arrangements
    responsibilities: list[Responsibility] = Field(default_factory=list)


class LocationRequest(BaseModel):
    address: str = Field(min_length=1, max_length=300)


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

