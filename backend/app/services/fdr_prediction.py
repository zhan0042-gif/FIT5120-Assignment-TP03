"""Machine-learning service for FDR historical-pattern prediction."""

from datetime import date
from pathlib import Path
from typing import Any

from app.schemas.fdr_prediction import FdrPredictionResponse


MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "models"
    / "fdr_model.joblib"
)

VALID_DISTRICTS = {
    "Mallee",
    "Wimmera",
    "South West",
    "Northern Country",
    "North Central",
    "Central",
    "North East",
    "South and West Gippsland",
    "East Gippsland",
}


class FdrRuntimeUnavailable(RuntimeError):
    """The optional FDR model runtime cannot serve a prediction."""


def _load_ml_runtime() -> tuple[Any, Any]:
    """Import optional ML packages only when the FDR endpoint is used."""
    try:
        import joblib
        import pandas as pd
    except Exception as exc:
        raise FdrRuntimeUnavailable(
            "The fire danger pattern estimate is temporarily unavailable."
        ) from exc

    return joblib, pd


class FdrPredictionService:
    """Load the trained FDR model and produce historical-pattern estimates."""

    def __init__(self, model_path: Path | None = None):
        resolved_model_path = model_path or MODEL_PATH

        if not resolved_model_path.is_file():
            raise FdrRuntimeUnavailable(
                "The fire danger pattern estimate is temporarily unavailable."
            )

        joblib, self._pandas = _load_ml_runtime()

        try:
            self.model = joblib.load(resolved_model_path)
        except Exception as exc:
            raise FdrRuntimeUnavailable(
                "The fire danger pattern estimate is temporarily unavailable."
            ) from exc

        if not callable(getattr(self.model, "predict", None)):
            raise FdrRuntimeUnavailable(
                "The fire danger pattern estimate is temporarily unavailable."
            )

        predict_proba = getattr(self.model, "predict_proba", None)
        if predict_proba is not None and not callable(predict_proba):
            raise FdrRuntimeUnavailable(
                "The fire danger pattern estimate is temporarily unavailable."
            )

    def predict(
        self,
        district: str,
        target_date: date,
    ) -> FdrPredictionResponse:
        """
        Predict Moderate or Elevated historical FDR pattern.

        Args:
            district:
                Victorian fire weather district.
            target_date:
                Date for which seasonal features are created.

        Returns:
            FdrPredictionResponse:
                Model prediction and probability where available.
        """
        if district not in VALID_DISTRICTS:
            raise ValueError(
                f"Unsupported fire district: {district}"
            )

        try:
            timestamp = self._pandas.Timestamp(target_date)

            features = self._pandas.DataFrame(
                [
                    {
                        "district": district,
                        "month": timestamp.month,
                        "day_of_year": timestamp.dayofyear,
                    }
                ]
            )

            prediction = int(self.model.predict(features)[0])

            if prediction not in (0, 1):
                raise ValueError("The FDR model returned an unsupported class.")

            prediction_label = "Elevated" if prediction == 1 else "Moderate"
            elevated_probability = None
            predict_proba = getattr(self.model, "predict_proba", None)

            if predict_proba is not None:
                probabilities = predict_proba(features)[0]
                elevated_probability = round(float(probabilities[1]), 4)

                if not 0 <= elevated_probability <= 1:
                    raise ValueError("The FDR model returned an invalid probability.")

            return FdrPredictionResponse(
                district=district,
                date=target_date,
                prediction_class=prediction,
                prediction_label=prediction_label,
                elevated_probability=elevated_probability,
            )
        except FdrRuntimeUnavailable:
            raise
        except Exception as exc:
            raise FdrRuntimeUnavailable(
                "The fire danger pattern estimate is temporarily unavailable."
            ) from exc
