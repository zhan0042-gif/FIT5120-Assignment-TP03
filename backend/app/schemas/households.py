"""Household, plan, location, context, and completion API contracts."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


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
Relationship = Literal[
    "self",
    "partner",
    "child",
    "parent",
    "grandparent",
    "sibling",
    "other_relative",
    "friend_or_housemate",
    "carer",
    "other",
]
AnimalType = Literal[
    "dog",
    "cat",
    "bird",
    "rabbit",
    "reptile",
    "horse",
    "cattle",
    "sheep",
    "goat",
    "alpaca",
    "poultry",
    "other",
]
TransportType = Literal["car", "ute", "van", "motorbike", "truck", "other"]


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
    relationship: Relationship | None = None
    relationship_other: str | None = Field(default=None, max_length=100)


class Animal(BaseModel):
    animal_id: EntityId
    category: Literal["pet", "livestock"]
    animal_type: AnimalType = "other"
    animal_type_other: str | None = Field(default=None, max_length=100)
    display_name: str = ""
    support_notes: str | None = None
    quantity: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def type_matches_category(self) -> "Animal":
        allowed = {
            "pet": {"dog", "cat", "bird", "rabbit", "reptile", "other"},
            "livestock": {"horse", "cattle", "sheep", "goat", "alpaca", "poultry", "other"},
        }
        if self.animal_type not in allowed[self.category]:
            raise ValueError(
                f"Animal type '{self.animal_type}' is not valid for category '{self.category}'."
            )
        return self


class Transport(BaseModel):
    transport_id: EntityId
    transport_type: TransportType
    display_name: str | None = None
    transport_type_other: str | None = Field(default=None, max_length=100)
    driver_member_ids: list[EntityId] = Field(default_factory=list)


class Destination(BaseModel):
    """A named destination with optional, non-blocking official address metadata."""

    destination_id: EntityId
    display_name: str = ""
    address: str | None = None
    canonical_address: str | None = None
    unit_number: str | None = Field(default=None, max_length=30)
    street_number: str | None = Field(default=None, max_length=30)
    street_name: str | None = Field(default=None, max_length=150)
    suburb_or_locality: str | None = Field(default=None, max_length=150)
    state: Literal["VIC"] | None = None
    postcode: str | None = Field(default=None, pattern=r"^\d{4}$")
    country: Literal["Australia"] | None = "Australia"
    latitude: Annotated[float | None, Field(ge=-90, le=90, allow_inf_nan=False)] = None
    longitude: Annotated[float | None, Field(ge=-180, le=180, allow_inf_nan=False)] = None
    verification_status: Literal["verified", "unverified"] = "unverified"
    verified_at: datetime | None = None
    selected_address: str | None = Field(default=None, exclude=True)


class AddressVerification(BaseModel):
    """Official enrichment result that can be applied to any saved address."""

    verification_status: Literal["verified", "unverified"] = "unverified"
    verification_message: str | None = None
    canonical_address: str | None = None
    unit_number: str | None = None
    street_number: str | None = None
    street_name: str | None = None
    suburb_or_locality: str | None = None
    state: Literal["VIC"] | None = None
    postcode: str | None = None
    country: Literal["Australia"] | None = None
    latitude: Annotated[float | None, Field(ge=-90, le=90, allow_inf_nan=False)] = None
    longitude: Annotated[float | None, Field(ge=-180, le=180, allow_inf_nan=False)] = None
    verified_at: datetime | None = None


class BackupArrangement(BaseModel):
    """One ordered fallback transport and/or destination option."""

    transport_id: EntityId | None = None
    destination: Destination | None = None


class Arrangements(BaseModel):
    """One primary arrangement plus an ordered list of independent fallbacks."""

    model_config = ConfigDict(extra="forbid")

    primary_transport_id: EntityId | None = None
    primary_destination: Destination | None = None
    backup_arrangements: list[BackupArrangement] = Field(default_factory=list)
    meeting_point: str | None = None


class Responsibility(BaseModel):
    responsibility_id: EntityId
    task_name: str = ""
    primary_member_id: EntityId | None = None
    backup_member_id: EntityId | None = None


class HouseholdPlan(BaseModel):
    """The saveable household aggregate, including valid but incomplete plans."""

    model_config = ConfigDict(extra="forbid")

    members: list[HouseholdMember] = Field(default_factory=list)
    animals: list[Animal] = Field(default_factory=list)
    has_private_transport: bool | None = None
    transports: list[Transport] = Field(default_factory=list)
    arrangements: Arrangements = Field(default_factory=Arrangements)
    responsibilities: list[Responsibility] = Field(default_factory=list)

    @model_validator(mode="after")
    def private_transport_answer_matches_resources(self) -> "HouseholdPlan":
        # Incompleteness is allowed, but an explicit "no private transport"
        # answer cannot coexist with private vehicle records in the aggregate.
        if self.has_private_transport is False and any(
            transport.transport_type in {"car", "ute", "van", "motorbike", "truck"}
            for transport in self.transports
        ):
            raise ValueError(
                "Private vehicle records require has_private_transport to be true."
            )
        return self


class LocationRequest(BaseModel):
    """Entered address plus an optional candidate explicitly selected in the UI."""

    address: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
    ]
    selected_address: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
    ] = None


class DeviceLocationRequest(BaseModel):
    """Coordinates explicitly shared by the browser after a user gesture."""

    latitude: Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
    longitude: Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


class CoordinateLookupRequest(BaseModel):
    """Coordinates used for a non-verifying nearby-address lookup."""

    latitude: Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
    longitude: Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


class HouseholdLocation(BaseModel):
    """Saved postal address or explicit browser-provided coordinates."""

    address: str
    location_source: Literal["address", "device_location"] = "address"
    canonical_address: str | None = None
    unit_number: str | None = None
    street_number: str | None = None
    street_name: str | None = None
    suburb_or_locality: str | None = None
    state: Literal["VIC"] = "VIC"
    postcode: str | None = Field(default=None, pattern=r"^\d{4}$")
    country: Literal["Australia"] = "Australia"
    latitude: Annotated[float | None, Field(ge=-90, le=90, allow_inf_nan=False)] = None
    longitude: Annotated[float | None, Field(ge=-180, le=180, allow_inf_nan=False)] = None
    verification_status: Literal["verified", "unverified"] = "unverified"
    verification_message: str | None = None
    verified_at: datetime | None = None


class AddressSuggestion(HouseholdLocation):
    """A canonical Vicmap address candidate returned by autocomplete."""


class HouseholdLocationContext(BaseModel):
    """Cached per-household spatial facts derived from processed open datasets."""

    is_bushfire_prone_area: bool
    fire_district: NonBlankText
    fire_history_record_count: int | None = Field(default=None, ge=0)
    fire_history_latest_year: int | None = None
    fire_history_latest_date: str | None = None
    fire_history_radius_km: float | None = Field(default=None, gt=0)
    generated_at: datetime


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
    """A derived snapshot of section completeness and non-blocking warnings."""

    overall_status: Literal["complete", "needs_information"]
    sections: list[CompletionSection]
    immediate_checks: list[ImmediateCheck] = Field(default_factory=list)


class BushfireContext(BaseModel):
    is_bushfire_prone_area: bool
    fire_district: NonBlankText


class FireDanger(BaseModel):
    availability: Literal["available"] = "available"
    today: FireDangerLevel
    tomorrow: FireDangerLevel
    day_3: FireDangerLevel
    day_4: FireDangerLevel
    source_updated_at: datetime
    source_url: str | None = None
    message: None = None


class UnavailableFireDanger(BaseModel):
    availability: Literal["unavailable"] = "unavailable"
    today: None = None
    tomorrow: None = None
    day_3: None = None
    day_4: None = None
    source_updated_at: None = None
    source_url: None = None
    message: NonBlankText = (
        "Current fire danger information is not available from the official source."
    )


FireDangerContext = Annotated[
    FireDanger | UnavailableFireDanger,
    Field(discriminator="availability"),
]


class Weather(BaseModel):
    temperature_c: float
    relative_humidity: int
    wind_speed_kmh: float
    wind_direction: str
    observed_at: datetime
    station_name: NonBlankText


class EnvironmentalContext(BaseModel):
    fire_history_summary: str | None = None
    vegetation_context: str | None = None
    terrain_context: str | None = None


class LocalContext(BaseModel):
    """API aggregate of saved location, static context, FDR, and weather."""

    location: HouseholdLocation
    bushfire_context: BushfireContext
    fire_danger: FireDangerContext
    weather: Weather | None
    environmental_context: EnvironmentalContext


class PreparationSupport(BaseModel):
    """Rule-based review guidance produced only from usable official FDR data."""

    status: Literal["up_to_date", "review_recommended"]
    message: str
    sections_to_review: list[CompletionSectionName]
