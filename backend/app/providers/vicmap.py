"""Official Vicmap Address ArcGIS client."""

import re
from typing import Any

import httpx

from app.core.exceptions import AddressResolutionError, ExternalDataUnavailable
from app.schemas.households import HouseholdLocation


VICMAP_ADDRESS_QUERY_URL = (
    "https://services-ap1.arcgis.com/P744lA0wf4LlBZ84/arcgis/rest/services/"
    "Vicmap_Address/FeatureServer/0/query"
)
VICMAP_OUT_FIELDS = "ezi_address,locality_name,state,postcode"


def _normalize_address(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", " ", value.upper())
    tokens = [token for token in normalized.split() if token != "VIC"]
    return " ".join(tokens)


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


class VicmapAddressClient:
    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.http_client = http_client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
        )

    def suggest(self, query: str, *, limit: int = 5) -> list[str]:
        """Return official Victorian address labels for a partial query."""

        normalized = _normalize_address(query)
        if len(normalized) < 3:
            return []
        payload = self._query(
            f"UPPER(ezi_address) LIKE '%{_sql_literal(normalized)}%'",
            result_limit=max(1, min(limit, 10)),
        )
        suggestions: list[str] = []
        for feature in self._credible_features(payload):
            address = self._to_location(feature).address
            if address not in suggestions:
                suggestions.append(address)
        return suggestions[:limit]

    def resolve(self, address: str) -> HouseholdLocation:
        normalized = _normalize_address(address)
        if not normalized:
            raise AddressResolutionError("Enter a Victorian household address.")
        if len(normalized.split()) < 3:
            raise AddressResolutionError(
                "Enter a more complete Victorian household address."
            )

        exact = self._query(f"UPPER(ezi_address) = '{_sql_literal(normalized)}'")
        exact_matches = self._credible_features(exact)
        if exact.get("exceededTransferLimit"):
            raise AddressResolutionError(
                "The address matches multiple Victorian locations. Enter a full address including locality and postcode."
            )
        if len(exact_matches) == 1:
            return self._to_location(exact_matches[0])
        if len(exact_matches) > 1:
            return self._resolve_unique(exact_matches)

        partial = self._query(
            f"UPPER(ezi_address) LIKE '%{_sql_literal(normalized)}%'"
        )
        partial_matches = self._credible_features(partial)
        if partial.get("exceededTransferLimit"):
            raise AddressResolutionError(
                "The address matches multiple Victorian locations. Enter a full address including locality and postcode."
            )
        if not partial_matches:
            raise AddressResolutionError(
                "No matching Victorian household address was found."
            )
        return self._resolve_unique(partial_matches)

    def _query(self, where: str, *, result_limit: int = 20) -> dict[str, Any]:
        try:
            response = self.http_client.get(
                VICMAP_ADDRESS_QUERY_URL,
                params={
                    "where": f"({where}) AND state = 'VIC'",
                    "outFields": VICMAP_OUT_FIELDS,
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "resultRecordCount": str(result_limit),
                    "f": "json",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalDataUnavailable(
                "Official Victorian address data is unavailable."
            ) from exc
        if not isinstance(payload, dict) or "error" in payload:
            raise ExternalDataUnavailable(
                "Official Victorian address data is unavailable."
            )
        features = payload.get("features")
        if not isinstance(features, list):
            raise ExternalDataUnavailable(
                "Official Victorian address data is unavailable."
            )
        return payload

    @staticmethod
    def _credible_features(payload: dict[str, Any]) -> list[dict[str, Any]]:
        credible: list[dict[str, Any]] = []
        for feature in payload["features"]:
            if not isinstance(feature, dict):
                raise ExternalDataUnavailable(
                    "Official Victorian address data is invalid."
                )
            attributes = feature.get("attributes")
            geometry = feature.get("geometry")
            if not isinstance(attributes, dict) or not isinstance(geometry, dict):
                raise ExternalDataUnavailable(
                    "Official Victorian address data is invalid."
                )
            if str(attributes.get("state", "")).strip().upper() != "VIC":
                continue
            if not all(
                str(attributes.get(field, "")).strip()
                for field in ("ezi_address", "locality_name", "postcode")
            ):
                raise ExternalDataUnavailable(
                    "Official Victorian address data is invalid."
                )
            x = geometry.get("x")
            y = geometry.get("y")
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                raise ExternalDataUnavailable(
                    "Official Victorian address data is invalid."
                )
            if not (140 <= x <= 150 and -40 <= y <= -33):
                raise ExternalDataUnavailable(
                    "Official Victorian address data is invalid."
                )
            credible.append(feature)
        return credible

    def _resolve_unique(self, features: list[dict[str, Any]]) -> HouseholdLocation:
        unique: dict[tuple[str, float, float], dict[str, Any]] = {}
        for feature in features:
            attributes = feature["attributes"]
            geometry = feature["geometry"]
            key = (
                _normalize_address(str(attributes["ezi_address"])),
                round(float(geometry["x"]), 7),
                round(float(geometry["y"]), 7),
            )
            unique[key] = feature
        if len(unique) != 1:
            raise AddressResolutionError(
                "The address matches multiple Victorian locations. Enter a full address including locality and postcode."
            )
        return self._to_location(next(iter(unique.values())))

    @staticmethod
    def _to_location(feature: dict[str, Any]) -> HouseholdLocation:
        attributes = feature["attributes"]
        geometry = feature["geometry"]
        ezi_address = " ".join(str(attributes["ezi_address"]).split())
        postcode = str(attributes["postcode"]).strip()
        if ezi_address.endswith(postcode):
            prefix = ezi_address[: -len(postcode)].rstrip()
            standardized = f"{prefix} VIC {postcode}"
        else:
            standardized = f"{ezi_address} VIC"
        return HouseholdLocation(
            address=standardized,
            latitude=float(geometry["y"]),
            longitude=float(geometry["x"]),
        )
