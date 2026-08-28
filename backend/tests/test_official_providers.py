from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

import httpx
import pytest

from app.core.config import build_external_providers
from app.core.exceptions import AddressResolutionError, ExternalDataUnavailable
from app.providers.bom import (
    BOMWeatherClient,
    haversine_km,
    parse_bom_observations,
    select_nearest_weather,
)
from app.providers.bom_fire_danger import (
    BOMFireDangerClient,
    BOM_FIRE_DISTRICTS,
    fire_danger_for_district,
    normalize_bom_fire_district,
    parse_bom_fire_danger_product,
)
from app.providers.cfa import (
    CFA_FEED_URLS,
    CFAFireDangerClient,
    normalize_district,
    parse_cfa_feed,
    parse_cfa_fire_danger,
)
from app.providers.mock import MockAddressClient
from app.providers.vicmap import VicmapAddressClient


FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 8, 28, 6, 0, tzinfo=timezone.utc)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def vicmap_feature(
    address: str = "1 TREASURY PLACE EAST MELBOURNE 3002",
    *,
    state: str = "VIC",
    longitude: float = 144.9749477,
    latitude: float = -37.8132320,
) -> dict:
    return {
        "attributes": {
            "ezi_address": address,
            "locality_name": "EAST MELBOURNE",
            "state": state,
            "postcode": "3002",
        },
        "geometry": {"x": longitude, "y": latitude},
    }


def test_vicmap_exact_match_returns_standardized_wgs84_location() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["returnGeometry"] == "true"
        assert request.url.params["outSR"] == "4326"
        assert "UPPER(ezi_address) =" in request.url.params["where"]
        return httpx.Response(200, json={"features": [vicmap_feature()]})

    client = VicmapAddressClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    result = client.resolve("1 Treasury Place, East Melbourne VIC 3002")

    assert result.address == "1 TREASURY PLACE EAST MELBOURNE VIC 3002"
    assert result.latitude == pytest.approx(-37.8132320)
    assert result.longitude == pytest.approx(144.9749477)


def test_vicmap_unique_partial_match_is_accepted() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        features = [] if calls == 1 else [vicmap_feature()]
        return httpx.Response(200, json={"features": features})

    client = VicmapAddressClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    result = client.resolve("1 Treasury Place East Melbourne")

    assert calls == 2
    assert result.address.endswith("VIC 3002")


def test_vicmap_no_match_is_controlled() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"features": []})
    )
    client = VicmapAddressClient(http_client=httpx.Client(transport=transport))

    with pytest.raises(AddressResolutionError, match="No matching Victorian"):
        client.resolve("999 Missing Road Nowhere VIC 3999")


def test_vicmap_ambiguous_match_is_rejected() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        features = [] if calls == 1 else [
            vicmap_feature(),
            vicmap_feature(
                "1 TREASURY PLACE CRAIGIEBURN 3064",
                longitude=144.9401190,
                latitude=-37.5860400,
            ),
        ]
        return httpx.Response(200, json={"features": features})

    client = VicmapAddressClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(AddressResolutionError, match="multiple Victorian"):
        client.resolve("1 Treasury Place")


def test_vicmap_interstate_result_is_rejected() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"features": [vicmap_feature(state="NSW")]}
        )
    )
    client = VicmapAddressClient(http_client=httpx.Client(transport=transport))

    with pytest.raises(AddressResolutionError, match="No matching Victorian"):
        client.resolve("1 Treasury Place East Melbourne 3002")


def test_vicmap_malformed_provider_result_is_unavailable() -> None:
    malformed = vicmap_feature()
    malformed.pop("geometry")
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"features": [malformed]})
    )
    client = VicmapAddressClient(http_client=httpx.Client(transport=transport))

    with pytest.raises(ExternalDataUnavailable, match="invalid"):
        client.resolve("1 Treasury Place East Melbourne 3002")


def test_vicmap_timeout_is_translated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timeout", request=request)

    client = VicmapAddressClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ExternalDataUnavailable, match="address data is unavailable"):
        client.resolve("1 Treasury Place East Melbourne 3002")


def test_cfa_verified_district_mapping_and_normalization() -> None:
    assert len(CFA_FEED_URLS) == 9
    assert normalize_district("  west AND south gippsland ") == (
        "West and South Gippsland"
    )
    assert CFA_FEED_URLS["Central"].endswith("central-firedistrict_rss.xml")
    with pytest.raises(ExternalDataUnavailable, match="not supported"):
        normalize_district("Somewhere Else")


def test_cfa_daily_forecast_and_extra_municipality_item() -> None:
    feed = parse_cfa_feed(fixture("cfa_forecast.xml"), "Central")
    result = parse_cfa_fire_danger(fixture("cfa_forecast.xml"), " central ")

    assert len(feed.daily) == 4
    assert [result.today, result.tomorrow, result.day_3, result.day_4] == [
        "Moderate",
        "High",
        "High",
        "Extreme",
    ]
    assert result.source_updated_at.isoformat() == "2026-08-28T16:00:00+10:00"
    assert result.source_url and result.source_url.startswith("https://www.cfa")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("cfa_no_rating.xml", "No Rating"),
        ("cfa_catastrophic.xml", "Catastrophic"),
    ],
)
def test_cfa_rating_normalization(name: str, expected: str) -> None:
    assert parse_cfa_fire_danger(fixture(name), "Central").today == expected


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("cfa_missing_item.xml", "four current forecast days"),
        ("cfa_malformed.xml", "feed is invalid"),
        ("cfa_unknown_rating.xml", "unsupported Fire Danger Rating"),
        ("cfa_missing_timestamp.xml", "issue time is unavailable"),
    ],
)
def test_cfa_invalid_or_incomplete_feed_is_unavailable(
    name: str, message: str
) -> None:
    with pytest.raises(ExternalDataUnavailable, match=message):
        parse_cfa_fire_danger(fixture(name), "Central")


def test_cfa_client_uses_cache() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=fixture("cfa_forecast.xml"))

    client = CFAFireDangerClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert client.get_fire_danger("Central").today == "Moderate"
    assert client.get_fire_danger(" central ").today == "Moderate"
    assert calls == 1


def test_cfa_connection_failure_is_translated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = CFAFireDangerClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ExternalDataUnavailable, match="CFA"):
        client.get_fire_danger("Central")


def test_bom_parser_skips_incomplete_station_and_parses_timestamp() -> None:
    observations = parse_bom_observations(fixture("bom_observations.xml"))
    names = {item.station_name for item in observations}

    assert "Nearest incomplete station" not in names
    assert "Fresh complete station" in names
    assert next(
        item for item in observations if item.station_name == "Fresh complete station"
    ).observed_at.isoformat() == "2026-08-28T05:50:00+00:00"


def test_bom_nearest_stale_or_incomplete_station_falls_through() -> None:
    weather = select_nearest_weather(
        parse_bom_observations(fixture("bom_observations.xml")),
        -37.8000,
        144.9000,
        now=NOW,
    )

    assert weather.station_name == "Fresh complete station"
    assert weather.temperature_c == 15.8
    assert weather.relative_humidity == 51
    assert weather.wind_direction == "WNW"
    assert weather.wind_speed_kmh == 7


def test_bom_nearest_fresh_complete_station_is_selected() -> None:
    weather = select_nearest_weather(
        parse_bom_observations(fixture("bom_observations.xml")),
        -38.1900,
        145.2900,
        now=NOW,
    )
    assert weather.station_name == "Far complete station"


def test_bom_no_fresh_valid_station_is_unavailable() -> None:
    with pytest.raises(ExternalDataUnavailable, match="sufficiently fresh"):
        select_nearest_weather(
            parse_bom_observations(fixture("bom_observations.xml")),
            -37.8,
            144.9,
            now=datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    "payload",
    [b"<product>", b"<product><observations /></product>"],
)
def test_bom_malformed_or_empty_xml_is_unavailable(payload: bytes) -> None:
    with pytest.raises(ExternalDataUnavailable):
        parse_bom_observations(payload)


def test_bom_haversine_and_client_cache() -> None:
    calls = 0

    def loader() -> bytes:
        nonlocal calls
        calls += 1
        return fixture("bom_observations.xml")

    client = BOMWeatherClient(loader=loader, now_provider=lambda: NOW)
    first = client.get_weather(-37.8, 144.9)
    second = client.get_weather(-37.8, 144.9)

    assert haversine_km(-37.8, 144.9, -37.8, 144.9) == pytest.approx(0)
    assert first.station_name == second.station_name
    assert calls == 1


def test_bom_transport_failure_is_translated() -> None:
    def failing_loader() -> bytes:
        raise TimeoutError("FTP timeout")

    client = BOMWeatherClient(loader=failing_loader, now_provider=lambda: NOW)
    with pytest.raises(ExternalDataUnavailable, match="BOM"):
        client.get_weather(-37.8, 144.9)


def test_bom_fire_danger_parses_all_districts_and_exact_four_days() -> None:
    forecast = parse_bom_fire_danger_product(fixture("bom_fire_danger.xml"))
    result = fire_danger_for_district(forecast, " central ")

    assert set(forecast.ratings) == set(BOM_FIRE_DISTRICTS)
    assert all(len(values) == 4 for values in forecast.ratings.values())
    assert forecast.fire_behaviour_indices["Central"] == (13, 24, 50, 100)
    assert [result.today, result.tomorrow, result.day_3, result.day_4] == [
        "Moderate",
        "High",
        "Extreme",
        "Catastrophic",
    ]
    assert result.source_updated_at.isoformat() == "2026-08-28T16:00:00+10:00"
    assert result.source_url == (
        "ftp://ftp.bom.gov.au/anon/gen/fwo/IDV18555.xml"
    )


def test_bom_fire_danger_district_normalization_is_strict() -> None:
    assert normalize_bom_fire_district(" WEST and south GIPPSLAND ") == (
        "West and South Gippsland"
    )
    with pytest.raises(ExternalDataUnavailable, match="not supported"):
        normalize_bom_fire_district("Somewhere Else")


def test_bom_fire_danger_client_uses_one_cached_state_product() -> None:
    calls = 0

    def loader() -> bytes:
        nonlocal calls
        calls += 1
        return fixture("bom_fire_danger.xml")

    client = BOMFireDangerClient(loader=loader, now_provider=lambda: NOW)

    assert client.get_fire_danger("Central").today == "Moderate"
    assert client.get_fire_danger("Mallee").today == "Catastrophic"
    assert calls == 1


def test_bom_fire_danger_stale_product_is_unavailable() -> None:
    client = BOMFireDangerClient(
        loader=lambda: fixture("bom_fire_danger.xml"),
        now_provider=lambda: datetime(2026, 8, 30, 7, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(ExternalDataUnavailable, match="stale"):
        client.get_fire_danger("Central")


def test_bom_fire_danger_missing_district_is_unavailable() -> None:
    root = ElementTree.fromstring(fixture("bom_fire_danger.xml"))
    forecast = root.find("forecast")
    assert forecast is not None
    forecast.remove(forecast.findall("area")[0])

    with pytest.raises(ExternalDataUnavailable, match="all nine"):
        parse_bom_fire_danger_product(ElementTree.tostring(root))


def test_bom_fire_danger_missing_day_is_unavailable() -> None:
    root = ElementTree.fromstring(fixture("bom_fire_danger.xml"))
    area = root.find("./forecast/area[@description='Central']")
    assert area is not None
    area.remove(area.findall("forecast-period")[-1])

    with pytest.raises(ExternalDataUnavailable, match="exactly four"):
        parse_bom_fire_danger_product(ElementTree.tostring(root))


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"<product>", "product is invalid"),
        (
            fixture("bom_fire_danger.xml").replace(
                b"<issue-time-local tz=\"EST\">2026-08-28T16:00:00+10:00</issue-time-local>",
                b"",
            ),
            "issue time is unavailable",
        ),
        (
            fixture("bom_fire_danger.xml").replace(
                b">Catastrophic</text>", b">Severe</text>", 1
            ),
            "unsupported Fire Danger Rating",
        ),
    ],
)
def test_bom_fire_danger_invalid_payload_is_unavailable(
    payload: bytes, message: str
) -> None:
    with pytest.raises(ExternalDataUnavailable, match=message):
        parse_bom_fire_danger_product(payload)


def test_bom_fire_danger_transport_failure_is_translated() -> None:
    def failing_loader() -> bytes:
        raise TimeoutError("FTP timeout")

    client = BOMFireDangerClient(loader=failing_loader, now_provider=lambda: NOW)
    with pytest.raises(ExternalDataUnavailable, match="BOM"):
        client.get_fire_danger("Central")


def test_explicit_provider_modes_do_not_fallback() -> None:
    assert isinstance(build_external_providers("mock").address, MockAddressClient)
    assert isinstance(build_external_providers("live").address, VicmapAddressClient)
    assert isinstance(
        build_external_providers("live").fire_danger, BOMFireDangerClient
    )
    with pytest.raises(RuntimeError, match="either 'mock' or 'live'"):
        build_external_providers("automatic")
