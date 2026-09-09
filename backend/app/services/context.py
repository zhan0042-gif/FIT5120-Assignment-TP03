"""Location, local-context aggregation, and preparation timing services."""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from app.core.config import spatial_cache_max_age
from app.core.exceptions import (
    ApplicationError,
    AddressResolutionError,
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
    HistoricalFireMapLocation,
    HistoricalFirePoint,
    HistoricalFirePoints,
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

    def reverse(self, latitude: float, longitude: float) -> list[AddressSuggestion]:
        try:
            return self.address_client.reverse(latitude, longitude, limit=5)
        except ExternalDataUnavailable:
            raise
        except Exception as exc:
            raise ExternalDataUnavailable(
                "Nearby address lookup is unavailable."
            ) from exc


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
            return saved.model_copy(
                update={"verification_message": verification.verification_message}
            )
        location = saved.model_copy(update=verification.model_dump())
        self.repository.save_location(household_id, location)
        return location

    def save_device_location(
        self, household_id: str, latitude: float, longitude: float
    ) -> HouseholdLocation:
        """Persist browser-shared coordinates without inventing an address."""
        if not self.repository.household_exists(household_id):
            raise HouseholdNotFound(f"Household '{household_id}' was not found.")
        location = HouseholdLocation(
            address="",
            location_source="device_location",
            latitude=latitude,
            longitude=longitude,
            verification_status="unverified",
            verification_message=(
                "Current location coordinates were provided by this device; "
                "no postal address was verified."
            ),
        )
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
        except AddressResolutionError as exc:
            return AddressVerification(verification_message=str(exc))
        except ExternalDataUnavailable:
            return AddressVerification(
                verification_message=(
                    "Official address verification is temporarily unavailable."
                )
            )
        except Exception:
            return AddressVerification(
                verification_message="The saved address could not be verified."
            )
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


class HouseholdStaticContextResolver:
    """Resolve cached full context or the narrow district needed for FDR."""

    def __init__(
        self,
        repository: HouseholdRepository,
        spatial_provider: SpatialProvider,
        *,
        cache_max_age: timedelta | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.spatial_provider = spatial_provider
        self.cache_max_age = (
            spatial_cache_max_age() if cache_max_age is None else cache_max_age
        )
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def get_full(
        self,
        household_id: str,
        *,
        require_fire_history: bool = False,
    ) -> tuple[HouseholdLocation, HouseholdLocationContext]:
        location = self._location(
            household_id,
            (
                "Household address is saved, but local context is not available "
                "until the location is verified."
            ),
        )
        cached = self.repository.get_location_context(household_id)
        if (
            cached is None
            or not self._is_fresh(cached)
            or (
                require_fire_history
                and (
                    cached.fire_history_record_count is None
                    or cached.fire_history_radius_km is None
                )
            )
        ):
            spatial = self.spatial_provider.get_context(
                location.latitude, location.longitude
            )
            cached = HouseholdLocationContext(
                is_bushfire_prone_area=spatial.is_bushfire_prone_area,
                fire_district=spatial.fire_district,
                fire_history_record_count=getattr(
                    spatial, "fire_history_record_count", None
                ),
                fire_history_latest_year=getattr(
                    spatial, "fire_history_latest_year", None
                ),
                fire_history_latest_date=getattr(
                    spatial, "fire_history_latest_date", None
                ),
                fire_history_radius_km=getattr(
                    spatial, "fire_history_radius_km", None
                ),
                generated_at=self._now_utc(),
            )
            self.repository.save_location_context(household_id, cached)
        return location, cached

    def get_fire_district(self, household_id: str) -> str:
        location = self._location(
            household_id,
            (
                "Household address is saved, but preparation support is not "
                "available until the location is verified."
            ),
        )
        cached = self.repository.get_location_context(household_id)
        if cached is not None and self._is_fresh(cached):
            return cached.fire_district
        return self.spatial_provider.get_fire_district(
            location.latitude, location.longitude
        )

    def _location(
        self, household_id: str, unverified_message: str
    ) -> HouseholdLocation:
        location = self.repository.get_location(household_id)
        if (
            location.verification_status != "verified"
            and location.location_source != "device_location"
        ) or location.latitude is None or location.longitude is None:
            raise LocationNotVerified(unverified_message)
        return location

    def _is_fresh(self, context: HouseholdLocationContext) -> bool:
        generated_at = context.generated_at
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        else:
            generated_at = generated_at.astimezone(timezone.utc)

        age = self._now_utc() - generated_at
        return timedelta(0) <= age <= self.cache_max_age

    def _now_utc(self) -> datetime:
        now = self.now_provider()
        if now.tzinfo is None or now.utcoffset() is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)


class LocalContextService:
    """Combine verified location context with independent official live data.

    Verified coordinates are required for static Open Data lookup. The
    resulting BPA, fire district, and fire-history snapshot is cached per
    household in MySQL; raw open datasets remain in the Data layer. BOM fire
    danger and weather are requested dynamically and are not part of that
    static snapshot.
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
        self.static_context = HouseholdStaticContextResolver(
            repository, spatial_provider
        )

    def get(self, household_id: str) -> LocalContext:
        try:
            location, cached = self.static_context.get_full(household_id)
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
            try:
                weather = self.weather_client.get_weather(
                    location.latitude, location.longitude
                )
            except ExternalDataUnavailable:
                weather = None
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
        except ApplicationError:
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


class HistoricalFireMapService:
    """Return bounded historical fire context around a saved household."""

    DEFAULT_RADIUS_KM = 20.0

    def __init__(
        self,
        repository: HouseholdRepository,
        spatial_provider: SpatialProvider,
    ) -> None:
        self.static_context = HouseholdStaticContextResolver(
            repository, spatial_provider
        )
        self.spatial_provider = spatial_provider

    def get(self, household_id: str, *, limit: int) -> HistoricalFirePoints:
        try:
            location, context = self.static_context.get_full(
                household_id, require_fire_history=True
            )
            radius_km = (
                context.fire_history_radius_km or self.DEFAULT_RADIUS_KM
            )
            provider_points = self.spatial_provider.get_fire_history_points(
                location.latitude,
                location.longitude,
                radius_km=radius_km,
                limit=limit,
            )
            if len(provider_points) > limit:
                raise ExternalDataUnavailable(
                    "Historical fire map result exceeded its requested limit."
                )
            points = [
                HistoricalFirePoint.model_validate(point)
                for point in provider_points
            ]
            returned_count = len(points)
            total_count = context.fire_history_record_count
            if total_count is None:
                if returned_count == limit:
                    raise ExternalDataUnavailable(
                        "Historical fire total count is unavailable."
                    )
                total_count = returned_count
            if total_count < returned_count:
                raise ExternalDataUnavailable(
                    "Historical fire count is inconsistent with point data."
                )
            return HistoricalFirePoints(
                household_location=HistoricalFireMapLocation(
                    latitude=location.latitude,
                    longitude=location.longitude,
                ),
                search_radius_km=radius_km,
                total_count=total_count,
                returned_count=returned_count,
                truncated=total_count > returned_count,
                points=points,
            )
        except ApplicationError:
            raise
        except Exception as exc:
            raise ExternalDataUnavailable(
                "Historical fire map data is unavailable."
            ) from exc


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
                message=(
                    "Current or forecast fire danger conditions indicate it is time "
                    "to review your household preparedness plan."
                ),
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
        self.static_context = HouseholdStaticContextResolver(
            repository, spatial_provider
        )

    def get(
        self, household_id: str, completion: PlanCompletion
    ) -> PreparationSupport:
        try:
            fire_district = self.static_context.get_fire_district(household_id)
            fire_danger = self.fire_danger_client.get_fire_danger(
                fire_district
            )
            return PreparationTimingService().recommend(fire_danger, completion)
        except ApplicationError:
            raise
        except Exception as exc:
            raise ExternalDataUnavailable(
                "Preparation support provider data is unavailable."
            ) from exc
