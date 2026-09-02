"""Official Vicmap Address ArcGIS client."""

import re
from typing import Any

import httpx

from app.core.exceptions import AddressResolutionError, ExternalDataUnavailable
from app.schemas.households import AddressSuggestion, HouseholdLocation


VICMAP_ADDRESS_QUERY_URL = (
    "https://services-ap1.arcgis.com/P744lA0wf4LlBZ84/arcgis/rest/services/"
    "Vicmap_Address/FeatureServer/0/query"
)
VICMAP_OUT_FIELDS = (
    "ezi_address,blg_unit_prefix_1,blg_unit_id_1,blg_unit_suffix_1,"
    "house_prefix_1,house_number_1,house_suffix_1,road_name,road_type,"
    "road_suffix,locality_name,state,postcode"
)


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
        timeout_seconds: float = 20.0,
    ) -> None:
        self.http_client = http_client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
        )

    def resolve(self, address: str) -> HouseholdLocation:
        normalized = _normalize_address(address)
        if not normalized:
            raise AddressResolutionError(
                "Please select a complete Victorian address from the suggestions."
            )
        if len(normalized.split()) < 3:
            raise AddressResolutionError(
                "Please select a complete Victorian address from the suggestions."
            )

        exact = self._query(f"ezi_address = '{_sql_literal(normalized)}'")
        exact_matches = self._credible_features(exact)
        if exact.get("exceededTransferLimit"):
            raise AddressResolutionError(
                "Please select a complete Victorian address from the suggestions."
            )
        if len(exact_matches) == 1:
            return self._to_location(exact_matches[0])
        if len(exact_matches) > 1:
            # Multiple official features may share one exact ezi_address (for
            # example unit/building records). The canonical address itself is
            # still exact, so use an official feature instead of treating the
            # selected suggestion as an ambiguous free-text prefix.
            return self._to_location(exact_matches[0])

        partial = self._query(f"ezi_address LIKE '{_sql_literal(normalized)}%'")
        partial_matches = self._credible_features(partial)
        if partial.get("exceededTransferLimit"):
            raise AddressResolutionError(
                "Please select a complete Victorian address from the suggestions."
            )
        if not partial_matches:
            raise AddressResolutionError(
                "Please select a complete Victorian address from the suggestions."
            )
        return self._resolve_unique(partial_matches)

    def suggest(self, query: str, limit: int = 8) -> list[AddressSuggestion]:
        """Return official Victorian address candidates for autocomplete."""
        normalized = _normalize_address(query)
        if len(normalized) < 3:
            return []
        payload = self._query(
            f"ezi_address LIKE '{_sql_literal(normalized)}%'",
            result_record_count=max(1, min(limit, 20)),
            order_by="ezi_address ASC",
        )
        suggestions: list[AddressSuggestion] = []
        seen: set[tuple[str, float, float]] = set()
        for feature in self._credible_features(payload):
            suggestion = self._to_suggestion(feature)
            key = (
                suggestion.address.casefold(),
                round(suggestion.latitude, 7),
                round(suggestion.longitude, 7),
            )
            if key not in seen:
                seen.add(key)
                suggestions.append(suggestion)
        return suggestions[:limit]

    def _query(
        self,
        where: str,
        *,
        result_record_count: int = 20,
        order_by: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "where": f"({where}) AND state = 'VIC'",
            "outFields": VICMAP_OUT_FIELDS,
            "returnGeometry": "true",
            "outSR": "4326",
            "resultRecordCount": str(result_record_count),
            "f": "json",
        }
        if order_by is not None:
            params["orderByFields"] = order_by
        try:
            response = self.http_client.get(
                VICMAP_ADDRESS_QUERY_URL,
                params=params,
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
                "Please select a complete Victorian address from the suggestions."
            )
        return self._to_location(next(iter(unique.values())))

    @staticmethod
    def _to_location(feature: dict[str, Any]) -> HouseholdLocation:
        return HouseholdLocation.model_validate(
            VicmapAddressClient._to_suggestion(feature).model_dump()
        )

    @staticmethod
    def _to_suggestion(feature: dict[str, Any]) -> AddressSuggestion:
        attributes = feature["attributes"]
        geometry = feature["geometry"]
        ezi_address = " ".join(str(attributes["ezi_address"]).split())
        postcode = str(attributes["postcode"]).strip()
        if ezi_address.endswith(postcode):
            prefix = ezi_address[: -len(postcode)].rstrip()
            standardized = f"{prefix} VIC {postcode}"
        else:
            standardized = f"{ezi_address} VIC"

        def joined(parts: tuple[object, ...], separator: str = "") -> str | None:
            values = [str(value).strip() for value in parts if value not in (None, "")]
            return separator.join(values) or None

        return AddressSuggestion(
            address=standardized,
            unit_number=joined(
                (
                    attributes.get("blg_unit_prefix_1"),
                    attributes.get("blg_unit_id_1"),
                    attributes.get("blg_unit_suffix_1"),
                )
            ),
            street_number=joined(
                (
                    attributes.get("house_prefix_1"),
                    attributes.get("house_number_1"),
                    attributes.get("house_suffix_1"),
                )
            ),
            street_name=joined(
                (
                    attributes.get("road_name"),
                    attributes.get("road_type"),
                    attributes.get("road_suffix"),
                ),
                " ",
            ),
            suburb_or_locality=str(attributes["locality_name"]).strip().title(),
            state="VIC",
            postcode=postcode,
            country="Australia",
            latitude=float(geometry["y"]),
            longitude=float(geometry["x"]),
        )
