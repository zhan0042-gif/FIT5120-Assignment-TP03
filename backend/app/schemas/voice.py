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
