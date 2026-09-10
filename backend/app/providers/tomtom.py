"""TomTom Orbis address search, verification, and reverse-geocoding client."""

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.core.exceptions import AddressResolutionError, ExternalDataUnavailable
from app.schemas.households import AddressSuggestion, HouseholdLocation


TOMTOM_PLACES_URL = "https://api.tomtom.com/maps/orbis/places"
VICTORIA_BBOX = (140.96, -39.2, 150.03, -33.98)
VICTORIA_SUBDIVISION = "AU-VIC"
DETAIL_TYPE_PATHS = {
    "address": "addresses",
    "street": "streets",
    "area": "areas",
}
PROVIDER_REFERENCE_PATTERN = re.compile(
    r"^(address|street|area):([A-Za-z0-9_-]{1,240})$"
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
    "TR": "TRACK",
    "TRK": "TRACK",
    "TRACK": "TRACK",
}


@dataclass(frozen=True)
class _EnteredAddress:
    unit_number: str | None
    house_number: str | None
    street: str | None
    locality: str | None
    postcode: str | None


def _tokens(value: str) -> list[str]:
    return re.sub(r"[^A-Z0-9]+", " ", value.upper()).split()


def _normalize_component(value: str) -> str:
    return " ".join(ROAD_TYPE_ALIASES.get(token, token) for token in _tokens(value))


def _normalize_postcode(value: str | None) -> str | None:
    if value is None:
        return None
    matches = re.findall(r"(?<!\d)\d{4}(?!\d)", value)
    return matches[0] if len(matches) == 1 else None


def _parse_entered_address(value: str) -> _EnteredAddress:
    upper = value.strip().upper()
    unit_match = re.match(r"^(?:UNIT\s+)?([A-Z0-9]+)\s*/\s*", upper)
    unit_number = unit_match.group(1) if unit_match else None
    if unit_match:
        upper = upper[unit_match.end() :]

    tokens = [token for token in _tokens(upper) if token not in {"AUSTRALIA", "VIC"}]
    postcode = tokens.pop() if tokens and re.fullmatch(r"\d{4}", tokens[-1]) else None
    if not tokens:
        return _EnteredAddress(unit_number, None, None, None, postcode)

    house_number = tokens.pop(0) if re.fullmatch(r"\d+[A-Z]?", tokens[0]) else None
    road_type_index = next(
        (index for index, token in enumerate(tokens) if token in ROAD_TYPE_ALIASES),
        None,
    )
    if road_type_index is None:
        return _EnteredAddress(unit_number, house_number, None, None, postcode)

    street_tokens = tokens[: road_type_index + 1]
    locality_tokens = tokens[road_type_index + 1 :]
    return _EnteredAddress(
        unit_number=unit_number,
        house_number=house_number,
        street=_normalize_component(" ".join(street_tokens)),
        locality=" ".join(locality_tokens) or None,
        postcode=postcode,
    )


class TomTomAddressClient:
    """Adapt current TomTom Orbis APIs to FIREBREAK's address boundary."""

    def __init__(
        self,
        *,
        api_key: str | None,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 10.0,
        autocomplete_timeout_seconds: float = 4.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise RuntimeError("TOMTOM_API_KEY is required when APP_DATA_MODE=live.")
        self._api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.autocomplete_timeout_seconds = autocomplete_timeout_seconds
        self.http_client = http_client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
        )

    def suggest(self, query: str, limit: int = 8) -> list[AddressSuggestion]:
        if len(query.strip()) < 3:
            return []
        payload = self._request_json(
            "POST",
            f"{TOMTOM_PLACES_URL}/suggest",
            version="3",
            timeout_seconds=self.autocomplete_timeout_seconds,
            json={
                "query": query.strip(),
                "maxResults": max(1, min(limit, 10)),
                "filters": {
                    "types": ["address", "street", "area"],
                    "countryCodesIso2": ["AU"],
                    "geometry": {
                        "type": "rectangle",
                        "coordinates": list(VICTORIA_BBOX),
                    },
                },
            },
        )
        suggestions: list[AddressSuggestion] = []
        seen: set[str] = set()
        for result in self._results(payload):
            suggestion = self._to_suggestion(result, require_position=False)
            if suggestion is None:
                continue
            key = suggestion.address.casefold()
            if key not in seen:
                seen.add(key)
                suggestions.append(suggestion)
        return suggestions[:limit]

    def resolve(
        self, address: str, *, provider_reference: str | None = None
    ) -> HouseholdLocation:
        reference = self._parse_provider_reference(provider_reference)
        if reference is not None:
            return self._resolve_reference(address, *reference)

        entered = _parse_entered_address(address)
        if entered.house_number is None or entered.street is None:
            raise AddressResolutionError(
                "Please select a complete Victorian street address from the suggestions."
            )

        payload = self._request_json(
            "GET",
            f"{TOMTOM_PLACES_URL}/geocode",
            version="2",
            timeout_seconds=self.timeout_seconds,
            params={
                "query": re.sub(
                    r"^(?:UNIT\s+)?[A-Z0-9]+\s*/\s*",
                    "",
                    address.strip(),
                    flags=re.IGNORECASE,
                ),
                "countryCodesIso2": "AU",
                "bbox": ",".join(str(value) for value in VICTORIA_BBOX),
                "types": "address",
                "maxResults": "20",
            },
        )
        matches: dict[
            tuple[str, str, str, str], tuple[int, HouseholdLocation]
        ] = {}
        for result in self._results(payload):
            if result.get("type") != "address":
                continue
            suggestion = self._to_suggestion(result, require_position=True)
            if suggestion is None:
                continue
            support = self._match_support(entered, suggestion)
            if support is None or not suggestion.street_number or not suggestion.street_name:
                continue
            key = (
                _normalize_component(suggestion.street_number),
                _normalize_component(suggestion.street_name),
                _normalize_component(suggestion.suburb_or_locality or ""),
                _normalize_postcode(suggestion.postcode) or "",
            )
            matches[key] = (
                support,
                HouseholdLocation.model_validate(suggestion.model_dump()),
            )

        if not matches:
            raise AddressResolutionError(
                "Please select a complete Victorian street address from the suggestions."
            )
        best_support = max(support for support, _ in matches.values())
        best_matches = [
            match for support, match in matches.values() if support == best_support
        ]
        if len(best_matches) > 1:
            raise AddressResolutionError(
                "Multiple Victorian addresses match. Please select a complete suggestion."
            )
        resolved = best_matches[0]
        if entered.unit_number:
            return resolved.model_copy(
                update={
                    "address": f"{entered.unit_number}/{resolved.address}",
                    "unit_number": entered.unit_number,
                    "verification_message": (
                        "The base street address was verified; the unit or apartment "
                        "was preserved but not independently verified."
                    ),
                }
            )
        return resolved

    def _resolve_reference(
        self, selected_address: str, result_type: str, result_id: str
    ) -> HouseholdLocation:
        if result_type != "address":
            raise AddressResolutionError(
                "Please select a complete Victorian street address from the suggestions."
            )
        payload = self._request_json(
            "GET",
            (
                f"{TOMTOM_PLACES_URL}/details/"
                f"{DETAIL_TYPE_PATHS[result_type]}/{quote(result_id, safe='')}"
            ),
            version="3",
            timeout_seconds=self.timeout_seconds,
            attributes="id,type,title,subtitles,position,address",
        )
        if payload.get("type") != "address":
            raise AddressResolutionError(
                "Please select a complete Victorian street address from the suggestions."
            )
        suggestion = self._to_suggestion(payload, require_position=True)
        if (
            suggestion is None
            or not suggestion.street_number
            or not suggestion.street_name
            or suggestion.latitude is None
            or suggestion.longitude is None
        ):
            raise AddressResolutionError(
                "Please select a complete Victorian street address from the suggestions."
            )

        resolved = HouseholdLocation.model_validate(
            suggestion.model_dump(exclude={"provider_reference"})
        )
        entered = _parse_entered_address(selected_address)
        if entered.unit_number:
            return resolved.model_copy(
                update={
                    "address": f"{entered.unit_number}/{resolved.address}",
                    "unit_number": entered.unit_number,
                    "verification_message": (
                        "The base street address was verified; the unit or apartment "
                        "was preserved but not independently verified."
                    ),
                }
            )
        return resolved

    def reverse(
        self, latitude: float, longitude: float, limit: int = 5
    ) -> list[AddressSuggestion]:
        if not self._inside_victoria_bounds(latitude, longitude):
            return []
        payload = self._request_json(
            "GET",
            f"{TOMTOM_PLACES_URL}/reverseGeocode",
            version="2",
            timeout_seconds=self.autocomplete_timeout_seconds,
            params={
                "position": f"{longitude},{latitude}",
                "radiusInMeters": "200",
            },
        )
        suggestions: list[AddressSuggestion] = []
        seen: set[str] = set()
        for result in self._results(payload):
            suggestion = self._to_suggestion(result, require_position=True)
            if suggestion is None:
                continue
            key = suggestion.address.casefold()
            if key not in seen:
                seen.add(key)
                suggestions.append(suggestion)
        return suggestions[: max(1, min(limit, 5))]

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        version: str,
        timeout_seconds: float,
        attributes: str = "results",
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = {
            "TomTom-Api-Key": self._api_key,
            "TomTom-Api-Version": version,
            "Attributes": attributes,
            "Accept": "application/json",
            "Accept-Language": "en-AU",
        }
        if method == "POST":
            headers["Content-Type"] = "application/json"
        try:
            response = self.http_client.request(
                method,
                url,
                headers=headers,
                timeout=timeout_seconds,
                **kwargs,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalDataUnavailable(
                "The address service is temporarily unavailable."
            ) from exc
        if not isinstance(payload, dict):
            raise ExternalDataUnavailable("The address service returned invalid data.")
        return payload

    @staticmethod
    def _results(payload: dict[str, Any]) -> list[dict[str, Any]]:
        results = payload.get("results")
        if not isinstance(results, list):
            raise ExternalDataUnavailable("The address service returned invalid data.")
        if any(not isinstance(result, dict) for result in results):
            raise ExternalDataUnavailable("The address service returned invalid data.")
        return results

    @staticmethod
    def _to_suggestion(
        result: dict[str, Any], *, require_position: bool
    ) -> AddressSuggestion | None:
        result_type = result.get("type")
        if result_type not in {"address", "street", "area"}:
            return None
        address = result.get("address")
        if not isinstance(address, dict):
            if result_type == "address":
                raise ExternalDataUnavailable("The address service returned invalid data.")
            return None
        if (
            str(address.get("countryCodeIso2", "")).upper() != "AU"
            or str(address.get("countrySubdivisionCodeIso", "")).upper()
            != VICTORIA_SUBDIVISION
        ):
            return None

        street_number = TomTomAddressClient._text(address.get("houseNumber"))
        street_name = TomTomAddressClient._text(address.get("street"))
        locality = TomTomAddressClient._text(
            address.get("municipalitySubdivision") or address.get("municipality")
        )
        raw_postcode = TomTomAddressClient._text(address.get("postalCode"))
        postcode = _normalize_postcode(raw_postcode)
        if raw_postcode is not None and postcode is None:
            raise ExternalDataUnavailable("The address service returned invalid data.")

        latitude: float | None = None
        longitude: float | None = None
        position = result.get("position")
        if position is not None:
            if not isinstance(position, dict):
                raise ExternalDataUnavailable("The address service returned invalid data.")
            coordinates = position.get("coordinates")
            if (
                not isinstance(coordinates, list)
                or len(coordinates) < 2
                or not all(isinstance(value, (int, float)) for value in coordinates[:2])
            ):
                raise ExternalDataUnavailable("The address service returned invalid data.")
            longitude = float(coordinates[0])
            latitude = float(coordinates[1])
            if not TomTomAddressClient._inside_victoria_bounds(latitude, longitude):
                return None
        elif require_position:
            raise ExternalDataUnavailable("The address service returned invalid data.")

        primary = " ".join(value for value in (street_number, street_name) if value)
        if not primary:
            primary = locality or TomTomAddressClient._text(result.get("title"))
        if not primary:
            return None
        parts = [primary]
        if locality and _normalize_component(locality) not in _normalize_component(primary):
            parts.append(locality)
        parts.append("VIC")
        if postcode:
            parts.append(postcode)

        return AddressSuggestion(
            address=" ".join(parts),
            street_number=street_number,
            street_name=street_name,
            suburb_or_locality=locality,
            state="VIC",
            postcode=postcode,
            country="Australia",
            latitude=latitude,
            longitude=longitude,
            provider_reference=TomTomAddressClient._provider_reference(result),
        )

    @staticmethod
    def _match_support(
        entered: _EnteredAddress,
        candidate: AddressSuggestion,
    ) -> int | None:
        if _normalize_component(entered.house_number or "") != _normalize_component(
            candidate.street_number or ""
        ):
            return None
        if _normalize_component(entered.street or "") != _normalize_component(
            candidate.street_name or ""
        ):
            return None

        locality_supplied = entered.locality is not None
        postcode_supplied = entered.postcode is not None
        locality_matches = locality_supplied and _normalize_component(
            entered.locality or ""
        ) == _normalize_component(candidate.suburb_or_locality or "")
        postcode_matches = postcode_supplied and _normalize_postcode(
            entered.postcode
        ) == _normalize_postcode(candidate.postcode)
        support = int(locality_matches) + int(postcode_matches)

        # Free text remains conservative. A supplied postcode is a strong
        # discriminator; locality may vary when the postcode still supports it.
        if postcode_supplied and not postcode_matches:
            return None
        if locality_supplied and not locality_matches and not postcode_matches:
            return None
        return support

    @staticmethod
    def _provider_reference(result: dict[str, Any]) -> str | None:
        result_type = result.get("type")
        result_id = result.get("id")
        if result_type not in DETAIL_TYPE_PATHS or not isinstance(result_id, str):
            return None
        reference = f"{result_type}:{result_id}"
        return reference if PROVIDER_REFERENCE_PATTERN.fullmatch(reference) else None

    @staticmethod
    def _parse_provider_reference(value: str | None) -> tuple[str, str] | None:
        if not value:
            return None
        match = PROVIDER_REFERENCE_PATTERN.fullmatch(value)
        if match is None:
            return None
        return match.group(1), match.group(2)

    @staticmethod
    def _inside_victoria_bounds(latitude: float, longitude: float) -> bool:
        west, south, east, north = VICTORIA_BBOX
        return south <= latitude <= north and west <= longitude <= east

    @staticmethod
    def _text(value: object) -> str | None:
        if value is None:
            return None
        normalized = " ".join(str(value).split())
        return normalized or None
