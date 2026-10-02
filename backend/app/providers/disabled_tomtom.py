"""Explicit unavailable boundaries, never fabricated address/route data."""

from app.core.exceptions import ExternalDataUnavailable


class DisabledTomTomAddressClient:
    def resolve(self, address, *, provider_reference=None):
        raise ExternalDataUnavailable("Address verification is not configured.")

    def suggest(self, query, limit=8):
        raise ExternalDataUnavailable("Address search is not configured.")

    def reverse(self, latitude, longitude, limit=5):
        raise ExternalDataUnavailable("Address lookup is not configured.")


class DisabledTomTomRoutingClient:
    def travel_times(self, origins, destination):
        raise ExternalDataUnavailable("Travel time estimates are not configured.")

    def road_route(self, origin, destination):
        raise ExternalDataUnavailable("Road routing is not configured.")
