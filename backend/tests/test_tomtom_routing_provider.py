import json

import httpx
import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.providers.tomtom_routing import TomTomRoutingClient

MATRIX_RESPONSE = {
    "data": [
        {"originIndex": 0, "destinationIndex": 0,
         "routeSummary": {"lengthInMeters": 1167, "travelTimeInSeconds": 389,
                          "trafficDelayInSeconds": 0}},
        {"originIndex": 1, "destinationIndex": 0,
         "routeSummary": {"lengthInMeters": 2977, "travelTimeInSeconds": 727,
                          "trafficDelayInSeconds": 12}},
    ]
}

ORIGINS = [(-37.8136, 144.9631), (-37.7963, 144.9524)]
DESTINATION = (-37.8100, 144.9700)


def _client(handler) -> TomTomRoutingClient:
    return TomTomRoutingClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_requires_an_api_key() -> None:
    with pytest.raises(RuntimeError, match="TOMTOM_API_KEY"):
        TomTomRoutingClient(api_key=None)


def test_sends_every_origin_and_one_destination_in_a_single_request() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=MATRIX_RESPONSE)

    _client(handler).travel_times(origins=ORIGINS, destination=DESTINATION)

    assert len(seen["body"]["origins"]) == 2
    assert len(seen["body"]["destinations"]) == 1
    assert seen["body"]["origins"][0]["point"] == {
        "latitude": -37.8136, "longitude": 144.9631
    }
    assert "key=test-key" in seen["url"]


def test_parses_legs_in_origin_order() -> None:
    legs = _client(lambda request: httpx.Response(200, json=MATRIX_RESPONSE)).travel_times(
        origins=ORIGINS, destination=DESTINATION
    )

    assert [leg.origin_index for leg in legs] == [0, 1]
    assert legs[0].travel_seconds == 389
    assert legs[1].distance_meters == 2977
    assert legs[1].traffic_delay_seconds == 12


def test_http_error_becomes_external_data_unavailable() -> None:
    client = _client(lambda request: httpx.Response(503, json={"error": "busy"}))

    with pytest.raises(ExternalDataUnavailable):
        client.travel_times(origins=ORIGINS, destination=DESTINATION)


def test_timeout_becomes_external_data_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(ExternalDataUnavailable):
        _client(handler).travel_times(origins=ORIGINS, destination=DESTINATION)


def test_malformed_payload_becomes_external_data_unavailable() -> None:
    client = _client(lambda request: httpx.Response(200, json={"data": [{"nope": 1}]}))

    with pytest.raises(ExternalDataUnavailable):
        client.travel_times(origins=ORIGINS, destination=DESTINATION)


def test_no_origins_short_circuits_without_calling_the_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call TomTom with no origins")

    assert _client(handler).travel_times(origins=[], destination=DESTINATION) == []
