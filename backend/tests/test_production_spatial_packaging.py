from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_backend_image_does_not_copy_geoparquet_or_legacy_lookup() -> None:
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert ".parquet" not in dockerfile
    assert "fire_history_lookup.py" not in dockerfile
    assert "location_context.py" in dockerfile
    assert "open_data_mysql.py" in dockerfile


def test_backend_runtime_dependencies_exclude_geoparquet_stack() -> None:
    requirements = (
        ROOT / "backend" / "requirements.txt"
    ).read_text(encoding="utf-8").casefold()

    assert "geopandas" not in requirements
    assert "pyarrow" not in requirements


def test_data_tooling_has_dedicated_geospatial_dependencies() -> None:
    requirements = (
        ROOT / "data" / "requirements.txt"
    ).read_text(encoding="utf-8").casefold()

    for dependency in ("geopandas", "pandas", "pyarrow", "pymysql", "shapely"):
        assert dependency in requirements


def test_python_package_does_not_bundle_processed_parquet() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "processed/*.parquet" not in pyproject
