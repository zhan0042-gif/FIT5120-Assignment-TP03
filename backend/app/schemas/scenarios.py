"""Preparedness scenario API contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.households import CompletionSectionName


ScenarioId = Literal[
    "vehicle_unavailable",
    "person_unavailable",
    "destination_unavailable",
]


class BasicScenario(BaseModel):
    """A fixed I1 scenario with relevance evaluated for one saved plan."""

    scenario_id: ScenarioId
    title: str
    description: str
    enabled: bool
    disabled_reason: str | None


class ScenarioTestRequest(BaseModel):
    scenario_id: str


class ScenarioCheck(BaseModel):
    check: Literal[
        "backup_transport", "backup_driver", "backup_person", "backup_destination"
    ]
    status: Literal["pass", "fail", "not_checked"]
    message: str


class FirstProblem(BaseModel):
    section: CompletionSectionName
    message: str


class ScenarioTestResult(BaseModel):
    """Persisted outcome kept separate from the plan aggregate it evaluated."""

    test_run_id: str
    scenario_id: ScenarioId
    overall_status: Literal["pass", "needs_attention"]
    checks: list[ScenarioCheck]
    first_problem: FirstProblem | None
    result_reason: str
    tested_at: datetime
