"""Official BOM Victoria observation client and nearest-station selection."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ftplib import FTP, all_errors as ftp_errors
from io import BytesIO
from math import asin, cos, radians, sin, sqrt
from typing import Callable
from xml.etree import ElementTree

from app.core.exceptions import ExternalDataUnavailable
from app.providers.cache import TTLCache
from app.schemas.households import Weather


BOM_FTP_HOST = "ftp.bom.gov.au"
BOM_FTP_PATH = "/anon/gen/fwo/IDV60920.xml"
BOM_SOURCE_URL = f"ftp://{BOM_FTP_HOST}{BOM_FTP_PATH}"
BOM_COPYRIGHT_URL = "http://www.bom.gov.au/other/copyright.shtml"
BOM_DISCLAIMER_URL = "http://www.bom.gov.au/other/disclaimer.shtml"
BOM_CACHE_SECONDS = 10 * 60
BOM_OBSERVATION_MAX_AGE = timedelta(minutes=75)
BOM_FUTURE_TOLERANCE = timedelta(minutes=5)


@dataclass(frozen=True)
class BOMObservation:
    latitude: float
    longitude: float
    station_name: str
    observed_at: datetime
    temperature_c: float
    relative_humidity: int
    wind_direction: str
    wind_speed_kmh: float


def haversine_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    earth_radius_km = 6371.0088
    lat_a, lat_b = radians(latitude_a), radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = radians(longitude_b - longitude_a)
    value = (
        sin(delta_lat / 2) ** 2
        + cos(lat_a) * cos(lat_b) * sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_km * asin(sqrt(value))


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalDataUnavailable(
            "The BOM observation timestamp is invalid."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExternalDataUnavailable(
            "The BOM observation timestamp is unavailable."
        )
    return parsed


def parse_bom_observations(xml: bytes | str) -> list[BOMObservation]:
    try:
        root = ElementTree.fromstring(xml)
    except (ElementTree.ParseError, ValueError) as exc:
        raise ExternalDataUnavailable("The BOM observation feed is invalid.") from exc
    observations = root.find("observations")
    if observations is None:
        raise ExternalDataUnavailable("The BOM feed contains no observations.")

    parsed: list[BOMObservation] = []
    for station in observations.findall("station"):
        try:
            latitude = float(station.attrib["lat"])
            longitude = float(station.attrib["lon"])
            station_name = (
                station.attrib.get("description")
                or station.attrib.get("stn-name")
                or ""
            ).strip()
        except (KeyError, ValueError):
            continue
        if not station_name:
            continue

        periods = []
        for period in station.findall("period"):
            time_value = period.attrib.get("time-utc")
            level = period.find("./level[@type='surface']")
            if not time_value or level is None:
                continue
            try:
                observed_at = _parse_datetime(time_value)
            except ExternalDataUnavailable:
                continue
            elements = {
                element.attrib.get("type", ""): (element.text or "").strip()
                for element in level.findall("element")
            }
            required = (
                "air_temperature",
                "rel-humidity",
                "wind_dir",
                "wind_spd_kmh",
            )
            if any(not elements.get(name) for name in required):
                continue
            try:
                observation = BOMObservation(
                    latitude=latitude,
                    longitude=longitude,
                    station_name=station_name,
                    observed_at=observed_at,
                    temperature_c=float(elements["air_temperature"]),
                    relative_humidity=int(float(elements["rel-humidity"])),
                    wind_direction=elements["wind_dir"],
                    wind_speed_kmh=float(elements["wind_spd_kmh"]),
                )
            except ValueError:
                continue
            periods.append(observation)
        if periods:
            parsed.append(max(periods, key=lambda item: item.observed_at))

    if not parsed:
        raise ExternalDataUnavailable(
            "The BOM feed contains no usable observations."
        )
    return parsed


def select_nearest_weather(
    observations: list[BOMObservation],
    latitude: float,
    longitude: float,
    *,
    now: datetime | None = None,
) -> Weather:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    valid = []
    for observation in observations:
        age = current - observation.observed_at.astimezone(timezone.utc)
        if age > BOM_OBSERVATION_MAX_AGE or age < -BOM_FUTURE_TOLERANCE:
            continue
        valid.append(observation)
    if not valid:
        raise ExternalDataUnavailable(
            "No sufficiently fresh BOM weather observation is available."
        )
    nearest = min(
        valid,
        key=lambda item: haversine_km(
            latitude, longitude, item.latitude, item.longitude
        ),
    )
    return Weather(
        temperature_c=nearest.temperature_c,
        relative_humidity=nearest.relative_humidity,
        wind_speed_kmh=nearest.wind_speed_kmh,
        wind_direction=nearest.wind_direction,
        observed_at=nearest.observed_at,
        station_name=nearest.station_name,
    )


def _download_bom_xml(timeout_seconds: float) -> bytes:
    target = BytesIO()
    try:
        with FTP(BOM_FTP_HOST, timeout=timeout_seconds) as ftp:
            ftp.login()
            ftp.retrbinary(f"RETR {BOM_FTP_PATH}", target.write)
    except (OSError, *ftp_errors) as exc:
        raise ExternalDataUnavailable(
            "Official BOM weather observations are unavailable."
        ) from exc
    return target.getvalue()


class BOMWeatherClient:
    def __init__(
        self,
        *,
        loader: Callable[[], bytes] | None = None,
        now_provider: Callable[[], datetime] | None = None,
        timeout_seconds: float = 15.0,
        cache_seconds: float = BOM_CACHE_SECONDS,
    ) -> None:
        self.loader = loader or (lambda: _download_bom_xml(timeout_seconds))
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.cache: TTLCache[list[BOMObservation]] = TTLCache(cache_seconds)

    def get_weather(self, latitude: float, longitude: float) -> Weather:
        observations = self.cache.get("IDV60920")
        if observations is None:
            try:
                payload = self.loader()
            except ExternalDataUnavailable:
                raise
            except Exception as exc:
                raise ExternalDataUnavailable(
                    "Official BOM weather observations are unavailable."
                ) from exc
            observations = parse_bom_observations(payload)
            self.cache.set("IDV60920", observations)
        return select_nearest_weather(
            observations,
            latitude,
            longitude,
            now=self.now_provider(),
        )
