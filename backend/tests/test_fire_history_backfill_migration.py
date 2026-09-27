from importlib import import_module
import inspect

import pytest

backfill_fire_history_area_009 = import_module(
    "database.data_migrations.009_backfill_fire_history_area"
)


def test_backfill_verification_accepts_equal_source_and_database_counts() -> None:
    backfill_fire_history_area_009.validate_backfill_result(3, 3, 0)
    backfill_fire_history_area_009.validate_backfill_result(17, 17, 0)


@pytest.mark.parametrize("database_row_count", [4, 6])
def test_backfill_verification_rejects_database_row_count_mismatch(
    database_row_count,
) -> None:
    with pytest.raises(RuntimeError, match="row-count mismatch"):
        backfill_fire_history_area_009.validate_backfill_result(
            5,
            database_row_count,
            0,
        )


def test_backfill_verification_rejects_empty_source() -> None:
    with pytest.raises(RuntimeError, match="source contains zero rows"):
        backfill_fire_history_area_009.validate_backfill_result(0, 0, 0)


def test_backfill_verification_rejects_null_area_values() -> None:
    with pytest.raises(RuntimeError, match="without area_ha"):
        backfill_fire_history_area_009.validate_backfill_result(5, 5, 1)


def test_backfill_source_count_comes_from_parquet_metadata() -> None:
    run_source = inspect.getsource(backfill_fire_history_area_009.run)

    assert "source.metadata.num_rows" in run_source
    assert "628308" not in run_source
