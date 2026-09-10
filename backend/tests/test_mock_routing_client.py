from app.providers.mock import MockRoutingClient


def test_returns_one_leg_per_origin_in_order() -> None:
    legs = MockRoutingClient().travel_times(
        origins=[(-37.8136, 144.9631), (-37.7963, 144.9524)],
        destination=(-37.8100, 144.9700),
    )

    assert [leg.origin_index for leg in legs] == [0, 1]


def test_a_further_origin_takes_longer() -> None:
    legs = MockRoutingClient().travel_times(
        origins=[(-37.8100, 144.9705), (-37.9500, 145.2000)],
        destination=(-37.8100, 144.9700),
    )

    assert legs[1].travel_seconds > legs[0].travel_seconds


def test_no_origins_returns_no_legs() -> None:
    assert MockRoutingClient().travel_times(origins=[], destination=(-37.81, 144.97)) == []
