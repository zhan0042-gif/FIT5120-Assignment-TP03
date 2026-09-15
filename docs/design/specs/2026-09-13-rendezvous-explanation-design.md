# Rendezvous Explanation — Design

**Status:** approved design, not yet implemented
**Branch:** `feature/rendezvous-explanation`, stacked on `experiment/rendezvous-simulation`
**Date:** 2026-09-13

## Problem

The rendezvous simulation produces correct facts that do not add up to an
insight. A real result from the working build:

```
⚠️ Lan cannot drive any transport in your plan.
⚠️ Bo cannot travel independently. Assign an adult to collect them.
⚠️ Bo cannot drive any transport in your plan.
⚠️ Lan takes the longest at 55 minutes. The others wait about 20 minutes.
```

Four true statements that know nothing about each other. The actual weakness —
*Lan is both the furthest away and unable to drive, so the plan never explains
how Lan gets there at all* — lives at the intersection of two rules, and no
`if` statement will find it.

## What this adds

One button. The user asks for an explanation of the result they are already
looking at, and gets two to three sentences naming the most serious weakness and
suggesting one fix.

**The model interprets; it never calculates.** Every figure the user sees comes
from the routing provider. This is not a style preference: a fabricated travel
time in an evacuation tool is the most dangerous failure this product has.

## Scope decisions

| Decision | Chosen | Rejected |
|---|---|---|
| Provider | NVIDIA `nemotron-3-super-120b-a12b` | Gemini; self-hosting |
| Trigger | A separate button after the result | Automatic with every simulation |
| Where the result comes from | The browser posts back the result it is displaying | Re-running the simulation; persisting results |
| Relationship to the old AI branch | None — nothing merged, nothing copied | Merging `feature/ai-scenario-recommendations` |

**Provider.** Chosen after a five-trial head-to-head against `gemini-2.5-flash`
on the same fixture: 1248 ms median against 1608 ms, and it identified the
dependent child who cannot travel alone in 3 of 5 trials where Gemini missed that
person in all 5. Its failure modes — occasional speculation about smoke and road
closures — are the kind a keyword rule catches. Gemini's weakness was omission,
which no filter can repair.

**Trigger.** Explanation costs 1.2 s and a request against a 40-per-minute quota.
The figures are the product; the prose is an extra. A separate button also means
a provider outage costs nothing.

**Source of the result.** Results are deliberately not persisted, because they
depend on traffic at the moment of the call. Re-running the simulation to explain
it would spend a second routing call *and* risk describing different figures than
the ones on screen. Posting the displayed result back is the only option that
guarantees the prose and the numbers agree.

## Provider layer

```python
class ExplanationClient(Protocol):
    """Turn a computed simulation result into a short plain-language explanation."""

    def explain(self, result: RendezvousResult) -> str: ...
```

`providers/nvidia_explanation.py`, using `httpx` directly, matching `tomtom.py`,
`tomtom_routing.py` and `cfa.py`. No SDK is added.

Request parameters, all established by measurement rather than assumption:

```python
{
    "model": "nvidia/nemotron-3-super-120b-a12b",
    "chat_template_kwargs": {"thinking": False},
    "temperature": 0.2,
    "max_tokens": 300,
}
```

`chat_template_kwargs` is load-bearing. Without it the model emits 200+ words of
internal deliberation into `content` and hits the token ceiling before answering.
With it, median latency is 1248 ms.

Timeout is 8 seconds — far above the measured 1.2 s, low enough that a hung
provider does not hold the page. Any failure raises `ExternalDataUnavailable`;
the client never returns empty text.

`MockExplanationClient` returns a fixed sentence so tests and
`APP_DATA_MODE=mock` stay keyless and offline, matching `MockRoutingClient`.

Configured through `AI_API_KEY`, already present in `.env.example`.

## Validation

`services/explanation.py` requests the text, then runs four gates in order. **Any
gate failing discards the whole passage.** Nothing is edited, nothing is retried.

| Gate | Rejects | Evidence |
|---|---|---|
| Numbers | Any number in the prose absent from the result it describes | The hard boundary; 0/5 violations observed but the cost of one is severe |
| Speculation | `fire`, `smoke`, `flame`, `ember`, `spread`, `burn`, `road closure` | 2 of 5 trials mentioned smoke and road closures |
| Gender | `he`, `she`, `him`, `her`, `his` | The data model records no gender; a weaker model produced "he" unprompted |
| Shape | Over 120 words, or containing list markers | Catches reasoning leaking into the answer |

The speculation gate is expected to fire. In measurement it rejected 2 of 5
responses, so roughly 40% of button presses will produce no explanation. That is
correct behaviour, not a defect: silence is better than a sentence the system has
no basis for. The figures and the deterministic warnings remain on screen either
way.

A rejected passage is logged as a validation failure with the gate that caught it,
not silently dropped, so the rejection rate is observable rather than guessed at.
The rejected text itself is never logged — it may quote the household's own
addresses and member names.

## API

```
POST /api/v1/households/{household_id}/rendezvous-explanation
body: the RendezvousResult the browser is displaying
```

```python
class RendezvousExplanation(BaseModel):
    explanation: str | None = None
    reason: str | None = None      # why there is none; diagnostic, not shown to the user
```

`reason` exists so the absence of an explanation is inspectable during
development and review. The interface never renders it — a user who asked for an
explanation and did not get one is shown nothing, not an apology.

Always `200` except an unknown household (`404`). A provider failure and a
rejected passage both return `explanation: null` with a reason — neither is an
error, and both leave the simulation intact. This matches how
`BasicScenario.disabled_reason` and the simulation's own `not_applicable` status
already work.

The endpoint holds no state. It does not read the plan, does not call the routing
provider, and stores nothing.

## Frontend

`RendezvousPanel` gains an **Explain this result** button beneath the warnings,
visible only when a `ready` result is displayed.

- While waiting: the button shows a loading label; figures stay visible.
- On success: the passage appears below, clearly labelled as generated text and
  visually distinct from the measured figures.
- On `explanation: null`: nothing appears. No error, no empty placeholder, no
  retry prompt.

The existing caveat on the scenarios page — *"Hypothetical planning exercises.
Not evacuation advice — for that, follow the CFA."* — covers this too.

## Testing

**Provider**, against a stubbed HTTP client: the request carries
`chat_template_kwargs: {"thinking": false}`; a normal response parses; timeout,
HTTP error, and malformed payload each raise `ExternalDataUnavailable`.

**Gates**, one passing and one failing case each: a number not in the result; the
word "smoke"; the word "he"; a 200-word passage; a bulleted list.

**Service**: a clean passage survives; each gate failure yields `explanation:
None` with a reason; a provider failure yields `explanation: None`.

**API**: success, rejected passage, provider down, unknown household.

**Frontend**: the button appears only for `ready`; `explanation: null` renders
nothing and breaks nothing.

## Out of scope

- Caching explanations. With a manual button and a 40-per-minute quota there is
  nothing to save yet.
- Explaining `not_applicable` or `unavailable` results — those already carry a
  plain-language reason.
- Any AI involvement in computing figures, ranking scenarios, or assessing fire
  behaviour.
- Replacing the deterministic warnings. They remain the source of truth; the
  passage sits alongside them.

## Dependency

This branch is stacked on `experiment/rendezvous-simulation` (PR #42), which
introduces `RendezvousResult`. It cannot be based on `main` until that merges.
