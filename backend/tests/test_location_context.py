from contextlib import contextmanager

from data.scripts import location_context


def _stub_basic_spatial_queries(monkeypatch) -> dict:
    cursor = object()
    fire_history = {
        "historical_fire_record_count": 3,
        "last_recorded_burn_year": 2024,
        "most_recent_fire_date": "2024-02-03",
        "search_radius_km": 20,
    }

    @contextmanager
    def connection():
        class Connection:
            @contextmanager
            def cursor(self):
                yield cursor

        yield Connection()

    def check_bpa(actual_cursor, latitude, longitude):
        assert actual_cursor is cursor
        assert (latitude, longitude) == (-37.89, 144.12)
        return True

    def get_fire_district(actual_cursor, latitude, longitude):
        assert actual_cursor is cursor
        assert (latitude, longitude) == (-37.89, 144.12)
        return "Central"

    def get_fire_history_context(
        actual_cursor,
        latitude,
        longitude,
        radius_km,
    ):
        assert actual_cursor is cursor
        assert (latitude, longitude, radius_km) == (-37.89, 144.12, 20)
        return fire_history.copy()

    monkeypatch.setattr(location_context, "get_connection", connection)
    monkeypatch.setattr(location_context, "check_bpa", check_bpa)
    monkeypatch.setattr(location_context, "get_fire_district", get_fire_district)
    monkeypatch.setattr(
        location_context, "get_fire_history_context", get_fire_history_context
    )
    return fire_history


def test_get_location_context_returns_basic_spatial_context(monkeypatch) -> None:
    fire_history = _stub_basic_spatial_queries(monkeypatch)
    monkeypatch.setattr(
        location_context,
        "get_fire_history_points",
        lambda *_args, **_kwargs: [
            {
                "latitude": -37.9,
                "longitude": 144.1,
                "season": 2024,
                "start_date": "2024-02-03",
            }
        ],
        raising=False,
    )

    result = location_context.get_location_context(-37.89, 144.12)

    assert result == {
        "location": {
            "latitude": -37.89,
            "longitude": 144.12,
        },
        "is_bushfire_prone_area": True,
        "fire_district": "Central",
        "environmental_context": {
            "fire_history": fire_history,
        },
    }


def test_get_location_context_does_not_query_historical_fire_points(
    monkeypatch,
) -> None:
    _stub_basic_spatial_queries(monkeypatch)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("basic location context queried historical fire points")

    monkeypatch.setattr(
        location_context,
        "get_fire_history_points",
        fail_if_called,
        raising=False,
    )

    location_context.get_location_context(-37.89, 144.12)


def test_get_location_fire_district_runs_only_the_district_query(monkeypatch) -> None:
    cursor = object()
    calls = []

    @contextmanager
    def connection():
        class Connection:
            @contextmanager
            def cursor(self):
                yield cursor

        yield Connection()

    def district_lookup(actual_cursor, latitude, longitude):
        calls.append((actual_cursor, latitude, longitude))
        return "Central"

    monkeypatch.setattr(location_context, "get_connection", connection)
    monkeypatch.setattr(location_context, "get_fire_district", district_lookup)
    monkeypatch.setattr(
        location_context,
        "check_bpa",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("narrow lookup queried BPA")
        ),
    )
    monkeypatch.setattr(
        location_context,
        "get_fire_history_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("narrow lookup queried fire history")
        ),
    )

    result = location_context.get_location_fire_district(-37.89, 144.12)

    assert result == "Central"
    assert calls == [(cursor, -37.89, 144.12)]
