from datetime import date

import pytest

from data.scripts import open_data_mysql


class FakeConnection:
    def close(self) -> None:
        pass


def clear_timeout_environment(monkeypatch) -> None:
    for name in open_data_mysql.OPEN_DATA_DB_TIMEOUT_DEFAULTS:
        monkeypatch.delenv(name, raising=False)


def set_connection_environment(monkeypatch) -> None:
    monkeypatch.setenv("MYSQL_USER", "test_user")
    monkeypatch.setenv("MYSQL_PASSWORD", "test_password")
    monkeypatch.setenv("MYSQL_DATABASE", "test_database")


def test_open_data_timeout_defaults_are_finite(monkeypatch) -> None:
    clear_timeout_environment(monkeypatch)

    assert open_data_mysql.get_open_data_db_timeouts() == {
        "connect_timeout": 5,
        "read_timeout": 15,
        "write_timeout": 10,
    }


def test_open_data_timeout_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("APP_OPEN_DATA_DB_CONNECT_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("APP_OPEN_DATA_DB_READ_TIMEOUT_SECONDS", "21")
    monkeypatch.setenv("APP_OPEN_DATA_DB_WRITE_TIMEOUT_SECONDS", "12")

    assert open_data_mysql.get_open_data_db_timeouts() == {
        "connect_timeout": 7,
        "read_timeout": 21,
        "write_timeout": 12,
    }


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "invalid"])
def test_invalid_open_data_timeout_fails_safely(
    monkeypatch, value: str
) -> None:
    monkeypatch.setenv("APP_OPEN_DATA_DB_READ_TIMEOUT_SECONDS", value)

    with pytest.raises(RuntimeError, match="positive integer"):
        open_data_mysql.get_open_data_db_timeouts()


def test_get_connection_passes_configured_timeouts(monkeypatch) -> None:
    set_connection_environment(monkeypatch)
    monkeypatch.setenv("APP_OPEN_DATA_DB_CONNECT_TIMEOUT_SECONDS", "6")
    monkeypatch.setenv("APP_OPEN_DATA_DB_READ_TIMEOUT_SECONDS", "18")
    monkeypatch.setenv("APP_OPEN_DATA_DB_WRITE_TIMEOUT_SECONDS", "9")
    captured = {}

    def connect(**kwargs):
        captured.update(kwargs)
        return FakeConnection()

    monkeypatch.setattr(open_data_mysql.pymysql, "connect", connect)

    with open_data_mysql.get_connection():
        pass

    assert captured["connect_timeout"] == 6
    assert captured["read_timeout"] == 18
    assert captured["write_timeout"] == 9
    assert captured["user"] == "test_user"
    assert captured["database"] == "test_database"


class PointCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.parameters = ()

    def execute(self, sql, parameters) -> None:
        self.sql = sql
        self.parameters = parameters

    def fetchall(self):
        return [
            {
                "latitude": -37.70,
                "longitude": 145.20,
                "season": 2025,
                "start_date": date(2025, 2, 3),
                "distance_meters": 5400.0,
            },
            {
                "latitude": -37.71,
                "longitude": 145.19,
                "season": 2024,
                "start_date": None,
                "distance_meters": 3250.0,
            },
        ]


def test_historical_fire_points_query_is_bounded_and_deterministic() -> None:
    cursor = PointCursor()

    result = open_data_mysql.get_fire_history_points(
        cursor, -37.74, 145.21, radius_km=20, limit=2
    )

    assert "LIMIT %s" in cursor.sql
    assert "ST_Distance_Sphere" in cursor.sql
    assert "start_date DESC" in cursor.sql
    assert "season DESC" in cursor.sql
    assert "fire_history_id DESC" in cursor.sql
    assert cursor.parameters[0] == "POINT(145.21 -37.74)"
    assert cursor.parameters[1].startswith("POLYGON((")
    assert cursor.parameters[-1] == 2
    assert result == [
        {
            "latitude": -37.70,
            "longitude": 145.20,
            "season": 2025,
            "start_date": "2025-02-03",
            "distance_km": 5.4,
        },
        {
            "latitude": -37.71,
            "longitude": 145.19,
            "season": 2024,
            "start_date": None,
            "distance_km": 3.25,
        },
    ]


@pytest.mark.parametrize("limit", [0, -1, 1.5, True])
def test_historical_fire_points_rejects_invalid_limit(limit) -> None:
    with pytest.raises(ValueError, match="positive"):
        open_data_mysql.get_fire_history_points(
            PointCursor(), -37.74, 145.21, limit=limit
        )


class NearestPointCursor(PointCursor):
    def fetchone(self):
        return {
            "latitude": -37.735,
            "longitude": 145.205,
            "season": 2019,
            "start_date": date(2019, 1, 12),
            "distance_meters": 812.5,
        }


def test_nearest_fire_query_searches_the_full_radius_and_returns_distance() -> None:
    cursor = NearestPointCursor()

    result = open_data_mysql.get_nearest_fire_history_point(
        cursor, -37.74, 145.21, radius_km=20
    )

    assert "WITH candidates AS" in cursor.sql
    assert "MBRContains" in cursor.sql
    assert "ST_Distance_Sphere" in cursor.sql
    assert "ORDER BY distance_meters ASC" in cursor.sql
    assert "LIMIT 1" in cursor.sql
    assert cursor.parameters[-1] == 20_000
    assert result == {
        "latitude": -37.735,
        "longitude": 145.205,
        "season": 2019,
        "start_date": "2019-01-12",
        "distance_km": 0.8125,
    }


def test_nearest_fire_query_returns_none_when_the_radius_is_empty() -> None:
    cursor = NearestPointCursor()
    cursor.fetchone = lambda: None

    assert (
        open_data_mysql.get_nearest_fire_history_point(
            cursor, -37.74, 145.21, radius_km=20
        )
        is None
    )
