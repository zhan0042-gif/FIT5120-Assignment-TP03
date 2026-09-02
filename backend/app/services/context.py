"""Location, local-context aggregation, and preparation timing services."""

from datetime import datetime, timedelta, timezone

from app.core.exceptions import (
    ExternalDataUnavailable,
    HouseholdNotFound,
    LocationNotVerified,
)
from app.providers.interfaces import (
    AddressClient,
    FireDangerClient,
    SpatialProvider,
    WeatherClient,
)
from app.repositories.households import HouseholdRepository
from app.schemas.households import (
    AddressSuggestion,
    AddressVerification,
    BushfireContext,
    EnvironmentalContext,
    FireDanger,
    HouseholdLocation,
    HouseholdLocationContext,
    LocalContext,
    PlanCompletion,
    PreparationSupport,
    UnavailableFireDanger,
)


class AddressSuggestionService:
    """Expose provider-backed suggestions without weakening final resolution checks."""

    def __init__(self, address_client: AddressClient) -> None:
        self.address_client = address_client

    def suggest(self, query: str) -> list[AddressSuggestion]:
        if len(query.strip()) < 3:
            return []
        try:
            return self.address_client.suggest(query, limit=8)
        except ExternalDataUnavailable:
            raise
        except Exception as exc:
            raise ExternalDataUnavailable("Address suggestions are unavailable.") from exc


class LocationService:
    """Persist entered household locations before attempting official enrichment.

    Persistence and verification are deliberately separate: a failed Vicmap
    lookup must not discard the address the user entered. Saving a location also
    invalidates any spatial snapshot derived from its previous coordinates.
    """

    def __init__(self, repository: HouseholdRepository, address_client: AddressClient) -> None:
        self.repository = repository
        self.address_client = address_client

    def save(
        self, household_id: str, address: str, selected_address: str | None = None
    ) -> HouseholdLocation:
        if not self.repository.household_exists(household_id):
            raise HouseholdNotFound(f"Household '{household_id}' was not found.")
        saved = HouseholdLocation(address=" ".join(address.split()))
        self.repository.save_location(household_id, saved)
        verification = AddressVerificationService(self.address_client).verify(
            saved.address, selected_address
        )
        if verification.verification_status == "unverified":
            return saved
        location = saved.model_copy(update=verification.model_dump())
        self.repository.save_location(household_id, location)
        return location


class AddressVerificationService:
    """Enrich an address with official canonical fields and coordinates.

    Unverified addresses remain valid saved input but receive no fabricated
    coordinates. Re-verification returns a complete fresh metadata set, so stale
    verification details cannot survive an edited address.
    """

    def __init__(self, address_client: AddressClient) -> None:
        self.address_client = address_client

    def verify(
        self, entered_address: str | None, selected_address: str | None = None
    ) -> AddressVerification:
        if not entered_address or not entered_address.strip():
            return AddressVerification()
        try:
            verified = self.address_client.resolve(selected_address or entered_address)
        except Exception:
            return AddressVerification()
        return AddressVerification(
            verification_status="verified",
            canonical_address=verified.address,
            unit_number=verified.unit_number,
            street_number=verified.street_number,
            street_name=verified.street_name,
            suburb_or_locality=verified.suburb_or_locality,
            state=verified.state,
            postcode=verified.postcode,
            country=verified.country,
            latitude=verified.latitude,
            longitude=verified.longitude,
            verified_at=datetime.now(timezone.utc),
        )


class LocalContextService:
    """Combine verified location context with independent official live data.

    Verified coordinates are required for GeoParquet lookup. The resulting BPA,
    fire district, and fire-history snapshot is cached per household in MySQL;
    raw open datasets remain in the Data layer. BOM fire danger and weather are
    requested dynamically and are not part of that static snapshot.
    """

    def __init__(
        self,
        repository: HouseholdRepository,
        spatial_provider: SpatialProvider,
        fire_danger_client: FireDangerClient,
        weather_client: WeatherClient,
    ) -> None:
        self.repository = repository
        self.spatial_provider = spatial_provider
        self.fire_danger_client = fire_danger_client
        self.weather_client = weather_client

    def get(self, household_id: str) -> LocalContext:
        location = self.repository.get_location(household_id)
        if (
            location.verification_status != "verified"
            or location.latitude is None
            or location.longitude is None
        ):
            raise LocationNotVerified(
                "Household address is saved, but local context is not available until the location is verified."
            )
        try:
            cached = self.repository.get_location_context(household_id)
            if cached is None:
                # Static spatial work is reused until saving a location invalidates
                # the snapshot; normal reads do not repeat the GeoParquet lookup.
                spatial = self.spatial_provider.get_context(
                    location.latitude, location.longitude
                )
                cached = HouseholdLocationContext(
                    is_bushfire_prone_area=spatial.is_bushfire_prone_area,
                    fire_district=spatial.fire_district,
                    fire_history_record_count=getattr(spatial, "fire_history_record_count", None),
                    fire_history_latest_year=getattr(spatial, "fire_history_latest_year", None),
                    fire_history_latest_date=getattr(spatial, "fire_history_latest_date", None),
                    fire_history_radius_km=getattr(spatial, "fire_history_radius_km", None),
                    generated_at=datetime.now(timezone.utc),
                )
                self.repository.save_location_context(household_id, cached)
            try:
                fire_danger = self.fire_danger_client.get_fire_danger(
                    cached.fire_district
                )
                PreparationTimingService().ensure_fresh(
                    fire_danger, datetime.now(timezone.utc)
                )
            except ExternalDataUnavailable:
                # Missing or stale FDR is a valid partial response. Static context
                # and weather remain useful and should not be hidden with it.
                fire_danger = UnavailableFireDanger()
            weather = self.weather_client.get_weather(
                location.latitude, location.longitude
            )
            return LocalContext(
                location=location,
                bushfire_context=BushfireContext(
                    is_bushfire_prone_area=cached.is_bushfire_prone_area,
                    fire_district=cached.fire_district,
                ),
                fire_danger=fire_danger,
                weather=weather,
                environmental_context=EnvironmentalContext(
                    fire_history_summary=self._history_summary(cached),
                ),
            )
        except ExternalDataUnavailable:
            raise
        except Exception as exc:
            raise ExternalDataUnavailable(
                "Local context provider data is unavailable."
            ) from exc

    @staticmethod
    def _history_summary(context: HouseholdLocationContext) -> str | None:
        if context.fire_history_record_count is None or context.fire_history_radius_km is None:
            return None
        radius = f"{context.fire_history_radius_km:g}"
        if context.fire_history_record_count == 0:
            return f"No historical bushfire records were found within {radius} km."
        text = (
            f"{context.fire_history_record_count} historical bushfire record"
            f"{'s' if context.fire_history_record_count != 1 else ''} were found within {radius} km."
        )
        if context.fire_history_latest_year is not None:
            text += f" The latest recorded burn season was {context.fire_history_latest_year}."
        if context.fire_history_latest_date:
            text += f" The most recent dated record was {context.fire_history_latest_date}."
        return text


class PreparationTimingService:
    """Produce rule-based preparation guidance, not a fire prediction.

    Recommendations use authoritative, fresh fire-danger data and may direct the
    household to incomplete plan sections. Stale, future-dated, or unsupported
    source data is rejected rather than interpreted as reassuring advice.
    """

    FDR_SEVERITY = {"No Rating": 0, "Moderate": 1, "High": 2, "Extreme": 3, "Catastrophic": 4}
    FIRE_DANGER_MAX_AGE = timedelta(hours=24)
    FIRE_DANGER_FUTURE_TOLERANCE = timedelta(minutes=5)

    def recommend(
        self,
        fire_danger: FireDanger,
        completion: PlanCompletion,
        *,
        now: datetime | None = None,
    ) -> PreparationSupport:
        self.ensure_fresh(fire_danger, now or datetime.now(timezone.utc))
        incomplete = [
            item.section
            for item in completion.sections
            if item.status == "needs_information"
        ]
        try:
            levels = [
                self.FDR_SEVERITY[value]
                for value in (
                    fire_danger.today,
                    fire_danger.tomorrow,
                    fire_danger.day_3,
                    fire_danger.day_4,
                )
            ]
        except KeyError as exc:
            raise ExternalDataUnavailable(
                f"Unsupported Fire Danger Rating supplied: {exc.args[0]}"
            ) from exc

        escalating = max(levels[1:], default=levels[0]) > levels[0]
        serious = max(levels) >= self.FDR_SEVERITY["High"]
        if escalating or serious:
            return PreparationSupport(
                status="review_recommended",
                message="Local fire conditions are expected to become more serious.",
                sections_to_review=incomplete,
            )
        if incomplete:
            return PreparationSupport(
                status="review_recommended",
                message="Review the incomplete sections of your household plan.",
                sections_to_review=incomplete,
            )
        return PreparationSupport(
            status="up_to_date",
            message="No immediate plan review is recommended.",
            sections_to_review=[],
        )

    def ensure_fresh(self, fire_danger: FireDanger, now: datetime) -> None:
        updated_at = fire_danger.source_updated_at
        if updated_at.tzinfo is None or updated_at.utcoffset() is None:
            raise ExternalDataUnavailable(
                "Fire Danger Rating issue time is unavailable."
            )
        age = now.astimezone(timezone.utc) - updated_at.astimezone(timezone.utc)
        if age > self.FIRE_DANGER_MAX_AGE:
            raise ExternalDataUnavailable(
                "Fire Danger Rating data is stale; preparation support is unavailable."
            )
        if age < -self.FIRE_DANGER_FUTURE_TOLERANCE:
            raise ExternalDataUnavailable(
                "Fire Danger Rating issue time is invalid."
            )


class PreparationSupportService:
    """Combine plan completion and official FDR without depending on weather.

    This boundary keeps preparation advice unavailable when the address cannot
    be located or the official fire-danger source is not authoritative enough.
    """

    def __init__(
        self,
        repository: HouseholdRepository,
        spatial_provider: SpatialProvider,
        fire_danger_client: FireDangerClient,
    ) -> None:
        self.repository = repository
        self.spatial_provider = spatial_provider
        self.fire_danger_client = fire_danger_client

    def get(
        self, household_id: str, completion: PlanCompletion
    ) -> PreparationSupport:
        location = self.repository.get_location(household_id)
        if (
            location.verification_status != "verified"
            or location.latitude is None
            or location.longitude is None
        ):
            raise LocationNotVerified(
                "Household address is saved, but preparation support is not available until the location is verified."
            )
        try:
            spatial = self.spatial_provider.get_context(
                location.latitude, location.longitude
            )
            fire_danger = self.fire_danger_client.get_fire_danger(
                spatial.fire_district
            )
            return PreparationTimingService().recommend(fire_danger, completion)
        except ExternalDataUnavailable:
            raise
        except Exception as exc:
            raise ExternalDataUnavailable(
                "Preparation support provider data is unavailable."
            ) from exc
