"""Official CFA district RSS client and deterministic parser."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
import re
from xml.etree import ElementTree

import httpx

from app.core.exceptions import ExternalDataUnavailable
from app.providers.cache import TTLCache
from app.schemas.households import FireDanger, FireDangerLevel


CFA_FEED_URLS = {
    "Mallee": "https://www.cfa.vic.gov.au/cfa/rssfeed/mallee-firedistrict_rss.xml",
    "Wimmera": "https://www.cfa.vic.gov.au/cfa/rssfeed/wimmera-firedistrict_rss.xml",
    "South West": "https://www.cfa.vic.gov.au/cfa/rssfeed/southwest-firedistrict_rss.xml",
    "Northern Country": "https://www.cfa.vic.gov.au/cfa/rssfeed/northerncountry-firedistrict_rss.xml",
    "North Central": "https://www.cfa.vic.gov.au/cfa/rssfeed/northcentral-firedistrict_rss.xml",
    "Central": "https://www.cfa.vic.gov.au/cfa/rssfeed/central-firedistrict_rss.xml",
    "North East": "https://www.cfa.vic.gov.au/cfa/rssfeed/northeast-firedistrict_rss.xml",
    "East Gippsland": "https://www.cfa.vic.gov.au/cfa/rssfeed/eastgippsland-firedistrict_rss.xml",
    "West and South Gippsland": "https://www.cfa.vic.gov.au/cfa/rssfeed/westandsouthgippsland-firedistrict_rss.xml",
}
CFA_CACHE_SECONDS = 60 * 60

_RATING_MAP: dict[str, FireDangerLevel] = {
    "NO RATING": "No Rating",
    "MODERATE": "Moderate",
    "HIGH": "High",
    "EXTREME": "Extreme",
    "CATASTROPHIC": "Catastrophic",
}
_DISTRICT_LOOKUP = {
    " ".join(name.casefold().split()): name for name in CFA_FEED_URLS
}
_ISSUE_PATTERN = re.compile(
    r"Bureau\s+of\s+Meteorology\s+forecast\s+issued\s+at:\s*"
    r"(?P<time>\d{1,2}:\d{2}\s*[ap]m)\s*"
    r"(?P<zone>A?E[DS]T)\s+on\s+"
    r"(?:[A-Za-z]+,?\s+)?(?P<date>\d{1,2}\s+[A-Za-z]+\s+\d{4})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CFAFeedData:
    daily: tuple[tuple[datetime, FireDangerLevel], ...]
    descriptions: tuple[str, ...]
    source_url: str


def normalize_district(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    try:
        return _DISTRICT_LOOKUP[normalized]
    except KeyError as exc:
        raise ExternalDataUnavailable(
            "The supplied CFA fire district is not supported."
        ) from exc


def _html_text(value: str) -> str:
    text = unescape(value)
    text = re.sub(r"<br\s*/?>|</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def _parse_issue_time(descriptions: list[str]) -> datetime:
    for description in descriptions:
        match = _ISSUE_PATTERN.search(_html_text(description))
        if not match:
            continue
        zone_name = match.group("zone").upper()
        offset_hours = 11 if zone_name in {"EDT", "AEDT"} else 10
        value = f"{match.group('time')} {match.group('date')}"
        try:
            parsed = datetime.strptime(value, "%I:%M %p %d %B %Y")
        except ValueError as exc:
            raise ExternalDataUnavailable(
                "The CFA forecast issue time is invalid."
            ) from exc
        return parsed.replace(tzinfo=timezone(timedelta(hours=offset_hours)))
    raise ExternalDataUnavailable(
        "The CFA forecast issue time is unavailable."
    )


def _parse_rating(description: str, district: str) -> FireDangerLevel:
    text = _html_text(description)
    match = re.search(
        rf"(?:^|\n){re.escape(district)}\s*:\s*([^\n]+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        raise ExternalDataUnavailable(
            f"The CFA forecast does not contain a rating for {district}."
        )
    raw = " ".join(match.group(1).upper().split())
    try:
        return _RATING_MAP[raw]
    except KeyError as exc:
        raise ExternalDataUnavailable(
            "The CFA feed contains an unsupported Fire Danger Rating."
        ) from exc


def parse_cfa_feed(xml: bytes | str, fire_district: str) -> CFAFeedData:
    district = normalize_district(fire_district)
    try:
        root = ElementTree.fromstring(xml)
    except (ElementTree.ParseError, ValueError) as exc:
        raise ExternalDataUnavailable("The CFA forecast feed is invalid.") from exc
    channel = root.find("channel")
    if channel is None:
        raise ExternalDataUnavailable("The CFA forecast feed is invalid.")

    source_url = (channel.findtext("link") or CFA_FEED_URLS[district]).strip()
    daily: list[tuple[datetime, FireDangerLevel]] = []
    descriptions: list[str] = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        description = item.findtext("description") or ""
        descriptions.append(description)
        try:
            forecast_date = datetime.strptime(title, "%A, %d %B %Y")
        except ValueError:
            continue
        daily.append((forecast_date, _parse_rating(description, district)))

    return CFAFeedData(
        daily=tuple(sorted(daily, key=lambda item: item[0])),
        descriptions=tuple(descriptions),
        source_url=source_url,
    )


def parse_cfa_fire_danger(xml: bytes | str, fire_district: str) -> FireDanger:
    district = normalize_district(fire_district)
    feed = parse_cfa_feed(xml, district)
    issue_time = _parse_issue_time(list(feed.descriptions))
    issue_date = issue_time.date()
    relevant = tuple(
        item for item in feed.daily if item[0].date() >= issue_date
    )
    if len(relevant) < 4:
        raise ExternalDataUnavailable(
            "The CFA feed does not contain four current forecast days."
        )
    ratings = [item[1] for item in relevant[:4]]
    return FireDanger(
        today=ratings[0],
        tomorrow=ratings[1],
        day_3=ratings[2],
        day_4=ratings[3],
        source_updated_at=issue_time,
        source_url=feed.source_url,
    )


class CFAFireDangerClient:
    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 10.0,
        cache_seconds: float = CFA_CACHE_SECONDS,
    ) -> None:
        self.http_client = http_client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
        )
        self.cache: TTLCache[FireDanger] = TTLCache(cache_seconds)

    def get_fire_danger(self, fire_district: str) -> FireDanger:
        district = normalize_district(fire_district)
        cached = self.cache.get(district)
        if cached is not None:
            return cached.model_copy(deep=True)
        try:
            response = self.http_client.get(CFA_FEED_URLS[district])
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalDataUnavailable(
                "Official CFA Fire Danger Rating data is unavailable."
            ) from exc
        result = parse_cfa_fire_danger(response.content, district)
        self.cache.set(district, result)
        return result.model_copy(deep=True)
