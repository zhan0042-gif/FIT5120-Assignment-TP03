"""OpenAI GPT-Live adapter: exchange a browser's WebRTC offer for a session answer.

The session configuration, including the conversation prompt, lives only here on the
server. The browser never sees the API key or the prompt. Plain httpx, no SDK.
Nothing here logs the offer or the answer.
"""

import httpx
from pydantic import ValidationError

from app.core.exceptions import ExternalDataUnavailable
from app.schemas.live import LiveSessionRef, LiveSessionResponse, LiveTransport

LIVE_URL = "https://api.openai.com/v1/live/sessions"
LIVE_MODEL = "gpt-live-1"

LIVE_INSTRUCTIONS = """\
You are a calm, friendly voice assistant inside a household bushfire-preparedness app. \
Speak English only, at an unhurried pace. Keep every reply to one or two short sentences.

You never give bushfire safety advice, weather, fire danger, fire history or any figure \
from your own knowledge. You only say what the app tells you.

Delegation policy:
Delegate to the backend, every time, when the user:
- asks about bushfire safety, when to leave, what to pack, pets or animals, staying to \
defend, or says anything that sounds like an emergency;
- asks to open, show, go to or go back to any page of the app, to scroll up or down, to go to \
the top or bottom of a page, or to jump to a part of a page;
- asks for the weather, the fire danger rating, fire history, the plan or road disruptions;
- asks you to repeat or say again anything you read out.
Do not delegate when the user only greets you or thanks you, or when you need one short \
question to understand what they want.

While delegated work runs, say one short acknowledgement such as "Let me check that." \
Do not guess the result. Never read out or invent any number yourself. When the backend \
gives you text, say it in your own words without changing any number, name, date or \
warning, and without adding reassurance. If the backend says something is unavailable, \
say so plainly.
"""


class OpenAILiveSessionClient:
    """Create a GPT-Live session with client delegation and return the SDP answer."""

    def __init__(
        self,
        *,
        api_key: str | None,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required when voice is enabled.")
        self._api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx.Client(
            timeout=timeout_seconds, follow_redirects=True
        )

    def create(self, sdp: str) -> LiveSessionResponse:
        body = {
            "session": {
                "model": LIVE_MODEL,
                "instructions": LIVE_INSTRUCTIONS,
                "delegation": {"type": "client"},
            },
            "transport": {"type": "webrtc", "sdp": sdp},
        }
        try:
            response = self.http_client.post(
                LIVE_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalDataUnavailable(
                "The voice service is temporarily unavailable."
            ) from exc

        try:
            return LiveSessionResponse(
                session=LiveSessionRef(id=data["session"]["id"]),
                transport=LiveTransport(sdp=data["transport"]["sdp"]),
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise ExternalDataUnavailable("The voice service response could not be read.") from exc


class DisabledLiveSessionClient:
    """Stands in when no OpenAI key is configured, so the app still starts."""

    def create(self, sdp: str) -> LiveSessionResponse:
        raise ExternalDataUnavailable("No voice service is configured.")
