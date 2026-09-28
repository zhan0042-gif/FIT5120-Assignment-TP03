"""Victorian Unplanned Road Disruptions Open Data provider."""

from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any

import httpx

from app.core.exceptions import ExternalDataUnavailable
from app.schemas.travel_disruptions import RoadDisruption


ROAD_DISRUPTIONS_URL = (
    "https://api.opendata.transport.vic.gov.au"
    "/api/opendata/roads/disruptions/unplanned/v3"
)

DEFAULT_PAGE_LIMIT = 100
MAX_PAGES = 20


def _haversine_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Great-circle distance between two WGS84 points."""

    earth_radius_km = 6371.0088

    lat1 = radians(latitude_a)
    lon1 = radians(longitude_a)
    lat2 = radians(latitude_b)
    lon2 = radians(longitude_b)

    d_lat = lat2 - lat1
    d_lon = lon2 - lon1

    h = (
        sin(d_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    )

    return 2 * earth_radius_km * asin(sqrt(h))


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    cleaned = value.strip()

    try:
        return datetime.fromisoformat(
            cleaned.replace("Z", "+00:00")
        )
    except ValueError:
        return None


def _normalise_text(value: Any) -> str | None:
    """
    Convert values returned by the DTP API into readable text.

    Some DTP fields, such as impact, may be dictionaries rather than
    simple strings.
    """

    if value is None:
        return None

    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, dict):
        parts: list[str] = []

        for key, item in value.items():
            if item is None:
                continue

            if isinstance(item, str):
                item = item.strip()

                if not item:
                    continue

            if isinstance(item, (str, int, float, bool)):
                label = (
                    str(key)
                    .replace("_", " ")
                    .strip()
                )

                parts.append(
                    f"{label}: {item}"
                )

            elif isinstance(item, (dict, list)):
                nested = _normalise_text(item)

                if nested:
                    label = (
                        str(key)
                        .replace("_", " ")
                        .strip()
                    )

                    parts.append(
                        f"{label}: {nested}"
                    )

        return "; ".join(parts) or None

    if isinstance(value, list):
        parts: list[str] = []

        for item in value:
            text = _normalise_text(item)

            if text:
                parts.append(text)

        return "; ".join(parts) or None

    return str(value)


def _flatten_points(
    coordinates: Any,
) -> list[tuple[float, float]]:
    """
    Convert Point/LineString-like GeoJSON coordinates to lat/lon points.
    """

    points: list[tuple[float, float]] = []

    def walk(value: Any) -> None:
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            longitude = float(value[0])
            latitude = float(value[1])

            if (
                -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                points.append(
                    (latitude, longitude)
                )

            return

        if isinstance(value, list):
            for item in value:
                walk(item)

    walk(coordinates)

    return points


def _distance_to_geometry_km(
    latitude: float,
    longitude: float,
    coordinates: Any,
) -> float | None:
    """
    Minimum distance to one of the coordinates representing the disruption.

    This is intentionally a proximity measure, not route-intersection logic.
    """

    points = _flatten_points(coordinates)

    if not points:
        return None

    return min(
        _haversine_km(
            latitude,
            longitude,
            point_lat,
            point_lon,
        )
        for point_lat, point_lon in points
    )


class DisabledRoadDisruptionClient:
    """Report that this optional integration has not been configured."""

    def nearby_disruptions(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
    ) -> list[RoadDisruption]:
        raise ExternalDataUnavailable(
            "Current road-disruption information is unavailable because "
            "VIC_ROAD_DISRUPTIONS_API_KEY is not configured."
        )


class VictorianRoadDisruptionClient:
    """
    Read near-real-time Victorian road disruptions from DTP Open Data.
    """

    def __init__(
        self,
        *,
        api_key: str | None,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise RuntimeError(
                "VIC_ROAD_DISRUPTIONS_API_KEY is required "
                "when APP_DATA_MODE=live."
            )

        self._api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds

        self._client = http_client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
        )

    def nearby_disruptions(
        self,
        latitude: float,
        longitude: float,
        *,
        radius_km: float,
    ) -> list[RoadDisruption]:
        if radius_km <= 0:
            raise ValueError(
                "radius_km must be greater than 0."
            )

        records = self._fetch_all()

        disruptions: list[RoadDisruption] = []

        for record in records:
            parsed = self._parse_record(
                record,
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km,
            )

            if parsed is not None:
                disruptions.append(parsed)

        disruptions.sort(
            key=lambda item: (
                item.distance_km
                if item.distance_km is not None
                else float("inf")
            )
        )

        return disruptions

    def _fetch_all(
        self,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []

        for page in range(
            1,
            MAX_PAGES + 1,
        ):
            try:
                response = self._client.get(
                    ROAD_DISRUPTIONS_URL,
                    headers={
                        "KeyID": self._api_key,
                        "Accept": "application/json",
                    },
                    params={
                        "page": page,
                        "limit": DEFAULT_PAGE_LIMIT,
                    },
                )

                response.raise_for_status()

                body = response.json()

            except (
                httpx.HTTPError,
                ValueError,
            ) as exc:
                raise ExternalDataUnavailable(
                    "Current road-disruption information "
                    "is temporarily unavailable."
                ) from exc

            page_records = self._extract_records(
                body
            )

            records.extend(
                page_records
            )

            meta = (
                body.get("meta")
                if isinstance(body, dict)
                else None
            )

            if isinstance(meta, dict):
                total_pages = meta.get(
                    "total_pages"
                )

                current_page = meta.get(
                    "page"
                )

                if (
                    isinstance(
                        total_pages,
                        int,
                    )
                    and isinstance(
                        current_page,
                        int,
                    )
                    and current_page
                    >= total_pages
                ):
                    break

            elif (
                len(page_records)
                < DEFAULT_PAGE_LIMIT
            ):
                break

        return records

    @staticmethod
    def _extract_records(
        body: Any,
    ) -> list[dict[str, Any]]:
        if isinstance(body, list):
            return body

        if not isinstance(body, dict):
            raise ExternalDataUnavailable(
                "The road-disruption response "
                "could not be read."
            )

        # Current Victorian DTP v3 response:
        #
        # {
        #     "meta": {...},
        #     "data": {
        #         "type": "FeatureCollection",
        #         "features": [...]
        #     },
        #     "links": [...]
        # }

        data = body.get("data")

        if isinstance(data, dict):
            features = data.get(
                "features"
            )

            if isinstance(
                features,
                list,
            ):
                return features

        # Compatibility with possible alternate shapes.

        for key in (
            "features",
            "results",
            "records",
        ):
            value = body.get(key)

            if isinstance(
                value,
                list,
            ):
                return value

        if isinstance(data, list):
            return data

        raise ExternalDataUnavailable(
            "The road-disruption response "
            "could not be read."
        )

    @staticmethod
    def _parse_record(
        record: dict[str, Any],
        *,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> RoadDisruption | None:
        geometry = (
            record.get("geometry")
            or {}
        )

        properties = (
            record.get("properties")
            or record
        )

        if not isinstance(
            geometry,
            dict,
        ):
            geometry = {}

        if not isinstance(
            properties,
            dict,
        ):
            return None

        status = (
            _normalise_text(
                properties.get("status")
            )
            or ""
        )

        if (
            status
            and status.casefold()
            != "active"
        ):
            return None

        coordinates = geometry.get(
            "coordinates"
        )

        distance_km = (
            _distance_to_geometry_km(
                latitude,
                longitude,
                coordinates,
            )
        )

        if (
            distance_km is None
            or distance_km > radius_km
        ):
            return None

        disruption_id = (
            properties.get("impactId")
            or properties.get("id")
            or properties.get("eventId")
        )

        if disruption_id is None:
            return None

        points = _flatten_points(
            coordinates
        )

        point_latitude = (
            points[0][0]
            if points
            else None
        )

        point_longitude = (
            points[0][1]
            if points
            else None
        )

        road_name = (
            properties.get(
                "closedRoadName"
            )
            or properties.get(
                "declaredRoadName"
            )
            or properties.get(
                "roadName"
            )
        )

        return RoadDisruption(
            disruption_id=str(
                disruption_id
            ),
            event_type=_normalise_text(
                properties.get(
                    "eventType"
                )
            ),
            event_subtype=_normalise_text(
                properties.get(
                    "eventSubType"
                )
            ),
            road_name=_normalise_text(
                road_name
            ),
            description=_normalise_text(
                properties.get(
                    "description"
                )
            ),
            impact=_normalise_text(
                properties.get(
                    "impact"
                )
            ),
            status=status or None,
            latitude=point_latitude,
            longitude=point_longitude,
            distance_km=round(
                distance_km,
                2,
            ),
            last_updated=_parse_datetime(
                properties.get(
                    "lastUpdated"
                )
            ),
            end_time=_parse_datetime(
                properties.get(
                    "endTime"
                )
            ),
        )
