import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.services import fdr_prediction


class FakeTimestamp:
    def __init__(self, value):
        self.month = value.month
        self.dayofyear = value.timetuple().tm_yday


class FakePandas:
    Timestamp = FakeTimestamp

    @staticmethod
    def DataFrame(rows):
        return rows


class FakeModel:
    def predict(self, features):
        assert features == [
            {"district": "Central", "month": 1, "day_of_year": 15}
        ]
        return [1]

    def predict_proba(self, features):
        return [[0.2, 0.8]]


class FakeJoblib:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def load(self, path):
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def model_path(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "fdr_model.joblib"
    path.write_bytes(b"test model placeholder")
    monkeypatch.setattr(fdr_prediction, "MODEL_PATH", path)
    return path


def set_runtime(monkeypatch, *, model=None, load_error=None):
    monkeypatch.setattr(
        fdr_prediction,
        "_load_ml_runtime",
        lambda: (FakeJoblib(model, load_error), FakePandas),
    )


def test_successful_prediction_has_the_public_response_schema(model_path, monkeypatch):
    set_runtime(monkeypatch, model=FakeModel())

    response = TestClient(app).get(
        "/api/v1/fdr/prediction?district=Central&date=2026-01-15"
    )

    assert response.status_code == 200
    assert response.json() == {
        "district": "Central",
        "date": "2026-01-15",
        "prediction_class": 1,
        "prediction_label": "Elevated",
        "elevated_probability": 0.8,
        "model_name": "Decision Tree",
        "disclaimer": (
            "This is a machine-learning estimate based on historical seasonal "
            "patterns. It is not an official Fire Danger Rating forecast and "
            "must not be used for emergency decisions."
        ),
    }


def test_invalid_district_returns_400():
    response = TestClient(app).get(
        "/api/v1/fdr/prediction?district=Unknown&date=2026-01-15"
    )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "Unsupported fire district."


@pytest.mark.parametrize("query", ["district=Central", "district=Central&date=not-a-date"])
def test_missing_or_invalid_date_returns_422(query):
    response = TestClient(app).get(f"/api/v1/fdr/prediction?{query}")

    assert response.status_code == 422


def test_missing_model_returns_503(tmp_path, monkeypatch):
    monkeypatch.setattr(fdr_prediction, "MODEL_PATH", tmp_path / "missing.joblib")

    response = TestClient(app).get(
        "/api/v1/fdr/prediction?district=Central&date=2026-01-15"
    )

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


def test_corrupt_model_returns_503(model_path, monkeypatch):
    set_runtime(monkeypatch, load_error=ValueError("corrupt model"))

    response = TestClient(app).get(
        "/api/v1/fdr/prediction?district=Central&date=2026-01-15"
    )

    assert response.status_code == 503


def test_deserialisation_or_version_failure_returns_503(model_path, monkeypatch):
    set_runtime(monkeypatch, load_error=ModuleNotFoundError("missing estimator class"))

    response = TestClient(app).get(
        "/api/v1/fdr/prediction?district=Central&date=2026-01-15"
    )

    assert response.status_code == 503


def test_prediction_failure_returns_503(model_path, monkeypatch):
    class FailingModel:
        def predict(self, features):
            raise RuntimeError("inference failed")

    set_runtime(monkeypatch, model=FailingModel())

    response = TestClient(app).get(
        "/api/v1/fdr/prediction?district=Central&date=2026-01-15"
    )

    assert response.status_code == 503


def test_incompatible_model_structure_returns_503(model_path, monkeypatch):
    set_runtime(monkeypatch, model=object())

    response = TestClient(app).get(
        "/api/v1/fdr/prediction?district=Central&date=2026-01-15"
    )

    assert response.status_code == 503


def test_missing_ml_runtime_does_not_block_app_startup_or_unrelated_endpoints():
    environment = os.environ.copy()
    backend_root = Path(__file__).resolve().parents[1]
    script = (
        "import sys; "
        "sys.modules['joblib'] = None; "
        "sys.modules['pandas'] = None; "
        "from fastapi.testclient import TestClient; "
        "from app.main import app; "
        "client = TestClient(app); "
        "assert client.get('/api/health').status_code == 200; "
        "assert client.post('/api/v1/households').status_code == 201; "
        "response = client.get('/api/v1/fdr/prediction?district=Central&date=2026-01-15'); "
        "assert response.status_code == 503, response.text"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
