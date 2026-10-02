"""Normalised road routes for Travel Readiness; no route-safety assessment."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RoutePoint(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False, strict=True)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False, strict=True)


class RoadRoute(BaseModel):
    geometry: list[RoutePoint] = Field(min_length=2)
    distance_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    travel_time_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class DestinationRoute(BaseModel):
    status: Literal["available", "unavailable"]
    destination_type: Literal["primary", "backup"]
    destination_id: str
    destination_name: str
    destination_address: str | None = None
    origin: RoutePoint
    destination: RoutePoint
    geometry: list[RoutePoint] = Field(default_factory=list)
    distance_m: float | None = None
    travel_time_seconds: float | None = None
    unavailable_reason: str | None = None


class TravelRouteResult(BaseModel):
    status: Literal["available", "partial", "unavailable", "not_applicable"]
    checked_at: datetime
    routes: list[DestinationRoute] = Field(default_factory=list)
    unavailable_reason: str | None = None
