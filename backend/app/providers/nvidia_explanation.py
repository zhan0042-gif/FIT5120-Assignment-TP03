"""NVIDIA hosted-model adapter for explaining a rendezvous result.

Uses the OpenAI-shaped chat completions endpoint with plain httpx, matching the
other providers in this package. No SDK is added.

`chat_template_kwargs: {"thinking": false}` is load-bearing. This model family
reasons by default and writes that reasoning into `content`, which both slows
the call and truncates the answer before it arrives.
"""

from typing import Any

import httpx

from app.core.exceptions import ExternalDataUnavailable
from app.schemas.rendezvous import RendezvousResult

NVIDIA_CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "nvidia/nemotron-3-super-120b-a12b"

SYSTEM_PROMPT = (
    "You explain household bushfire evacuation planning results in plain "
    "Australian English. Reply with 2-3 sentences of prose only, no preamble, "
    "no lists, no reasoning steps. Never invent a number: use only figures "
    "given to you. Never guess anyone's gender. Never say anything about how a "
    "fire will behave, spread, or when it will arrive."
)


class NvidiaExplanationClient:
    """Ask a hosted model to explain figures it is given."""

    def __init__(
        self,
        *,
        api_key: str | None,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise RuntimeError("AI_API_KEY is required when APP_DATA_MODE=live.")
        self._api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx.Client(
            timeout=timeout_seconds, follow_redirects=True
        )

    def explain(self, result: RendezvousResult) -> str:
        try:
            response = self.http_client.post(
                NVIDIA_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": _user_prompt(result)},
                    ],
                    "chat_template_kwargs": {"thinking": False},
                    "temperature": 0.2,
                    "max_tokens": 300,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalDataUnavailable(
                "The explanation service is temporarily unavailable."
            ) from exc

        text = _content(body)
        if not text:
            raise ExternalDataUnavailable("The explanation service returned nothing.")
        return text


def _content(body: dict[str, Any]) -> str:
    try:
        return (body["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ExternalDataUnavailable(
            "The explanation response could not be read."
        ) from exc


def _minutes(seconds: int) -> int:
    """Round as the browser does, so prose and screen agree."""
    return round(seconds / 60)


def _user_prompt(result: RendezvousResult) -> str:
    lines = [
        "Rendezvous simulation results. Everyone drives to the same evacuation "
        "destination from where they usually are during the day. The household is "
        "together once the last person arrives.",
        "",
    ]
    for eta in result.member_etas:
        lines.append(
            f"- {eta.display_name or 'A member'}, from {eta.origin_kind}, "
            f"arrives in {_minutes(eta.travel_seconds)} minutes"
        )
    if result.everyone_together_seconds is not None:
        lines.append(
            f"- Household together after "
            f"{_minutes(result.everyone_together_seconds)} minutes"
        )
    if result.warnings:
        lines.append("")
        lines.append("Known issues already identified:")
        lines.extend(f"- {warning}" for warning in result.warnings)
    lines.append("")
    lines.append("Name the single biggest weakness and suggest one practical fix.")
    return "\n".join(lines)
