# Rendezvous Explanation Implementation Plan

**Goal:** Add a button that asks a hosted language model to explain a rendezvous simulation result in two or three sentences, and discards anything the model says that cannot be trusted.

**Architecture:** A new `ExplanationClient` provider boundary wraps NVIDIA's hosted API with plain `httpx`. `ExplanationService` requests a passage and runs it through four validation gates; any gate failing discards the whole passage. A stateless endpoint receives the result the browser is already displaying, so the prose can never describe different figures than the screen. Nothing is persisted.

**Tech Stack:** FastAPI · Pydantic v2 · httpx · pytest · Vue 3 + Pinia · Node built-in test runner

**Spec:** `docs/design/specs/2026-09-13-rendezvous-explanation-design.md`

## Global Constraints

- Branch: `feature/rendezvous-explanation`, stacked on `experiment/rendezvous-simulation`. Do not rebase onto `main` until PR #42 merges.
- **The model never calculates.** Every figure shown to a user comes from the routing provider.
- Model id is exactly `nvidia/nemotron-3-super-120b-a12b`.
- The request MUST send `"chat_template_kwargs": {"thinking": false}`. Without it the model emits 200+ words of internal deliberation into `content` and truncates before answering.
- Request timeout is 8.0 seconds. Measured median latency is 1248 ms.
- Any provider failure raises `ExternalDataUnavailable`. The client never returns empty text.
- A rejected passage is never logged — it may quote household addresses and member names. Log the gate name only.
- `reason` is diagnostic. The interface never renders it.
- No new Python dependency. Use `httpx`, as `tomtom.py`, `tomtom_routing.py` and `cfa.py` do.
- Backend tests run keyless: `APP_DATA_MODE=mock APP_REPOSITORY_MODE=memory APP_SPATIAL_MODE=mock`.
- Backend: `cd backend && python3 -m pytest`. Frontend: `cd frontend && npm test`.
- Australian English in all user-facing copy.

---

### Task 1: Explanation boundary and mock

**Files:**
- Modify: `backend/app/providers/interfaces.py`
- Modify: `backend/app/providers/mock.py`
- Test: `backend/tests/test_mock_explanation_client.py`

**Interfaces:**
- Consumes: `RendezvousResult` from `app.schemas.rendezvous`
- Produces: `ExplanationClient` protocol with `explain(result: RendezvousResult) -> str`; `MockExplanationClient`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_mock_explanation_client.py`:

```python
from datetime import datetime, timezone

from app.providers.mock import MockExplanationClient
from app.schemas.rendezvous import MemberEta, RendezvousResult


def _result() -> RendezvousResult:
    return RendezvousResult(
        status="ready",
        destination_name="Grandma's house",
        member_etas=[
            MemberEta(
                member_id="m1",
                display_name="Minh",
                origin_kind="home",
                travel_seconds=1620,
                distance_meters=21000,
                waiting_seconds=1680,
            )
        ],
        everyone_together_seconds=3300,
        slowest_member_id="m1",
        warnings=[],
        simulated_at=datetime.now(timezone.utc),
    )


def test_returns_prose_without_calling_anything() -> None:
    text = MockExplanationClient().explain(_result())

    assert isinstance(text, str)
    assert text.strip()


def test_output_passes_the_projects_own_rules() -> None:
    text = MockExplanationClient().explain(_result())

    assert len(text.split()) <= 120
    assert "\n-" not in text
    for banned in ("fire", "smoke", " he ", " she "):
        assert banned not in f" {text.lower()} "
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_mock_explanation_client.py -v`
Expected: FAIL — `ImportError: cannot import name 'MockExplanationClient'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/providers/interfaces.py`:

```python
class ExplanationClient(Protocol):
    """Turn a computed simulation result into a short plain-language explanation.

    The implementation never calculates: it receives figures that are already
    correct and writes prose about them.
    """

    def explain(self, result: "RendezvousResult") -> str: ...
```

Add the import at the top of `interfaces.py`:

```python
from app.schemas.rendezvous import RendezvousResult
```

> If that import creates a cycle (`schemas.rendezvous` imports from `schemas.households`, which does not import providers, so it should not), keep the quoted forward reference and import under `typing.TYPE_CHECKING` instead.

Append to `backend/app/providers/mock.py`:

```python
class MockExplanationClient:
    """A fixed passage for tests and APP_DATA_MODE=mock.

    Deliberately says nothing a real model could get wrong, so a test that
    fails is a test about our code rather than about a sentence.
    """

    def explain(self, result: RendezvousResult) -> str:
        slowest = max(
            result.member_etas, key=lambda eta: eta.travel_seconds, default=None
        )
        if slowest is None:
            return "There is not enough detail in this plan to comment on."
        return (
            f"{slowest.display_name or 'One member'} takes the longest to reach "
            f"{result.destination_name}, so the household is not together until "
            "that journey finishes. Consider whether anyone could start closer."
        )
```

Add `RendezvousResult` to the imports at the top of `mock.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_mock_explanation_client.py -v`
Expected: 2 passed

- [ ] **Step 5: Confirm nothing else broke**

Run: `cd backend && APP_DATA_MODE=mock APP_REPOSITORY_MODE=memory APP_SPATIAL_MODE=mock python3 -m pytest -q`
Expected: all previously passing tests still pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/providers/interfaces.py backend/app/providers/mock.py backend/tests/test_mock_explanation_client.py
git commit -m "feat(backend): add explanation client boundary and mock"
```

---

### Task 2: NVIDIA explanation client, wired in

**Files:**
- Create: `backend/app/providers/nvidia_explanation.py`
- Modify: `backend/app/core/config.py` (`ExternalProviders`, `build_external_providers`)
- Modify: `backend/app/core/dependencies.py`
- Test: `backend/tests/test_nvidia_explanation_provider.py`

**Interfaces:**
- Consumes: `ExplanationClient`, `MockExplanationClient` from Task 1
- Produces: `NvidiaExplanationClient(api_key=..., timeout_seconds=8.0)`; `ExternalProviders.explanation`; `get_explanation_client()`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_nvidia_explanation_provider.py`:

```python
import json
from datetime import datetime, timezone

import httpx
import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.providers.nvidia_explanation import NvidiaExplanationClient
from app.schemas.rendezvous import MemberEta, RendezvousResult


def _result() -> RendezvousResult:
    return RendezvousResult(
        status="ready",
        destination_name="Grandma's house",
        member_etas=[
            MemberEta(
                member_id="m1", display_name="Minh", origin_kind="home",
                travel_seconds=1620, distance_meters=21000, waiting_seconds=1680,
            ),
            MemberEta(
                member_id="m2", display_name="Lan", origin_kind="work",
                travel_seconds=3300, distance_meters=65000, waiting_seconds=0,
            ),
        ],
        everyone_together_seconds=3300,
        slowest_member_id="m2",
        warnings=["Lan cannot drive any transport in your plan."],
        simulated_at=datetime.now(timezone.utc),
    )


def _reply(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _client(handler) -> NvidiaExplanationClient:
    return NvidiaExplanationClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_requires_an_api_key() -> None:
    with pytest.raises(RuntimeError, match="AI_API_KEY"):
        NvidiaExplanationClient(api_key=None)


def test_disables_model_reasoning_in_the_request() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=_reply("Some prose."))

    _client(handler).explain(_result())

    assert seen["body"]["chat_template_kwargs"] == {"thinking": False}
    assert seen["body"]["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert seen["auth"] == "Bearer test-key"


def test_prompt_carries_the_figures_and_the_warnings() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_reply("Some prose."))

    _client(handler).explain(_result())

    prompt = " ".join(m["content"] for m in seen["body"]["messages"])
    assert "Minh" in prompt and "Lan" in prompt
    assert "27" in prompt and "55" in prompt
    assert "cannot drive" in prompt


def test_returns_the_models_text_stripped() -> None:
    text = _client(
        lambda request: httpx.Response(200, json=_reply("  Prose here.  "))
    ).explain(_result())

    assert text == "Prose here."


def test_http_error_becomes_external_data_unavailable() -> None:
    with pytest.raises(ExternalDataUnavailable):
        _client(lambda request: httpx.Response(503, json={"e": 1})).explain(_result())


def test_timeout_becomes_external_data_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ExternalDataUnavailable):
        _client(handler).explain(_result())


def test_empty_content_becomes_external_data_unavailable() -> None:
    with pytest.raises(ExternalDataUnavailable):
        _client(lambda request: httpx.Response(200, json=_reply("   "))).explain(_result())


def test_malformed_payload_becomes_external_data_unavailable() -> None:
    with pytest.raises(ExternalDataUnavailable):
        _client(lambda request: httpx.Response(200, json={"nope": 1})).explain(_result())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_nvidia_explanation_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.providers.nvidia_explanation'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/providers/nvidia_explanation.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_nvidia_explanation_provider.py -v`
Expected: 8 passed

- [ ] **Step 5: Wire it into the runtime**

In `backend/app/core/config.py`, add to `ExternalProviders`:

```python
    explanation: ExplanationClient
```

In `build_external_providers`, add `explanation=MockExplanationClient()` to the mock branch and to the live branch:

```python
            explanation=NvidiaExplanationClient(api_key=os.getenv("AI_API_KEY")),
```

Import `ExplanationClient` from `app.providers.interfaces`, `MockExplanationClient` from `app.providers.mock`, and `NvidiaExplanationClient` from `app.providers.nvidia_explanation`.

In `backend/app/core/dependencies.py`:

```python
def get_explanation_client() -> ExplanationClient:
    return _external_providers.explanation
```

Import `ExplanationClient` from `app.providers.interfaces`.

- [ ] **Step 6: Verify both modes import**

Run:
```bash
cd backend && APP_DATA_MODE=mock APP_REPOSITORY_MODE=memory APP_SPATIAL_MODE=mock \
  python3 -c "from app.core.dependencies import get_explanation_client; print(type(get_explanation_client()).__name__)"
```
Expected: `MockExplanationClient`

Run:
```bash
cd backend && TOMTOM_API_KEY=x AI_API_KEY=y APP_DATA_MODE=live \
  python3 -c "from app.core.config import build_external_providers as b; print(type(b().explanation).__name__)"
```
Expected: `NvidiaExplanationClient`

Run: `cd backend && APP_DATA_MODE=mock APP_REPOSITORY_MODE=memory APP_SPATIAL_MODE=mock python3 -m pytest -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/providers/nvidia_explanation.py backend/app/core/config.py backend/app/core/dependencies.py backend/tests/test_nvidia_explanation_provider.py
git commit -m "feat(backend): add the NVIDIA explanation provider"
```

---

### Task 3: The four validation gates

**Files:**
- Create: `backend/app/services/explanation_gates.py`
- Test: `backend/tests/test_explanation_gates.py`

**Interfaces:**
- Consumes: `RendezvousResult`, `MemberEta`
- Produces: `allowed_numbers(result) -> set[str]`; `rejection_reason(text, result) -> str | None` returning the name of the first gate that rejects, or `None` when the passage is acceptable

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_explanation_gates.py`:

```python
from datetime import datetime, timezone

from app.schemas.rendezvous import MemberEta, RendezvousResult
from app.services.explanation_gates import allowed_numbers, rejection_reason


def _result() -> RendezvousResult:
    return RendezvousResult(
        status="ready",
        destination_name="Grandma's house",
        member_etas=[
            MemberEta(
                member_id="m1", display_name="Minh", origin_kind="home",
                travel_seconds=1620, distance_meters=21000, waiting_seconds=1680,
            ),
            MemberEta(
                member_id="m2", display_name="Lan", origin_kind="work",
                travel_seconds=3300, distance_meters=65000, waiting_seconds=0,
            ),
        ],
        everyone_together_seconds=3300,
        slowest_member_id="m2",
        warnings=[],
        simulated_at=datetime.now(timezone.utc),
    )


def test_allowed_numbers_cover_every_figure_a_reader_can_see() -> None:
    allowed = allowed_numbers(_result())

    assert "27" in allowed      # Minh's 1620 seconds
    assert "55" in allowed      # Lan's 3300 seconds, and the household total
    assert "28" in allowed      # Minh's 1680 seconds of waiting
    assert "21" in allowed      # Minh's 21000 metres
    assert "65" in allowed      # Lan's 65000 metres
    assert "2" in allowed       # the number of members
    assert "99" not in allowed


def test_a_clean_passage_is_accepted() -> None:
    text = (
        "Lan takes 55 minutes and arrives last, so the household is not together "
        "until then. Consider arranging a lift so Lan can set off sooner."
    )

    assert rejection_reason(text, _result()) is None


def test_a_number_that_is_not_in_the_result_is_rejected() -> None:
    text = "Lan takes 72 minutes, which is the longest journey in the household."

    assert rejection_reason(text, _result()) == "invented_number"


def test_speculation_about_fire_or_smoke_is_rejected() -> None:
    text = "Lan may be delayed by smoke on the roads, which would hold everyone up."

    assert rejection_reason(text, _result()) == "speculation"


def test_the_word_fire_is_rejected() -> None:
    text = "If the fire reaches the highway, Lan will not get through at all."

    assert rejection_reason(text, _result()) == "speculation"


def test_a_gendered_pronoun_is_rejected() -> None:
    text = "Lan cannot drive, so he will need a lift from somebody else."

    assert rejection_reason(text, _result()) == "gendered"


def test_a_passage_longer_than_120_words_is_rejected() -> None:
    text = " ".join(["Lan arrives last and the household waits."] * 30)

    assert rejection_reason(text, _result()) == "shape"


def test_a_bulleted_list_is_rejected() -> None:
    text = "The problems are:\n- Lan cannot drive\n- Minh drives everyone"

    assert rejection_reason(text, _result()) == "shape"


def test_gates_run_in_order_so_the_first_failure_is_reported() -> None:
    text = "He will be delayed by smoke for 72 minutes."

    assert rejection_reason(text, _result()) == "invented_number"


def test_her_inside_another_word_is_not_treated_as_a_pronoun() -> None:
    text = "Gathering there first would shorten the wait for everyone involved."

    assert rejection_reason(text, _result()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_explanation_gates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.explanation_gates'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/explanation_gates.py`:

```python
"""Checks a generated passage must survive before a user is shown it.

Each gate rejects the whole passage. Nothing is edited and nothing is retried:
a sentence that has to be repaired before it is safe was not safe to begin with.
"""

import re

from app.schemas.rendezvous import RendezvousResult

MAX_WORDS = 120

# Measured: 2 of 5 sampled responses speculated about smoke and road closures.
# The model has no basis for any of this.
SPECULATION = re.compile(
    r"\b(fire|fires|flame|flames|ember|embers|smoke|smoky|burn|burning|burnt|"
    r"spread|spreading|road closure|road closures)\b",
    re.IGNORECASE,
)

# The data model records no gender. A weaker model produced "he" unprompted.
GENDERED = re.compile(r"\b(he|she|him|her|his|hers)\b", re.IGNORECASE)

LIST_MARKER = re.compile(r"(^|\n)\s*([-*•]|\d+[.)])\s", re.MULTILINE)

NUMBER = re.compile(r"\d+")


def _minutes(seconds: int) -> int:
    return round(seconds / 60)


def allowed_numbers(result: RendezvousResult) -> set[str]:
    """Every figure a reader could legitimately see, as bare digit strings.

    Derived from the result rather than listed by hand, so a passage quoting a
    distance is accepted while one inventing a duration is not.
    """
    allowed: set[str] = {str(len(result.member_etas))}
    for eta in result.member_etas:
        allowed.add(str(_minutes(eta.travel_seconds)))
        allowed.add(str(_minutes(eta.waiting_seconds)))
        allowed.add(str(round(eta.distance_meters / 1000)))
    if result.everyone_together_seconds is not None:
        allowed.add(str(_minutes(result.everyone_together_seconds)))
    return allowed


def rejection_reason(text: str, result: RendezvousResult) -> str | None:
    """Return the name of the first gate that rejects this passage, or None.

    Order matters only for reporting: an invented figure is the most serious
    fault, so it is named first when a passage breaks several rules at once.
    """
    allowed = allowed_numbers(result)
    if any(found not in allowed for found in NUMBER.findall(text)):
        return "invented_number"
    if SPECULATION.search(text):
        return "speculation"
    if GENDERED.search(text):
        return "gendered"
    if len(text.split()) > MAX_WORDS or LIST_MARKER.search(text):
        return "shape"
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_explanation_gates.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/explanation_gates.py backend/tests/test_explanation_gates.py
git commit -m "feat(backend): add validation gates for generated explanations"
```

---

### Task 4: Explanation service and schema

**Files:**
- Create: `backend/app/schemas/explanation.py`
- Create: `backend/app/services/explanation.py`
- Test: `backend/tests/test_explanation_service.py`

**Interfaces:**
- Consumes: `ExplanationClient` (Task 1); `rejection_reason` (Task 3)
- Produces: `RendezvousExplanation(explanation, reason)`; `ExplanationService(explanation_client).explain(result) -> RendezvousExplanation`

- [ ] **Step 1: Write the schema**

Create `backend/app/schemas/explanation.py`:

```python
"""Generated-explanation API contract."""

from pydantic import BaseModel


class RendezvousExplanation(BaseModel):
    """A short passage about a simulation result, or nothing plus why.

    `reason` is diagnostic. The interface never renders it: a user who asked for
    an explanation and did not get one is shown nothing, not an apology.
    """

    explanation: str | None = None
    reason: str | None = None
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_explanation_service.py`:

```python
from datetime import datetime, timezone

from app.core.exceptions import ExternalDataUnavailable
from app.schemas.rendezvous import MemberEta, RendezvousResult
from app.services.explanation import ExplanationService

CLEAN = (
    "Lan takes 55 minutes and arrives last, so the household is not together "
    "until then. Consider arranging a lift so Lan can set off sooner."
)


def _result(status: str = "ready") -> RendezvousResult:
    return RendezvousResult(
        status=status,
        destination_name="Grandma's house",
        member_etas=[
            MemberEta(
                member_id="m1", display_name="Minh", origin_kind="home",
                travel_seconds=1620, distance_meters=21000, waiting_seconds=1680,
            ),
            MemberEta(
                member_id="m2", display_name="Lan", origin_kind="work",
                travel_seconds=3300, distance_meters=65000, waiting_seconds=0,
            ),
        ],
        everyone_together_seconds=3300,
        slowest_member_id="m2",
        warnings=[],
        simulated_at=datetime.now(timezone.utc),
    )


class FixedClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def explain(self, result: RendezvousResult) -> str:
        self.calls += 1
        return self.text


class DeadClient:
    def explain(self, result: RendezvousResult) -> str:
        raise ExternalDataUnavailable("The explanation service is unavailable.")


def test_a_clean_passage_is_returned() -> None:
    outcome = ExplanationService(FixedClient(CLEAN)).explain(_result())

    assert outcome.explanation == CLEAN
    assert outcome.reason is None


def test_an_invented_figure_discards_the_whole_passage() -> None:
    outcome = ExplanationService(
        FixedClient("Lan takes 72 minutes, longer than anyone else.")
    ).explain(_result())

    assert outcome.explanation is None
    assert outcome.reason == "invented_number"


def test_speculation_discards_the_whole_passage() -> None:
    outcome = ExplanationService(
        FixedClient("Lan may be held up by smoke along the way.")
    ).explain(_result())

    assert outcome.explanation is None
    assert outcome.reason == "speculation"


def test_a_dead_provider_yields_no_explanation_and_no_exception() -> None:
    outcome = ExplanationService(DeadClient()).explain(_result())

    assert outcome.explanation is None
    assert outcome.reason == "unavailable"


def test_a_result_that_is_not_ready_is_never_sent_to_the_model() -> None:
    client = FixedClient(CLEAN)

    outcome = ExplanationService(client).explain(_result(status="not_applicable"))

    assert outcome.explanation is None
    assert outcome.reason == "not_ready"
    assert client.calls == 0


def test_a_ready_result_with_no_members_is_never_sent_to_the_model() -> None:
    client = FixedClient(CLEAN)
    empty = _result()
    empty.member_etas = []

    outcome = ExplanationService(client).explain(empty)

    assert outcome.explanation is None
    assert outcome.reason == "not_ready"
    assert client.calls == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_explanation_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.explanation'`

- [ ] **Step 4: Write minimal implementation**

Create `backend/app/services/explanation.py`:

```python
"""Request a passage about a simulation result, and discard it unless it is safe."""

import logging

from app.core.exceptions import ExternalDataUnavailable
from app.providers.interfaces import ExplanationClient
from app.schemas.explanation import RendezvousExplanation
from app.schemas.rendezvous import RendezvousResult
from app.services.explanation_gates import rejection_reason

logger = logging.getLogger(__name__)


class ExplanationService:
    """Turn a computed result into prose, or into nothing.

    Nothing here calculates. The figures arrive already correct and the passage
    is only allowed to talk about them.
    """

    def __init__(self, explanation_client: ExplanationClient) -> None:
        self.explanation_client = explanation_client

    def explain(self, result: RendezvousResult) -> RendezvousExplanation:
        if result.status != "ready" or not result.member_etas:
            return RendezvousExplanation(reason="not_ready")

        try:
            text = self.explanation_client.explain(result)
        except ExternalDataUnavailable:
            return RendezvousExplanation(reason="unavailable")

        reason = rejection_reason(text, result)
        if reason is not None:
            # The passage itself is never logged: it may quote the household's
            # own addresses and member names.
            logger.info("explanation rejected by gate: %s", reason)
            return RendezvousExplanation(reason=reason)

        return RendezvousExplanation(explanation=text)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_explanation_service.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/explanation.py backend/app/services/explanation.py backend/tests/test_explanation_service.py
git commit -m "feat(backend): add the explanation service"
```

---

### Task 5: Explanation endpoint

**Files:**
- Modify: `backend/app/api/routes/households.py`
- Modify: `docs/iteration1-integration-contract.md`
- Test: `backend/tests/test_explanation_endpoint.py`

**Interfaces:**
- Consumes: `ExplanationService`, `RendezvousExplanation` (Task 4); `get_explanation_client` (Task 2)
- Produces: `POST /api/v1/households/{household_id}/rendezvous-explanation`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_explanation_endpoint.py`. There is no shared `client` fixture in `conftest.py`; `test_api_v1.py` defines its own at line 26 and this follows the same pattern:

```python
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_explanation_client, get_household_repository
from app.core.exceptions import ExternalDataUnavailable
from app.main import app
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.rendezvous import RendezvousResult

READY_BODY = {
    "status": "ready",
    "destination_name": "Grandma's house",
    "member_etas": [
        {
            "member_id": "m1", "display_name": "Minh", "origin_kind": "home",
            "travel_seconds": 1620, "distance_meters": 21000, "waiting_seconds": 1680,
        },
        {
            "member_id": "m2", "display_name": "Lan", "origin_kind": "work",
            "travel_seconds": 3300, "distance_meters": 65000, "waiting_seconds": 0,
        },
    ],
    "everyone_together_seconds": 3300,
    "slowest_member_id": "m2",
    "warnings": [],
    "simulated_at": datetime.now(timezone.utc).isoformat(),
}


class FixedClient:
    def __init__(self, text: str) -> None:
        self.text = text

    def explain(self, result: RendezvousResult) -> str:
        return self.text


class DeadClient:
    def explain(self, result: RendezvousResult) -> str:
        raise ExternalDataUnavailable("unavailable")


@pytest.fixture
def api():
    repository = InMemoryHouseholdRepository()
    app.dependency_overrides[get_household_repository] = lambda: repository
    with TestClient(app) as client:
        yield client, repository
    app.dependency_overrides.clear()


def _household(client: TestClient) -> str:
    return client.post("/api/v1/households").json()["household_id"]


def test_a_clean_passage_is_returned(api) -> None:
    client, _ = api
    clean = (
        "Lan takes 55 minutes and arrives last, so the household is not together "
        "until then. Consider arranging a lift so Lan can set off sooner."
    )
    app.dependency_overrides[get_explanation_client] = lambda: FixedClient(clean)
    household_id = _household(client)

    response = client.post(
        f"/api/v1/households/{household_id}/rendezvous-explanation", json=READY_BODY
    )

    assert response.status_code == 200
    assert response.json()["explanation"] == clean


def test_a_rejected_passage_returns_200_with_no_explanation(api) -> None:
    client, _ = api
    app.dependency_overrides[get_explanation_client] = lambda: FixedClient(
        "Lan may be delayed by smoke on the way."
    )
    household_id = _household(client)

    response = client.post(
        f"/api/v1/households/{household_id}/rendezvous-explanation", json=READY_BODY
    )

    assert response.status_code == 200
    assert response.json()["explanation"] is None
    assert response.json()["reason"] == "speculation"


def test_a_dead_provider_returns_200_with_no_explanation(api) -> None:
    client, _ = api
    app.dependency_overrides[get_explanation_client] = lambda: DeadClient()
    household_id = _household(client)

    response = client.post(
        f"/api/v1/households/{household_id}/rendezvous-explanation", json=READY_BODY
    )

    assert response.status_code == 200
    assert response.json()["explanation"] is None
    assert response.json()["reason"] == "unavailable"


def test_an_unknown_household_is_404(api) -> None:
    client, _ = api
    app.dependency_overrides[get_explanation_client] = lambda: FixedClient("Fine.")

    response = client.post(
        "/api/v1/households/hh_missing/rendezvous-explanation", json=READY_BODY
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_explanation_endpoint.py -v`
Expected: FAIL — the route does not exist

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/routes/households.py`, beside the existing dependency aliases:

```python
ExplanationDependency = Annotated[ExplanationClient, Depends(get_explanation_client)]
```

Add the route after `simulate_rendezvous`:

```python
@router.post(
    "/{household_id}/rendezvous-explanation", response_model=RendezvousExplanation
)
def explain_rendezvous(
    household_id: str,
    result: RendezvousResult,
    repository: RepositoryDependency,
    explanation_client: ExplanationDependency,
) -> RendezvousExplanation:
    """Explain a simulation result the browser is already displaying.

    The result arrives in the request rather than being recomputed, so the prose
    can never describe different figures than the ones on screen.
    """
    if not repository.household_exists(household_id):
        raise HouseholdNotFound(f"Household '{household_id}' was not found.")
    return ExplanationService(explanation_client).explain(result)
```

Import `ExplanationClient` from `app.providers.interfaces`, `get_explanation_client` from `app.core.dependencies`, `RendezvousExplanation` from `app.schemas.explanation`, `RendezvousResult` from `app.schemas.rendezvous`, `ExplanationService` from `app.services.explanation`, and confirm `HouseholdNotFound` is already imported in this module.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_explanation_endpoint.py -v`
Expected: 4 passed

- [ ] **Step 5: Run the whole backend suite**

Run: `cd backend && APP_DATA_MODE=mock APP_REPOSITORY_MODE=memory APP_SPATIAL_MODE=mock python3 -m pytest -q`
Expected: all pass

- [ ] **Step 6: Document the endpoint**

In `docs/iteration1-integration-contract.md`, add a row beside the rendezvous simulation row:

```markdown
| `POST /households/{household_id}/rendezvous-explanation` | Explain a rendezvous result in 2-3 sentences. Takes the result the browser is displaying. Returns `explanation: null` when the model is unavailable or the passage fails validation. |
```

And add beneath the rendezvous simulation section:

```markdown
### Rendezvous explanation

Takes a `RendezvousResult` in the request body rather than recomputing it, so
the prose always describes the figures the user is looking at. Nothing is
stored.

The generated passage is discarded entirely if it contains a number absent from
the result, mentions fire or smoke, uses a gendered pronoun, or arrives as a
list or longer than 120 words. Rejection is expected on a minority of responses
and returns `explanation: null` — the figures and the deterministic warnings are
unaffected. `reason` names the gate and is diagnostic only; it is not shown to
users.
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/routes/households.py backend/tests/test_explanation_endpoint.py docs/iteration1-integration-contract.md
git commit -m "feat(backend): expose the rendezvous explanation endpoint"
```

---

### Task 6: Explain button in the panel

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/stores/rendezvous.js`
- Modify: `frontend/src/components/scenario/RendezvousPanel.vue`
- Test: `frontend/tests/rendezvousStore.test.js`

**Interfaces:**
- Consumes: `POST /households/{id}/rendezvous-explanation` (Task 5)
- Produces: `api.explainRendezvous(householdId, result)`; store fields `explanation`, `explanationStatus`; action `requestExplanation(householdId)`

- [ ] **Step 1: Write the failing test**

Append to `frontend/tests/rendezvousStore.test.js`:

```javascript
test('a returned passage is stored', async () => {
  api.simulateRendezvous = async () => READY
  api.explainRendezvous = async () => ({ explanation: 'Lan arrives last.', reason: null })
  const store = freshStore()
  await store.runSimulation('hh_1')

  await store.requestExplanation('hh_1')

  assert.equal(store.explanationStatus, 'success')
  assert.equal(store.explanation, 'Lan arrives last.')
})

test('a rejected passage leaves no explanation and no error', async () => {
  api.simulateRendezvous = async () => READY
  api.explainRendezvous = async () => ({ explanation: null, reason: 'speculation' })
  const store = freshStore()
  await store.runSimulation('hh_1')

  await store.requestExplanation('hh_1')

  assert.equal(store.explanationStatus, 'success')
  assert.equal(store.explanation, null)
})

test('a thrown explanation request never disturbs the result', async () => {
  api.simulateRendezvous = async () => READY
  api.explainRendezvous = async () => {
    throw new Error('network down')
  }
  const store = freshStore()
  await store.runSimulation('hh_1')

  await store.requestExplanation('hh_1')

  assert.equal(store.explanationStatus, 'error')
  assert.equal(store.explanation, null)
  assert.equal(store.result.everyone_together_seconds, 2820)
})

test('running the simulation again clears the previous passage', async () => {
  api.simulateRendezvous = async () => READY
  api.explainRendezvous = async () => ({ explanation: 'Old passage.', reason: null })
  const store = freshStore()
  await store.runSimulation('hh_1')
  await store.requestExplanation('hh_1')

  await store.runSimulation('hh_1')

  assert.equal(store.explanation, null)
  assert.equal(store.explanationStatus, 'idle')
})

test('no explanation is requested without a result', async () => {
  let called = false
  api.explainRendezvous = async () => {
    called = true
    return { explanation: 'x', reason: null }
  }
  const store = freshStore()

  await store.requestExplanation('hh_1')

  assert.equal(called, false)
})
```

Add `explainRendezvous` to the `originalSimulate` save/restore block at the top of the file so the stub does not leak between tests:

```javascript
const originalExplain = api.explainRendezvous

afterEach(() => {
  api.simulateRendezvous = originalSimulate
  api.explainRendezvous = originalExplain
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — `store.requestExplanation is not a function`

- [ ] **Step 3: Add the API method**

In `frontend/src/api/client.js`, beside `simulateRendezvous`:

```javascript
  explainRendezvous: (householdId, result) =>
    request(`/households/${encodeURIComponent(householdId)}/rendezvous-explanation`, {
      method: 'POST',
      body: JSON.stringify(result),
    }),
```

- [ ] **Step 4: Extend the store**

In `frontend/src/stores/rendezvous.js`, add refs beside the existing ones:

```javascript
  const explanation = ref(null)
  const explanationStatus = ref('idle')
```

Inside `runSimulation`, clear them before the request so a passage never outlives
the figures it described:

```javascript
    explanation.value = null
    explanationStatus.value = 'idle'
```

Add the action:

```javascript
  async function requestExplanation(householdId) {
    // The result goes up with the request: the passage must describe the figures
    // on screen, not figures fetched again a moment later.
    if (!householdId || !result.value || result.value.status !== 'ready') return
    explanationStatus.value = 'loading'
    try {
      const body = await api.explainRendezvous(householdId, result.value)
      // A null explanation is an answer, not a failure: the passage was
      // rejected or the model was unavailable, and the panel shows nothing.
      explanation.value = body.explanation ?? null
      explanationStatus.value = 'success'
    } catch {
      explanation.value = null
      explanationStatus.value = 'error'
    }
  }
```

Return `explanation`, `explanationStatus` and `requestExplanation` from the store.

- [ ] **Step 5: Run tests**

Run: `cd frontend && npm test`
Expected: all pass, including the existing tests

- [ ] **Step 6: Add the button to the panel**

In `frontend/src/components/scenario/RendezvousPanel.vue`, add to the script:

```javascript
function explain() {
  rendezvousStore.requestExplanation(householdStore.householdId)
}
```

In the template, inside the `isReady` block, after the warnings list and before
the caveat:

```vue
      <p v-if="rendezvousStore.explanation" class="explanation">
        <span class="explanation-label">Generated summary</span>
        {{ rendezvousStore.explanation }}
      </p>

      <button
        v-else
        class="btn btn-ghost btn-sm"
        type="button"
        :disabled="rendezvousStore.explanationStatus === 'loading'"
        @click="explain"
      >
        {{ rendezvousStore.explanationStatus === 'loading' ? 'Thinking…' : 'Explain this result' }}
      </button>
```

Add to the scoped styles:

```css
.explanation {
  background: var(--color-bg-card-muted);
  border-radius: var(--radius);
  padding: 0.75rem 0.9rem;
  margin: 0 0 1rem;
}
.explanation-label {
  color: var(--color-text-muted);
  display: block;
  font-size: 0.75rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
```

- [ ] **Step 7: Verify in the browser**

Start the backend in live mode with the real key and the frontend dev server, then:

1. Complete a plan and run the simulation. An **Explain this result** button sits under the warnings.
2. Click it. Within a few seconds either a passage appears under a "Generated summary" label, or nothing appears and the button returns to its resting state.
3. Click **Run again**. Any previous passage disappears with the old figures.
4. Confirm every number in the passage matches a number in the rows above it.

Roughly two in five clicks are expected to produce no passage, because the
speculation gate rejects it. That is the designed behaviour.

- [ ] **Step 8: Confirm build and tests**

Run: `cd frontend && npm run build && npm test`
Expected: builds and all tests pass

Run: `cd backend && APP_DATA_MODE=mock APP_REPOSITORY_MODE=memory APP_SPATIAL_MODE=mock python3 -m pytest -q`
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add frontend/src/api/client.js frontend/src/stores/rendezvous.js frontend/src/components/scenario/RendezvousPanel.vue frontend/tests/rendezvousStore.test.js
git commit -m "feat(frontend): add an explain button to the rendezvous panel"
```

---

## Before opening a pull request

1. This branch is stacked on `experiment/rendezvous-simulation`. Open the PR against that branch, or wait for PR #42 to merge and rebase onto `main`.
2. Live mode now requires `AI_API_KEY` as well as `TOMTOM_API_KEY`. Both are already named in `.env.example`.
3. State the rejection rate in the PR description. It is a designed behaviour that looks like a bug to anyone clicking the button twice and seeing nothing.
