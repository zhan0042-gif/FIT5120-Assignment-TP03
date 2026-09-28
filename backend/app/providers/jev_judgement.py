"""JEV judgement engine adapter.

JEV answers a batch of small typed questions about a spoken command in one
request, with a probability per answer, and never writes text.

Only the disabled stand-in lives here for now. The live client joins it once
JEV's interface documentation is available (see the voice control design spec,
"Open until JEV's documentation arrives").
"""

from app.core.exceptions import ExternalDataUnavailable
from app.schemas.voice import VoiceAnswer, VoiceQuestion, VoiceState


class DisabledJudgementClient:
    """Stands in when voice judging is switched off.

    Voice control is an optional extra. Switched off, it refuses politely and
    the endpoint answers 503; the rest of the application is unaffected.
    """

    def judge(
        self, state: VoiceState, questions: list[VoiceQuestion]
    ) -> list[VoiceAnswer]:
        raise ExternalDataUnavailable("Voice commands are not configured.")
