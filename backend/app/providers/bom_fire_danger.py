"""Official BOM IDV18555 Victorian Fire Danger Rating client."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ftplib import FTP, all_errors as ftp_errors
from io import BytesIO
from typing import Callable
from xml.etree import ElementTree

from app.core.exceptions import ExternalDataUnavailable
from app.providers.cache import TTLCache
from app.schemas.households import FireDanger, FireDangerLevel


BOM_FDR_FTP_HOST = "ftp.bom.gov.au"
BOM_FDR_FTP_PATH = "/anon/gen/fwo/IDV18555.xml"
BOM_FDR_SOURCE_URL = f"ftp://{BOM_FDR_FTP_HOST}{BOM_FDR_FTP_PATH}"
BOM_FDR_CACHE_SECONDS = 60 * 60
BOM_FDR_MAX_AGE = timedelta(hours=24)
BOM_FDR_FUTURE_TOLERANCE = timedelta(minutes=5)

BOM_FIRE_DISTRICTS = (
    "Mallee",
    "Wimmera",
    "South West",
    "Northern Country",
    "North Central",
    "Central",
    "North East",
    "East Gippsland",
    "West and South Gippsland",
)
_DISTRICT_LOOKUP = {
    " ".join(name.casefold().split()): name for name in BOM_FIRE_DISTRICTS
}
_RATING_LOOKUP: dict[str, FireDangerLevel] = {
    "NO RATING": "No Rating",
    "MODERATE": "Moderate",
    "HIGH": "High",
    "EXTREME": "Extreme",
    "CATASTROPHIC": "Catastrophic",
}


@dataclass(frozen=True)
class BOMFireDangerForecast:
    source_updated_at: datetime
    dates: tuple[datetime, ...]
    ratings: dict[str, tuple[FireDangerLevel, ...]]
    fire_behaviour_indices: dict[str, tuple[int | None, ...]]


def normalize_bom_fire_district(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    try:
        return _DISTRICT_LOOKUP[normalized]
    except KeyError as exc:
        raise ExternalDataUnavailable(
            "The supplied BOM fire district is not supported."
        ) from exc


def _aware_datetime(value: str, message: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalDataUnavailable(message) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExternalDataUnavailable(message)
    return parsed


def _canonical_rating(value: str) -> FireDangerLevel:
    normalized = " ".join(value.upper().split())
    try:
        return _RATING_LOOKUP[normalized]
    except KeyError as exc:
        raise ExternalDataUnavailable(
            "The BOM product contains an unsupported Fire Danger Rating."
        ) from exc


def parse_bom_fire_danger_product(xml: bytes | str) -> BOMFireDangerForecast:
    try:
        root = ElementTree.fromstring(xml)
    except (ElementTree.ParseError, ValueError) as exc:
        raise ExternalDataUnavailable(
            "The BOM Fire Danger Rating product is invalid."
        ) from exc

    if (root.findtext("./amoc/identifier") or "").strip() != "IDV18555":
        raise ExternalDataUnavailable(
            "The BOM Fire Danger Rating product identifier is invalid."
        )
    issue_value = (root.findtext("./amoc/issue-time-local") or "").strip()
    if not issue_value:
        raise ExternalDataUnavailable(
            "The BOM Fire Danger Rating issue time is unavailable."
        )
    issue_time = _aware_datetime(
        issue_value,
        "The BOM Fire Danger Rating issue time is invalid.",
    )

    parsed: dict[
        str, tuple[tuple[datetime, FireDangerLevel, int | None], ...]
    ] = {}
    for area in root.findall("./forecast/area[@type='fire-district']"):
        description = area.attrib.get("description", "")
        district = _DISTRICT_LOOKUP.get(" ".join(description.casefold().split()))
        if district is None:
            continue
        if district in parsed:
            raise ExternalDataUnavailable(
                f"The BOM product contains duplicate data for {district}."
            )
        periods: list[tuple[datetime, FireDangerLevel, int | None]] = []
        for period in area.findall("forecast-period"):
            start_value = (period.attrib.get("start-time-local") or "").strip()
            rating_value = period.findtext("./text[@type='fire_danger']")
            if not start_value or not rating_value:
                raise ExternalDataUnavailable(
                    f"The BOM product contains incomplete data for {district}."
                )
            start = _aware_datetime(
                start_value,
                "The BOM Fire Danger Rating forecast time is invalid.",
            )
            fbi_value = period.findtext(
                "./element[@type='fire_behaviour_index']"
            )
            try:
                fbi = int(fbi_value) if fbi_value is not None else None
            except ValueError as exc:
                raise ExternalDataUnavailable(
                    "The BOM product contains an invalid Fire Behaviour Index."
                ) from exc
            periods.append((start, _canonical_rating(rating_value), fbi))
        parsed[district] = tuple(sorted(periods, key=lambda item: item[0]))

    if set(parsed) != set(BOM_FIRE_DISTRICTS):
        raise ExternalDataUnavailable(
            "The BOM product does not contain all nine Victorian fire districts."
        )

    expected_dates: tuple[datetime, ...] | None = None
    ratings: dict[str, tuple[FireDangerLevel, ...]] = {}
    indices: dict[str, tuple[int | None, ...]] = {}
    for district in BOM_FIRE_DISTRICTS:
        periods = parsed[district]
        if len(periods) != 4:
            raise ExternalDataUnavailable(
                f"The BOM product does not contain exactly four forecast days for {district}."
            )
        dates = tuple(item[0] for item in periods)
        local_dates = tuple(item.date() for item in dates)
        if len(set(local_dates)) != 4 or any(
            later != earlier + timedelta(days=1)
            for earlier, later in zip(local_dates, local_dates[1:])
        ):
            raise ExternalDataUnavailable(
                f"The BOM product contains invalid forecast days for {district}."
            )
        issue_date = issue_time.date()
        if local_dates[0] not in {issue_date, issue_date + timedelta(days=1)}:
            raise ExternalDataUnavailable(
                "The BOM product does not begin with the current or next forecast day."
            )
        if expected_dates is None:
            expected_dates = dates
        elif tuple(item.date() for item in expected_dates) != local_dates:
            raise ExternalDataUnavailable(
                "The BOM product contains inconsistent district forecast days."
            )
        ratings[district] = tuple(item[1] for item in periods)
        indices[district] = tuple(item[2] for item in periods)

    assert expected_dates is not None
    return BOMFireDangerForecast(
        source_updated_at=issue_time,
        dates=expected_dates,
        ratings=ratings,
        fire_behaviour_indices=indices,
    )


def ensure_bom_fire_danger_is_fresh(
    forecast: BOMFireDangerForecast,
    now: datetime,
) -> None:
    age = now.astimezone(timezone.utc) - forecast.source_updated_at.astimezone(
        timezone.utc
    )
    if age > BOM_FDR_MAX_AGE:
        raise ExternalDataUnavailable(
            "BOM Fire Danger Rating data is stale."
        )
    if age < -BOM_FDR_FUTURE_TOLERANCE:
        raise ExternalDataUnavailable(
            "The BOM Fire Danger Rating issue time is invalid."
        )


def fire_danger_for_district(
    forecast: BOMFireDangerForecast,
    fire_district: str,
) -> FireDanger:
    district = normalize_bom_fire_district(fire_district)
    values = forecast.ratings[district]
    return FireDanger(
        today=values[0],
        tomorrow=values[1],
        day_3=values[2],
        day_4=values[3],
        source_updated_at=forecast.source_updated_at,
        source_url=BOM_FDR_SOURCE_URL,
    )


def _download_bom_fire_danger_xml(timeout_seconds: float) -> bytes:
    target = BytesIO()
    try:
        with FTP(BOM_FDR_FTP_HOST, timeout=timeout_seconds) as ftp:
            ftp.login()
            ftp.retrbinary(f"RETR {BOM_FDR_FTP_PATH}", target.write)
    except (OSError, *ftp_errors) as exc:
        raise ExternalDataUnavailable(
            "Official BOM Fire Danger Rating data is unavailable."
        ) from exc
    return target.getvalue()


class BOMFireDangerClient:
    def __init__(
        self,
        *,
        loader: Callable[[], bytes] | None = None,
        now_provider: Callable[[], datetime] | None = None,
        timeout_seconds: float = 15.0,
        cache_seconds: float = BOM_FDR_CACHE_SECONDS,
    ) -> None:
        self.loader = loader or (
            lambda: _download_bom_fire_danger_xml(timeout_seconds)
        )
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.cache: TTLCache[BOMFireDangerForecast] = TTLCache(cache_seconds)

    def get_fire_danger(self, fire_district: str) -> FireDanger:
        district = normalize_bom_fire_district(fire_district)
        forecast = self.cache.get("IDV18555")
        if forecast is None:
            try:
                payload = self.loader()
            except ExternalDataUnavailable:
                raise
            except Exception as exc:
                raise ExternalDataUnavailable(
                    "Official BOM Fire Danger Rating data is unavailable."
                ) from exc
            forecast = parse_bom_fire_danger_product(payload)
            ensure_bom_fire_danger_is_fresh(forecast, self.now_provider())
            self.cache.set("IDV18555", forecast)
        else:
            ensure_bom_fire_danger_is_fresh(forecast, self.now_provider())
        return fire_danger_for_district(forecast, district)
