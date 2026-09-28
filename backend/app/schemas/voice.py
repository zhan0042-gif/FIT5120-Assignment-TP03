"""Voice control API contract: a judgement batch and its answers.

The judge chooses among options the page offered. It never writes text, so a
batch is a set of small typed questions, and an answer is always one of the
options it was given ("yes"/"no" for a yes/no question).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

MAX_TRANSCRIPT_CHARS = 500
MAX_QUESTIONS = 100
MAX_OPTIONS = 100
MAX_TARGETS = 300

OptionText = Annotated[str, Field(min_length=1, max_length=300)]


class VoiceTarget(BaseModel):
    """What the page offers, as the judge sees it. Handlers stay in the browser."""

    id: str = Field(min_length=1, max_length=160)
    kind: Literal["page", "command", "button", "select", "text", "checkbox", "address"]
    label: str = Field(min_length=1, max_length=300)
    current: str | None = Field(default=None, max_length=MAX_TRANSCRIPT_CHARS)


class VoiceState(BaseModel):
    page: str = Field(min_length=1, max_length=80)
    step: str | None = Field(default=None, max_length=80)
    mode: Literal["normal", "confirming", "choosing"] = "normal"
    transcript: str = Field(min_length=1, max_length=MAX_TRANSCRIPT_CHARS)
    targets: list[VoiceTarget] = Field(default_factory=list, max_length=MAX_TARGETS)


class VoiceQuestion(BaseModel):
    id: str = Field(min_length=1, max_length=160)
    type: Literal["pick_one", "yes_no"]
    options: list[OptionText] = Field(default_factory=list, max_length=MAX_OPTIONS)

    @model_validator(mode="after")
    def _options_fit_the_type(self) -> "VoiceQuestion":
        if self.type == "pick_one" and not self.options:
            raise ValueError("A pick_one question needs at least one option.")
        if self.type == "yes_no" and self.options:
            raise ValueError("A yes_no question takes no options.")
        return self


class VoiceJudgeRequest(BaseModel):
    state: VoiceState
    questions: list[VoiceQuestion] = Field(min_length=1, max_length=MAX_QUESTIONS)

    @model_validator(mode="after")
    def _question_ids_are_unique(self) -> "VoiceJudgeRequest":
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("Question ids must be unique.")
        return self


class VoiceAnswer(BaseModel):
    """Deliberately unconstrained: the service decides whether to trust it."""

    id: str
    answer: str
    probability: float


class VoiceJudgeResponse(BaseModel):
    answers: list[VoiceAnswer]


class VoiceLoggedAnswer(BaseModel):
    """`answer` may be withheld; the probability always stays."""

    id: str = Field(min_length=1, max_length=160)
    answer: str | None = Field(default=None, max_length=300)
    probability: float = Field(ge=0.0, le=1.0)


class VoiceLoggedAction(BaseModel):
    """`target` is a target id, never a spoken label: labels can hold member names."""

    kind: Literal["page", "command", "button", "select", "text", "checkbox", "address"]
    target: str = Field(min_length=1, max_length=160)
    value: str | None = Field(default=None, max_length=MAX_TRANSCRIPT_CHARS)


class VoiceLatency(BaseModel):
    judge: int | None = Field(default=None, ge=0, le=600_000)
    turn: int = Field(ge=0, le=600_000)


class VoiceTurnLog(BaseModel):
    """One finished utterance: what was heard, what was chosen, what happened."""

    turn_id: str = Field(min_length=1, max_length=80)
    page: str | None = Field(default=None, max_length=80)
    step: str | None = Field(default=None, max_length=80)
    mode: Literal["normal", "confirming", "choosing", "dictating"]
    transcript: str | None = Field(default=None, max_length=MAX_TRANSCRIPT_CHARS)
    answers: list[VoiceLoggedAnswer] = Field(default_factory=list, max_length=MAX_QUESTIONS)
    decision: Literal[
        "execute", "confirm", "dictate", "choose", "keep", "reject",
        "stop", "cancel", "unclear", "dictated", "unavailable",
    ]
    action: VoiceLoggedAction | None = None
    outcome: Literal["ok", "fail", "pending", "none"]
    latency_ms: VoiceLatency


class VoiceLogAccepted(BaseModel):
    accepted: bool = True
