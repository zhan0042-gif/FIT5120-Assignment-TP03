"""Request and response contracts for FDR historical-pattern prediction."""

from datetime import date

from pydantic import BaseModel, Field


class FdrPredictionResponse(BaseModel):
    """Historical-pattern classification produced by the FDR model."""

    district: str
    date: date

    prediction_class: int = Field(
        description="0 = Moderate, 1 = Elevated."
    )
    prediction_label: str

    elevated_probability: float | None = None

    model_name: str = "Decision Tree"

    disclaimer: str = (
        "This is a machine-learning estimate based on historical seasonal "
        "patterns. It is not an official Fire Danger Rating forecast and "
        "must not be used for emergency decisions."
    )