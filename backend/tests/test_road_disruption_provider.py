import httpx
import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.providers.road_disruptions import VictorianRoadDisruptionClient


def make_client(handler):
    return VictorianRoadDisruptionClient(
        api_key="test-road-key",
        http_client=httpx.Client(
            transport=httpx.MockTransport(handler)
        ),
    )


def api_response(features):
    """Return the current Victorian DTP v3 API response shape."""
    return {
        "meta": {
            "total_records": len(features),
            "total_pages": 1,
            "page": 1,
            "limit": 100,
            "count": len(features),
        },
        "data": {
            "type": "FeatureCollection",
            "features": features,
        },
        "links": [],
    }


def test_missing_api_key_fails_explicitly():
    with pytest.raises(
        RuntimeError,
        match="VIC_ROAD_DISRUPTIONS_API_KEY",
    ):
        VictorianRoadDisruptionClient(api_key=None)


def test_active_nearby_disruption_is_returned():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["KeyID"] == "test-road-key"
        assert request.url.params["page"] == "1"
        assert request.url.params["limit"] == "100"

        return httpx.Response(
            200,
            json=api_response(
                [
                    {
                        "geometry": {
                            "type": "Point",
                            "coordinates": [144.9631, -37.8136],
                        },
                        "properties": {
                            "impactId": "impact-1",
                            "status": "Active",
                            "eventType": "Hazard",
                            "eventSubType": "Road Damage",
                            "closedRoadName": "Example Road",
                            "description": "Road damaged",
                            "impact": {"direction": "Both directions", "impactType": "Traffic affected"},
                            "lastUpdated": "2026-09-14T00:30:00Z",
                        },
                    }
                ]
            ),
        )

    client = make_client(handler)

    result = client.nearby_disruptions(
        -37.8136,
        144.9631,
        radius_km=10,
    )

    assert len(result) == 1

    disruption = result[0]
    assert disruption.disruption_id == "impact-1"
    assert disruption.event_type == "Hazard"
    assert disruption.event_subtype == "Road Damage"
    assert disruption.road_name == "Example Road"
    assert disruption.status == "Active"
    assert disruption.direction == "Both directions"
    assert disruption.impact == "direction: Both directions; impactType: Traffic affected"
    assert disruption.distance_km == pytest.approx(0.0, abs=0.01)


def test_line_disruption_marker_uses_nearest_reported_coordinate():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=api_response([{
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[145.5, -37.0], [144.9631, -37.8136]],
                },
                "properties": {"impactId": "line-1", "status": "Active"},
            }]),
        )

    result = make_client(handler).nearby_disruptions(
        -37.8136, 144.9631, radius_km=10
    )

    assert len(result) == 1
    assert result[0].latitude == -37.8136
    assert result[0].longitude == 144.9631


def test_inactive_disruption_is_ignored():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=api_response(
                [
                    {
                        "geometry": {
                            "type": "Point",
                            "coordinates": [144.9631, -37.8136],
                        },
                        "properties": {
                            "impactId": "impact-1",
                            "status": "Closed",
                            "eventType": "Hazard",
                        },
                    }
                ]
            ),
        )

    client = make_client(handler)

    result = client.nearby_disruptions(
        -37.8136,
        144.9631,
        radius_km=10,
    )

    assert result == []


def test_disruption_outside_radius_is_ignored():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=api_response(
                [
                    {
                        "geometry": {
                            "type": "Point",
                            "coordinates": [145.5, -37.0],
                        },
                        "properties": {
                            "impactId": "impact-far",
                            "status": "Active",
                        },
                    }
                ]
            ),
        )

    client = make_client(handler)

    result = client.nearby_disruptions(
        -37.8136,
        144.9631,
        radius_km=10,
    )

    assert result == []


def test_results_are_sorted_by_distance():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=api_response(
                [
                    {
                        "geometry": {
                            "type": "Point",
                            "coordinates": [145.00, -37.8136],
                        },
                        "properties": {
                            "impactId": "farther",
                            "status": "Active",
                        },
                    },
                    {
                        "geometry": {
                            "type": "Point",
                            "coordinates": [144.965, -37.8136],
                        },
                        "properties": {
                            "impactId": "nearer",
                            "status": "Active",
                        },
                    },
                ]
            ),
        )

    client = make_client(handler)

    result = client.nearby_disruptions(
        -37.8136,
        144.9631,
        radius_km=20,
    )

    assert [item.disruption_id for item in result] == [
        "nearer",
        "farther",
    ]


def test_malformed_payload_is_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"unexpected": "shape"},
        )

    client = make_client(handler)

    with pytest.raises(
        ExternalDataUnavailable,
        match="could not be read",
    ):
        client.nearby_disruptions(
            -37.8136,
            144.9631,
            radius_km=10,
        )


def test_http_failure_is_translated():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "offline",
            request=request,
        )

    client = make_client(handler)

    with pytest.raises(
        ExternalDataUnavailable,
        match="temporarily unavailable",
    ):
        client.nearby_disruptions(
            -37.8136,
            144.9631,
            radius_km=10,
        )


def test_invalid_radius_rejected():
    client = VictorianRoadDisruptionClient(
        api_key="test-road-key",
    )

    with pytest.raises(
        ValueError,
        match="radius_km must be greater than 0",
    ):
        client.nearby_disruptions(
            -37.8136,
            144.9631,
            radius_km=0,
        )
