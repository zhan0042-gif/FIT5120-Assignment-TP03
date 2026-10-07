"""Request and response models for the voice assistant endpoints."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

MAX_SDP_LENGTH = 65536
MAX_UTTERANCE_LENGTH = 300
MAX_LABEL_LENGTH = 40


class LiveSessionRequest(BaseModel):
    """The browser's WebRTC offer. Never logged."""

    model_config = ConfigDict(extra="forbid")

    sdp: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_SDP_LENGTH),
    ]


class LiveSessionRef(BaseModel):
    id: str


class LiveTransport(BaseModel):
    type: Literal["webrtc"] = "webrtc"
    sdp: str


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
    """One action from the closed list and how sure the chooser was."""

    action: str
    confidence: float
