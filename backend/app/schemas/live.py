"""Request and response models for the voice assistant endpoints."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_SDP_LENGTH = 65536
MAX_UTTERANCE_LENGTH = 300
MAX_LABEL_LENGTH = 40

Emotion = Literal["calm", "worried", "urgent", "frustrated", "playful"]


class LiveSessionRequest(BaseModel):
    """The browser's WebRTC offer. Never logged."""

    model_config = ConfigDict(extra="forbid")

    # Deliberately not stripped: every SDP line, the last one included, must end with
    # CRLF, and OpenAI rejects an offer whose final line break was removed.
    sdp: Annotated[str, StringConstraints(min_length=1, max_length=MAX_SDP_LENGTH)]

    @field_validator("sdp")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("The offer must not be blank.")
        return value


class LiveSessionRef(BaseModel):
    id: str


class LiveTransport(BaseModel):
    type: Literal["webrtc"] = "webrtc"
    # An empty answer cannot be applied by the browser, so it is never a valid result.
    sdp: str = Field(min_length=1)


class LiveSessionResponse(BaseModel):
    """The created session id and the SDP answer the browser must apply."""

    session: LiveSessionRef
    transport: LiveTransport


class DecideRequest(BaseModel):
    """What the browser heard and where the person is. Never household data."""

    model_config = ConfigDict(extra="forbid")

    utterance: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_UTTERANCE_LENGTH),
    ]
    page: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=MAX_LABEL_LENGTH)
    ] = ""
    last_readout: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=MAX_LABEL_LENGTH)
    ] = ""


class ActionDecision(BaseModel):
    """One action from the closed list, how sure the chooser was, and how the speaker sounded."""

    action: str
    confidence: float
    # Only ever changes the character's face for a moment; never what the app does.
    emotion: Emotion = "calm"
