"""Machine-learning service for FDR historical-pattern prediction."""

from datetime import date
from pathlib import Path

import joblib
import pandas as pd

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


class FdrPredictionService:
    """Load the trained FDR model and produce historical-pattern estimates."""

    def __init__(self):
        if not MODEL_PATH.exists():
            raise RuntimeError(
                f"FDR model file was not found at {MODEL_PATH}"
            )

        self.model = joblib.load(MODEL_PATH)

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

        timestamp = pd.Timestamp(target_date)

        features = pd.DataFrame(
            [
                {
                    "district": district,
                    "month": timestamp.month,
                    "day_of_year": timestamp.dayofyear,
                }
            ]
        )

        prediction = int(self.model.predict(features)[0])

        prediction_label = (
            "Elevated"
            if prediction == 1
            else "Moderate"
        )

        elevated_probability = None

        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba(features)[0]

            elevated_probability = round(
                float(probabilities[1]),
                4,
            )

        return FdrPredictionResponse(
            district=district,
            date=target_date,
            prediction_class=prediction,
            prediction_label=prediction_label,
            elevated_probability=elevated_probability,
        )