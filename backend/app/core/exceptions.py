"""Application exceptions translated to HTTP responses at the API boundary."""


class ApplicationError(Exception):
    """Base class for expected application failures."""


class HouseholdNotFound(ApplicationError):
    pass


class PlanNotFound(ApplicationError):
    pass


class LocationNotFound(ApplicationError):
    pass


class UnsupportedScenario(ApplicationError):
    pass


class ScenarioNotApplicable(ApplicationError):
    pass


class TestResultNotFound(ApplicationError):
    pass


class ExternalDataUnavailable(ApplicationError):
    pass


class DatabaseUnavailable(ApplicationError):
    pass


class AddressResolutionError(ApplicationError):
    pass


class PlanValidationError(ApplicationError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))
