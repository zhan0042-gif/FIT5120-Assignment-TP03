"""TomTom Matrix Routing adapter for the rendezvous simulation.

Matrix Routing lives on the legacy v2 API and authenticates with a `key` query
parameter, unlike the Orbis Places endpoints used by TomTomAddressClient, which
authenticate by header. Orbis exposes no matrix endpoint, so this is a separate
module rather than a branch inside the address client.
"""

from typing import Any

import httpx

from app.core.exceptions import ExternalDataUnavailable
from app.providers.interfaces import RouteLeg

TOMTOM_MATRIX_URL = "https://api.tomtom.com/routing/matrix/2"


class TomTomRoutingClient:
    """Estimate travel time from several origins to one destination."""

    def __init__(
        self,
        *,
        api_key: str | None,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise RuntimeError("TOMTOM_API_KEY is required when APP_DATA_MODE=live.")
        self._api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx.Client(
            timeout=timeout_seconds, follow_redirects=True
        )

    def travel_times(
        self,
        origins: list[tuple[float, float]],
        destination: tuple[float, float],
    ) -> list[RouteLeg]:
        """Return one leg per origin, in the order the origins were given.

        The whole household travels in a single request: cheaper, faster, and
        atomic, so a partial failure cannot leave some members with figures and
        others without.
        """
        if not origins:
            return []

        payload = {
            "origins": [
                {"point": {"latitude": latitude, "longitude": longitude}}
                for latitude, longitude in origins
            ],
            "destinations": [
                {"point": {"latitude": destination[0], "longitude": destination[1]}}
            ],
        }
        try:
            response = self.http_client.post(
                TOMTOM_MATRIX_URL,
                params={
                    "key": self._api_key,
                    "routeType": "fastest",
                    "travelMode": "car",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalDataUnavailable(
                "Travel time estimates are temporarily unavailable."
            ) from exc

        return self._legs(body, expected=len(origins))

    @staticmethod
    def _legs(body: dict[str, Any], *, expected: int) -> list[RouteLeg]:
        legs: list[RouteLeg] = []
        try:
            for entry in body["data"]:
                summary = entry["routeSummary"]
                legs.append(
                    RouteLeg(
                        origin_index=int(entry["originIndex"]),
                        travel_seconds=int(summary["travelTimeInSeconds"]),
                        distance_meters=int(summary["lengthInMeters"]),
                        traffic_delay_seconds=int(
                            summary.get("trafficDelayInSeconds", 0)
                        ),
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise ExternalDataUnavailable(
                "The travel time response could not be read."
            ) from exc

        if len(legs) != expected:
            raise ExternalDataUnavailable("The travel time response was incomplete.")
        legs.sort(key=lambda leg: leg.origin_index)
        return legs
