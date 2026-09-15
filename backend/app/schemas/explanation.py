"""Generated-explanation API contract."""

from pydantic import BaseModel


class RendezvousExplanation(BaseModel):
    """A short passage about a simulation result, or nothing plus why.

    `reason` is diagnostic. The interface never renders it: a user who asked for
    an explanation and did not get one is shown nothing, not an apology.
    """

    explanation: str | None = None
    reason: str | None = None
