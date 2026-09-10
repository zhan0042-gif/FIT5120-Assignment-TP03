import httpx
import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.providers.tomtom import TomTomAddressClient
from app.services.context import AddressVerificationService


def tomtom_result(
    *,
    title: str = "1 Treasury Place, East Melbourne, VIC, 3002",
    result_type: str = "address",
    country_code: str = "AU",
    subdivision_code: str = "AU-VIC",
    house_number: str | None = "1",
    street: str | None = "Treasury Place",
    locality: str | None = "East Melbourne",
    postcode: str | None = "3002",
    longitude: float = 144.974343,
    latitude: float = -37.8135811,
    with_position: bool = True,
) -> dict:
    address = {
        "country": "Australia",
        "countryCodeIso2": country_code,
        "countrySubdivision": "Victoria" if subdivision_code == "AU-VIC" else "New South Wales",
        "countrySubdivisionCodeIso": subdivision_code,
        "municipality": "Melbourne",
        "municipalitySubdivision": locality,
        "postalCode": postcode,
        "street": street,
        "houseNumber": house_number,
    }
    result = {
        "id": "safe-provider-id",
        "type": result_type,
        "title": title,
        "address": address,
    }
    if with_position:
        result["position"] = {
            "type": "Point",
            "coordinates": [longitude, latitude],
        }
    return result


def client_for(handler) -> TomTomAddressClient:
    return TomTomAddressClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.parametrize("api_key", [None, "", "   "])
def test_live_client_requires_api_key(api_key: str | None) -> None:
    with pytest.raises(RuntimeError, match="TOMTOM_API_KEY"):
        TomTomAddressClient(api_key=api_key)


def test_suggest_uses_orbis_v3_and_normalizes_without_fabricating_coordinates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/maps/orbis/places/suggest")
        assert request.headers["TomTom-Api-Version"] == "3"
        assert request.headers["TomTom-Api-Key"] == "test-key"
        assert "key" not in request.url.params
        assert b'"countryCodesIso2":["AU"]' in request.content
        return httpx.Response(
            200, json={"results": [tomtom_result(with_position=False)]}
        )

    suggestions = client_for(handler).suggest("1 Tre")

    assert len(suggestions) == 1
    assert suggestions[0].address == "1 Treasury Place East Melbourne VIC 3002"
    assert suggestions[0].street_number == "1"
    assert suggestions[0].street_name == "Treasury Place"
    assert suggestions[0].suburb_or_locality == "East Melbourne"
    assert suggestions[0].latitude is None
    assert suggestions[0].longitude is None
    assert suggestions[0].verification_status == "unverified"


def test_suggest_rejects_nsw_and_deduplicates_victorian_candidates() -> None:
    victoria = tomtom_result(with_position=False)
    nsw = tomtom_result(
        subdivision_code="AU-NSW",
        locality="Boree Creek",
        postcode="2652",
        with_position=False,
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"results": [nsw, victoria, victoria]})
    )

    suggestions = TomTomAddressClient(
        api_key="test-key", http_client=httpx.Client(transport=transport)
    ).suggest("788 Drummond")

    assert [item.address for item in suggestions] == [
        "1 Treasury Place East Melbourne VIC 3002"
    ]


@pytest.mark.parametrize("query", ["788 Drumm", "788 Drummnod St"])
def test_partial_and_typo_suggestions_return_provider_candidates(query: str) -> None:
    result = tomtom_result(
        title="788 Drummond Street",
        house_number="788",
        street="Drummond Street",
        locality="Carlton North",
        postcode="3054",
        with_position=False,
    )
    assert client_for(lambda request: httpx.Response(200, json={"results": [result]})).suggest(query)[
        0
    ].address == "788 Drummond Street Carlton North VIC 3054"


def test_suggest_no_results_returns_empty_list() -> None:
    client = client_for(lambda request: httpx.Response(200, json={"results": []}))
    assert client.suggest("missing") == []


def test_malformed_result_is_sanitized_as_unavailable() -> None:
    client = client_for(
        lambda request: httpx.Response(
            200, json={"results": [{"type": "address", "address": "invalid"}]}
        )
    )
    with pytest.raises(ExternalDataUnavailable, match="invalid data"):
        client.suggest("invalid")


def test_timeout_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret upstream detail", request=request)

    with pytest.raises(ExternalDataUnavailable, match="temporarily unavailable"):
        client_for(handler).suggest("1 Treasury")


def test_connection_failure_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret upstream detail", request=request)

    with pytest.raises(ExternalDataUnavailable, match="temporarily unavailable"):
        client_for(handler).suggest("1 Treasury")


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_provider_http_failures_are_sanitized(status: int) -> None:
    client = client_for(
        lambda request: httpx.Response(
            status, json={"detailedError": {"message": "internal provider detail"}}
        )
    )
    with pytest.raises(ExternalDataUnavailable, match="temporarily unavailable") as error:
        client.suggest("1 Treasury")
    assert "internal provider detail" not in str(error.value)


def test_exact_victorian_address_is_verified_with_geojson_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/maps/orbis/places/geocode")
        assert request.headers["TomTom-Api-Version"] == "2"
        assert request.url.params["countryCodesIso2"] == "AU"
        assert request.url.params["types"] == "address"
        return httpx.Response(200, json={"results": [tomtom_result()]})

    verification = AddressVerificationService(client_for(handler)).verify(
        "1 Treasury Place East Melbourne VIC 3002"
    )

    assert verification.verification_status == "verified"
    assert verification.canonical_address == "1 Treasury Place East Melbourne VIC 3002"
    assert verification.latitude == pytest.approx(-37.8135811)
    assert verification.longitude == pytest.approx(144.974343)
    assert verification.state == "VIC"
    assert verification.country == "Australia"


@pytest.mark.parametrize(
    "entered,result",
    [
        (
            "1 Treasury Place East Melbourne VIC 3003",
            tomtom_result(postcode="3002"),
        ),
        (
            "2 Treasury Place East Melbourne VIC 3002",
            tomtom_result(house_number="1"),
        ),
        (
            "1 Parliament Place East Melbourne VIC 3002",
            tomtom_result(street="Treasury Place"),
        ),
    ],
)
def test_wrong_address_components_remain_unverified(entered: str, result: dict) -> None:
    client = client_for(
        lambda request: httpx.Response(200, json={"results": [result]})
    )
    verification = AddressVerificationService(client).verify(entered)
    assert verification.verification_status == "unverified"
    assert verification.latitude is None


def test_interstate_forward_result_is_rejected() -> None:
    result = tomtom_result(subdivision_code="AU-NSW")
    client = client_for(
        lambda request: httpx.Response(200, json={"results": [result]})
    )
    verification = AddressVerificationService(client).verify(
        "1 Treasury Place East Melbourne VIC 3002"
    )
    assert verification.verification_status == "unverified"
    assert verification.latitude is None


def test_ambiguous_results_are_not_verified() -> None:
    second = tomtom_result(
        title="1 Treasury Place, Craigieburn, VIC, 3064",
        locality="Craigieburn",
        postcode="3064",
        longitude=144.9401189,
        latitude=-37.5860395,
    )
    client = client_for(
        lambda request: httpx.Response(
            200, json={"results": [tomtom_result(), second]}
        )
    )
    verification = AddressVerificationService(client).verify("1 Treasury Pl")
    assert verification.verification_status == "unverified"
    assert "Multiple Victorian" in (verification.verification_message or "")


def test_selected_full_address_resolves_only_matching_candidate() -> None:
    unrelated = tomtom_result(
        title="1 Treasury Place, Craigieburn, VIC, 3064",
        locality="Craigieburn",
        postcode="3064",
    )
    client = client_for(
        lambda request: httpx.Response(
            200, json={"results": [unrelated, tomtom_result()]}
        )
    )
    verification = AddressVerificationService(client).verify(
        "1 Treasury Pl", "1 Treasury Place East Melbourne VIC 3002"
    )
    assert verification.verification_status == "verified"
    assert verification.suburb_or_locality == "East Melbourne"


@pytest.mark.parametrize(
    "selected,result",
    [
        (
            "60 WAVERLEY AVE MERRIGUM VIC 3618",
            tomtom_result(
                title="60 Waverley Avenue",
                house_number="60",
                street="Waverley Avenue",
                locality="Greater Shepparton",
                postcode="3618",
            ),
        ),
        (
            "45 DAFFODIL CRES. DIGGERS REST VIC 3427",
            tomtom_result(
                title="45 Daffodil Crescent",
                house_number="45",
                street="Daffodil Crescent",
                locality="Diggers Rest",
                postcode="VIC 3427",
            ),
        ),
    ],
)
def test_selected_suggestion_accepts_normalized_format_and_support_variations(
    selected: str, result: dict
) -> None:
    client = client_for(
        lambda request: httpx.Response(200, json={"results": [result]})
    )
    verification = AddressVerificationService(client).verify(selected, selected)
    assert verification.verification_status == "verified"


def test_free_text_locality_variation_is_supported_by_matching_postcode() -> None:
    result = tomtom_result(locality="City of Melbourne")
    client = client_for(
        lambda request: httpx.Response(200, json={"results": [result]})
    )
    verification = AddressVerificationService(client).verify(
        "1 Treasury Rd East Melbourne VIC 3002"
    )
    assert verification.verification_status == "unverified"

    verification = AddressVerificationService(client).verify(
        "1 Treasury Pl Melbourne CBD VIC 3002"
    )
    assert verification.verification_status == "verified"


def test_selected_suggestion_rejects_clear_locality_and_postcode_contradiction() -> None:
    client = client_for(
        lambda request: httpx.Response(200, json={"results": [tomtom_result()]})
    )
    verification = AddressVerificationService(client).verify(
        "1 Treasury Place Carlton VIC 3053",
        "1 Treasury Place Carlton VIC 3053",
    )
    assert verification.verification_status == "unverified"


def test_selected_suggestion_without_coordinates_is_not_verified() -> None:
    result = tomtom_result(with_position=False)
    client = client_for(
        lambda request: httpx.Response(200, json={"results": [result]})
    )
    verification = AddressVerificationService(client).verify(
        "1 Treasury Place East Melbourne VIC 3002",
        "1 Treasury Place East Melbourne VIC 3002",
    )
    assert verification.verification_status == "unverified"
    assert verification.latitude is None


def test_unit_input_verifies_only_the_base_address_and_preserves_unit() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.params["query"] == "1 Treasury Place East Melbourne VIC 3002"
        return httpx.Response(200, json={"results": [tomtom_result()]})

    verification = AddressVerificationService(client_for(handler)).verify(
        "4/1 Treasury Place East Melbourne VIC 3002"
    )
    assert verification.verification_status == "verified"
    assert verification.unit_number == "4"
    assert verification.canonical_address == "4/1 Treasury Place East Melbourne VIC 3002"
    assert "not independently verified" in (verification.verification_message or "")
    assert calls == 1


def test_unit_input_does_not_accept_a_different_base_house_number() -> None:
    result = tomtom_result(house_number="4")
    client = client_for(
        lambda request: httpx.Response(200, json={"results": [result]})
    )
    verification = AddressVerificationService(client).verify(
        "4/84 Treasury Place East Melbourne VIC 3002"
    )
    assert verification.verification_status == "unverified"
    assert verification.latitude is None


def test_missing_coordinates_cannot_be_verified() -> None:
    client = client_for(
        lambda request: httpx.Response(
            200, json={"results": [tomtom_result(with_position=False)]}
        )
    )
    verification = AddressVerificationService(client).verify(
        "1 Treasury Place East Melbourne VIC 3002"
    )
    assert verification.verification_status == "unverified"


def test_reverse_returns_one_unverified_victorian_address() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/maps/orbis/places/reverseGeocode")
        assert request.url.params["position"] == "144.974948,-37.813232"
        assert request.url.params["radiusInMeters"] == "200"
        return httpx.Response(200, json={"results": [tomtom_result()]})

    results = client_for(handler).reverse(-37.813232, 144.974948)
    assert len(results) == 1
    assert results[0].verification_status == "unverified"
    assert results[0].latitude == pytest.approx(-37.8135811)


def test_reverse_locality_only_result_is_safe_and_unverified() -> None:
    result = tomtom_result(
        title="Sheoaks, She Oaks, VIC",
        result_type="area",
        house_number=None,
        street=None,
        locality="She Oaks",
        postcode=None,
    )
    client = client_for(
        lambda request: httpx.Response(200, json={"results": [result]})
    )
    values = client.reverse(-37.89, 144.126)
    assert values[0].address == "She Oaks VIC"
    assert values[0].street_number is None
    assert values[0].verification_status == "unverified"


def test_reverse_rejects_interstate_and_handles_no_results() -> None:
    result = tomtom_result(subdivision_code="AU-NSW")
    responses = iter(
        [
            httpx.Response(200, json={"results": [result]}),
            httpx.Response(200, json={"results": []}),
        ]
    )
    client = client_for(lambda request: next(responses))
    assert client.reverse(-37.8, 145.0) == []
    assert client.reverse(-37.8, 145.0) == []


def test_reverse_timeout_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret upstream detail", request=request)

    with pytest.raises(ExternalDataUnavailable, match="temporarily unavailable"):
        client_for(handler).reverse(-37.8, 145.0)


def test_reverse_malformed_payload_is_sanitized() -> None:
    client = client_for(lambda request: httpx.Response(200, json={"results": {}}))
    with pytest.raises(ExternalDataUnavailable, match="invalid data"):
        client.reverse(-37.8, 145.0)


def test_reverse_outside_victoria_avoids_provider_call() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"results": []})

    assert client_for(handler).reverse(-33.0, 151.0) == []
    assert calls == 0
