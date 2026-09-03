"""Official Vicmap Address ArcGIS client."""

from dataclasses import dataclass
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
    "ezi_address,hsa_unit_id,blg_unit_prefix_1,blg_unit_id_1,blg_unit_suffix_1,"
    "house_prefix_1,house_number_1,house_suffix_1,road_name,road_type,"
    "road_suffix,locality_name,state,postcode"
)

ROAD_TYPE_ALIASES = {
    "RD": "ROAD",
    "ROAD": "ROAD",
    "ST": "STREET",
    "STREET": "STREET",
    "AVE": "AVENUE",
    "AVENUE": "AVENUE",
    "DR": "DRIVE",
    "DRIVE": "DRIVE",
    "HWY": "HIGHWAY",
    "HIGHWAY": "HIGHWAY",
    "CT": "COURT",
    "COURT": "COURT",
    "CRES": "CRESCENT",
    "CRESCENT": "CRESCENT",
    "PDE": "PARADE",
    "PARADE": "PARADE",
    "PL": "PLACE",
    "PLACE": "PLACE",
    "LN": "LANE",
    "LANE": "LANE",
    "TCE": "TERRACE",
    "TERRACE": "TERRACE",
}


@dataclass(frozen=True)
class _AddressQuery:
    normalized: str
    unit_number: str | None = None
    house_number: int | None = None
    house_suffix: str | None = None
    road_name: str | None = None
    road_type: str | None = None
    locality: str | None = None
    postcode: str | None = None


def _normalize_address(value: str) -> str:
    return _parse_address(value).normalized


def _parse_address(value: str) -> _AddressQuery:
    """Create one safe comparison/query representation for Victorian addresses."""
    upper = value.strip().upper()
    unit_match = re.match(r"^([A-Z0-9]+)\s*/\s*", upper)
    unit_number = unit_match.group(1) if unit_match else None
    if unit_match:
        upper = upper[unit_match.end() :]

    tokens = re.sub(r"[^A-Z0-9]+", " ", upper).split()
    tokens = [token for token in tokens if token != "VIC"]
    if not tokens:
        return _AddressQuery(normalized="")

    house_match = re.fullmatch(r"(\d+)([A-Z]?)", tokens[0])
    if not house_match:
        return _AddressQuery(normalized=" ".join(tokens))

    house_number = int(house_match.group(1))
    house_suffix = house_match.group(2) or None
    remaining = tokens[1:]
    postcode = (
        remaining.pop()
        if remaining and re.fullmatch(r"\d{4}", remaining[-1])
        else None
    )

    road_type_index = next(
        (
            index
            for index, token in enumerate(remaining)
            if index >= 1 and token in ROAD_TYPE_ALIASES
        ),
        None,
    )
    if road_type_index is None:
        road_tokens = remaining
        road_type = None
        locality_tokens: list[str] = []
    else:
        road_tokens = remaining[:road_type_index]
        road_type = ROAD_TYPE_ALIASES[remaining[road_type_index]]
        locality_tokens = remaining[road_type_index + 1 :]

    normalized_tokens = []
    if unit_number:
        normalized_tokens.append(unit_number)
    normalized_tokens.append(f"{house_number}{house_suffix or ''}")
    normalized_tokens.extend(road_tokens)
    if road_type:
        normalized_tokens.append(road_type)
    normalized_tokens.extend(locality_tokens)
    if postcode:
        normalized_tokens.append(postcode)

    return _AddressQuery(
        normalized=" ".join(normalized_tokens),
        unit_number=unit_number,
        house_number=house_number,
        house_suffix=house_suffix,
        road_name=" ".join(road_tokens) or None,
        road_type=road_type,
        locality=" ".join(locality_tokens) or None,
        postcode=postcode,
    )


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


class VicmapAddressClient:
    """Adapt the official Vicmap ArcGIS layer to the address provider boundary.

    Suggestions use indexed prefix matching for interactive discovery. Final
    resolution requires a credible exact or unique official feature and takes
    coordinates only from Vicmap geometry. ArcGIS OBJECTID is intentionally not
    exposed as a permanent application identifier.
    """

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 20.0,
        autocomplete_timeout_seconds: float = 4.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.autocomplete_timeout_seconds = autocomplete_timeout_seconds
        self.http_client = http_client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
        )

    def resolve(self, address: str) -> HouseholdLocation:
        """Resolve one complete official address rather than accept a broad prefix."""
        parsed = _parse_address(address)
        normalized = parsed.normalized
        if not normalized:
            raise AddressResolutionError(
                "Please select a complete Victorian address from the suggestions."
            )
        if len(normalized.split()) < 3:
            raise AddressResolutionError(
                "Please select a complete Victorian address from the suggestions."
            )

        # Exact and trailing-wildcard queries allow ArcGIS to use its address
        # index; a leading wildcard would force slow full-layer scans.
        exact_address = normalized
        if parsed.unit_number:
            without_unit = normalized[len(parsed.unit_number) + 1 :]
            exact_address = f"{parsed.unit_number}/{without_unit}"
        exact = self._query(f"ezi_address = '{_sql_literal(exact_address)}'")
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

        structured_where = self._structured_where(parsed)
        if structured_where is not None:
            structured = self._query(structured_where)
            structured_matches = self._credible_features(structured)
            if structured.get("exceededTransferLimit"):
                raise AddressResolutionError(
                    "Multiple official addresses match. "
                    "Please select one from the suggestions."
                )
            if structured_matches:
                return self._resolve_unique(structured_matches)

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
        """Return partial official candidates for autocomplete, not verification."""
        parsed = _parse_address(query)
        normalized = parsed.normalized
        if len(normalized) < 3:
            return []
        structured_where = self._structured_where(parsed, partial_road=True)
        payload = self._query(
            structured_where or f"ezi_address LIKE '{_sql_literal(normalized)}%'",
            result_record_count=max(1, min(limit, 20)),
            order_by="road_name ASC,road_type ASC,locality_name ASC,ezi_address ASC",
            timeout_seconds=self.autocomplete_timeout_seconds,
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

    def reverse(
        self, latitude: float, longitude: float, limit: int = 5
    ) -> list[AddressSuggestion]:
        """Return nearby official candidates without asserting an exact address."""
        if not (-40 <= latitude <= -33 and 140 <= longitude <= 150):
            return []
        payload = self._query(
            "house_number_1 IS NOT NULL",
            result_record_count=max(1, min(limit, 10)),
            timeout_seconds=self.autocomplete_timeout_seconds,
            extra_params={
                "geometry": f"{longitude},{latitude}",
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "distance": "200",
                "units": "esriSRUnit_Meter",
            },
        )
        features = self._credible_features(payload)
        features.sort(
            key=lambda feature: (
                (float(feature["geometry"]["y"]) - latitude) ** 2
                + (float(feature["geometry"]["x"]) - longitude) ** 2
            )
        )
        suggestions: list[AddressSuggestion] = []
        seen: set[str] = set()
        for feature in features:
            suggestion = self._to_suggestion(feature)
            key = suggestion.address.casefold()
            if key not in seen:
                seen.add(key)
                suggestions.append(suggestion)
        return suggestions[:limit]

    @staticmethod
    def _structured_where(
        parsed: _AddressQuery, *, partial_road: bool = False
    ) -> str | None:
        if parsed.house_number is None or not parsed.road_name:
            return None
        clauses = [f"house_number_1 = {parsed.house_number}"]
        if parsed.house_suffix:
            clauses.append(f"house_suffix_1 = '{_sql_literal(parsed.house_suffix)}'")
        if parsed.unit_number:
            unit_number = _sql_literal(parsed.unit_number)
            unit_clauses = [f"hsa_unit_id = '{unit_number}'"]
            if parsed.unit_number.isdigit():
                unit_clauses.append(f"blg_unit_id_1 = {int(parsed.unit_number)}")
            clauses.append(f"({' OR '.join(unit_clauses)})")
        road_name = _sql_literal(parsed.road_name)
        if partial_road and parsed.road_type is None:
            clauses.append(f"road_name LIKE '{road_name}%'")
        else:
            clauses.append(f"road_name = '{road_name}'")
        if parsed.road_type:
            clauses.append(f"road_type = '{_sql_literal(parsed.road_type)}'")
        if parsed.locality:
            clauses.append(f"locality_name = '{_sql_literal(parsed.locality)}'")
        if parsed.postcode:
            clauses.append(f"postcode = '{_sql_literal(parsed.postcode)}'")
        return " AND ".join(clauses)

    def _query(
        self,
        where: str,
        *,
        result_record_count: int = 20,
        order_by: str | None = None,
        timeout_seconds: float | None = None,
        extra_params: dict[str, str] | None = None,
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
        if extra_params:
            params.update(extra_params)
        try:
            response = self.http_client.get(
                VICMAP_ADDRESS_QUERY_URL,
                params=params,
                timeout=timeout_seconds or self.timeout_seconds,
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
                "Multiple official addresses match. "
                "Please select one from the suggestions."
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
            ) or joined((attributes.get("hsa_unit_id"),)),
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
