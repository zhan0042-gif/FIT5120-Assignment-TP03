"""Preparedness scenario API contracts."""

from datetime import datetime

from pydantic import BaseModel


class BasicScenario(BaseModel):
    scenario_id: str
    title: str
    description: str


class ScenarioTestRequest(BaseModel):
    scenario_id: str


class ScenarioCheck(BaseModel):
    check: str
    status: str
    message: str


class FirstProblem(BaseModel):
    section: str
    message: str


class ScenarioTestResult(BaseModel):
    test_run_id: str
    scenario_id: str
    overall_status: str
    checks: list[ScenarioCheck]
    first_problem: FirstProblem | None
    tested_at: datetime

