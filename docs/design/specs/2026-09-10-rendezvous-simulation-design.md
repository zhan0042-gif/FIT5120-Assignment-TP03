# Rendezvous Simulation — Design

**Status:** approved design, not yet implemented
**Branch:** `experiment/rendezvous-simulation`
**Date:** 2026-09-10

## Problem

The plan knows *where the home is* but not *where the people are*. A household
whose members are scattered across the day — a parent at work, a child at
school — has no way to ask the one question that decides whether their plan is
survivable: **how long until everyone is together?**

The three existing scenarios answer "do you have a backup?" with pass/fail.
None of them produce a number, and none of them touch a map.

## What this feature does

From a completed plan, estimate how long it takes every household member to
reach the primary evacuation destination from where they usually are during the
day, and report the slowest member as the time the household is finally
together.

## Scope decisions

These were settled during brainstorming. Each one narrows the build
deliberately; the rejected alternative is recorded so a later iteration does not
have to re-derive it.

| Decision | Chosen | Rejected alternative |
|---|---|---|
| Origin of member locations | Declared once in the plan (Step 1 — People) | Chosen per run on the scenarios page; real device GPS |
| Pickup legs | Not modelled — every member travels directly | Assign adults to collect dependants (routing chain + assignment problem) |
| Rendezvous target | `arrangements.primary_destination` (already has verified coordinates) | Upgrade `meeting_point` from free text to a coordinate-bearing place |
| AI explanation | Out of scope for v1 | Ship AI commentary in the first version |
| Preconditions | Plan must be 100% complete | Run partially and list who was skipped |

**Why real GPS was rejected.** `docs/security/privacy-requirements.md` mandates
collect-the-minimum and already classes home address as High sensitivity.
Tracking each member's live position is a step-change in sensitivity, and the
household model is one-browser-per-household with no multi-user mechanism. A
user-declared *usual* location is a hypothetical, not a tracked position, and
answers the same question.

**Why pickup legs were rejected for v1.** Modelling them requires deciding who
collects whom — an assignment problem — plus multi-leg routing, vehicle
capacity, and ordering when two dependants are in different places. The
warning rules below surface the same gap in words, and v2 can compute it.

**Why the primary destination, not the meeting point.** `meeting_point` is a
free-text field (`str | None`) labelled *"Meeting point if separated"* with the
placeholder *"e.g. Front gate"*. It has no coordinates, so nothing can be
routed to it. `primary_destination` already carries verified latitude and
longitude. Beyond cost, converging on a gate beside a threatened house
contradicts the act of evacuating.

## Data model

### `MemberUsualLocation` (new)

```python
class MemberUsualLocation(BaseModel):
    kind: Literal["home", "work", "school", "other"]
    address: str = ""                        # empty when kind == "home"
    latitude: float | None = None
    longitude: float | None = None
    verification_status: Literal["verified", "unverified"] = "unverified"
```

`HouseholdMember` gains `usual_location: MemberUsualLocation | None = None`.

Optional, so existing plans keep saving unchanged.

`kind="home"` carries no address; the simulation substitutes the household's
own verified coordinates. Most members of a typical household are at home, so
most rows require one dropdown and no typing.

**Why not reuse `Destination`.** It carries sixteen fields (canonical address,
unit number, street name, postcode, country, …). Routing needs coordinates.
Copying the shape would create a model whose fields are mostly unread. If a
richer shared place type is ever needed, extracting it is a change to code the
whole team depends on — not something to do from an experiment branch.

### Migration

```sql
-- database/migrations/008_member_usual_location.sql
ALTER TABLE household_member
    ADD COLUMN usual_location_kind        VARCHAR(20)   NULL,
    ADD COLUMN usual_location_address     VARCHAR(255)  NULL,
    ADD COLUMN usual_latitude             DECIMAL(9,6)  NULL,
    ADD COLUMN usual_longitude            DECIMAL(9,6)  NULL,
    ADD COLUMN usual_verification_status  VARCHAR(20)   NULL;
```

Numbered `008`, not `007`: `feature/ai-scenario-recommendations` already holds
`007_ai_scenario_recommendations.sql`, and two branches claiming one number
collide at merge.

## Routing provider

### Boundary

```python
class RouteLeg(BaseModel):
    origin_index: int
    travel_seconds: int
    distance_meters: int
    traffic_delay_seconds: int

class RoutingClient(Protocol):
    def travel_times(
        self,
        origins: list[tuple[float, float]],
        destination: tuple[float, float],
    ) -> list[RouteLeg]: ...
```

Follows the existing provider pattern in `providers/interfaces.py`
(`AddressClient`, `SpatialProvider`, `FireDangerClient`, `WeatherClient`).

### `TomTomRoutingClient` — its own module

Verified live against the project's API key on 2026-09-10:

| Probe | Result |
|---|---|
| Orbis `calculateRoute`, header auth, apiVersion 2 | `200` — 615 s, 2364 m, 0 s traffic delay |
| Legacy Matrix Routing v2, query-param key | `200` — 3 origins → 1 destination in one request: 389 s / 727 s / 536 s |
| Orbis `routing/matrix` (two path spellings) | `404` — Orbis exposes no matrix endpoint |
| Orbis `routeType=fastest` / `eco` | `400` — Orbis accepts `fast` and `short`; legacy accepts `fastest` |

The existing key needs no upgrade.

The two API families authenticate differently: Orbis Places uses the
`TomTom-Api-Key` header plus `TomTom-Api-Version` and `Attributes`; Matrix
Routing uses `?key=`. `TomTomAddressClient._request_json` hard-codes the header
form and serves four endpoints well. Routing therefore lives in
`providers/tomtom_routing.py` rather than adding a branch inside it.

### Failure behaviour

- **Timeout 8 s.** The user is watching the screen; a hung request reads as a
  broken page. The address client's own 10 s ceiling is what made a plan save
  take 20 s in production.
- **Never fabricate.** On error or timeout, raise `ExternalDataUnavailable`; the
  service reports "unavailable", never a straight-line estimate. A wrong number
  in an evacuation tool is worse than no number.
- **One request per household**, not one per member — cheaper, faster, and
  atomic: either everyone has a figure or nobody does.

`MockRoutingClient` returns straight-line estimates for tests and
`APP_DATA_MODE=mock`, keeping local development and CI keyless.

Both are wired through `build_external_providers()` in `core/config.py` using
the existing `TOMTOM_API_KEY`.

## Service

`services/rendezvous.py` — `RendezvousSimulationService(repository, routing_client)`.

Reads the saved plan, mutates nothing, mirroring `BasicScenarioService`.

### Sequence

1. Load plan and saved household location.
2. Target = `arrangements.primary_destination`; require coordinates.
3. Collect origins: `kind="home"` resolves to the household's coordinates;
   otherwise the member's own verified coordinates.
4. One `routing_client.travel_times()` call.
5. `everyone_together_seconds = max(travel_seconds)`; each member's
   `waiting_seconds` is that total minus their own.

### Preconditions

The simulation runs only when `PlanCompletionService.evaluate(plan)` returns
`overall_status == "complete"`. When it does not, the missing sections are read
straight off `completion.sections` rather than re-implementing the checks.

### Completion gains a seventh section

`PlanCompletionService` predates `usual_location`, so a plan could read 100%
complete while no member has a location and the simulation still cannot run.
`member_locations` is therefore added to `CompletionSectionName` and to
`SECTION_ORDER`: complete when every member has a `usual_location`.

Consequences, which the team must be told before this merges to `main`:

- `GET /completion` returns seven sections instead of six.
- Every existing plan drops from 100% to 86% on deploy. No data is lost and
  nothing breaks, but it is user-visible.
- `docs/iteration1-integration-contract.md` must be updated.
- `CompletionOverview.vue` counts `sections.length` and falls back to the raw
  key for unknown names, so the UI absorbs the change; it needs only a label.

### Warning rules

Deterministic, no AI, each derived from data the plan already holds:

1. **Cannot travel independently** — `is_dependant or mobility_support_required`
   → name the member and prompt for an adult to collect them.
2. **Cannot drive** — member absent from every `transport.driver_member_ids`
   → note that the figures assume car travel.
3. **Bottleneck** — the slowest member, and how long the others wait.

Rules 1 and 2 are where the feature earns its place: they expose gaps in the
plan that a bare number does not, using fields already collected.

### Result is not persisted

Figures depend on traffic at the moment of the call (TomTom returns
`trafficDelayInSeconds`). A stored result presented later as current would be
worse than none. This differs from `ScenarioTestResult`, which evaluates plan
structure and only changes when the plan does.

No result table, no migration beyond `008`.

```python
class MemberEta(BaseModel):
    member_id: str
    display_name: str
    origin_kind: Literal["home", "work", "school", "other"]
    travel_seconds: int
    distance_meters: int
    waiting_seconds: int

class RendezvousResult(BaseModel):
    status: Literal["ready", "unavailable", "not_applicable"]
    unavailable_reason: str | None = None
    missing_sections: list[CompletionSectionName] = []   # set when not_applicable
    destination_name: str = ""
    member_etas: list[MemberEta] = []
    everyone_together_seconds: int | None = None
    slowest_member_id: str | None = None
    warnings: list[str] = []
    simulated_at: datetime
```

## API

```
POST /api/v1/households/{household_id}/rendezvous-simulation → 200 RendezvousResult
```

POST rather than GET: it matches the existing `POST /tests`, the result depends
on traffic at call time and must not be cached by browsers or proxies, and each
call consumes TomTom quota — a refresh should not silently re-run it.

| Case | Status | Body |
|---|---|---|
| Computed | `200` | `status: "ready"` with figures |
| Plan below 100% | `200` | `status: "not_applicable"` + missing sections |
| TomTom failed or timed out | `200` | `status: "unavailable"` + reason |
| Unknown household | `404` | existing error envelope |

The two middle cases are answers, not errors — the same reasoning behind
`BasicScenario.enabled` / `disabled_reason`.

The route resolves dependencies, calls the service, returns the result, and
holds no logic, matching every existing route.

Frontend gains `api.simulateRendezvous(householdId)` in `api/client.js`.

## Frontend

### Step 1 — People

Each member card gains a "Where are they during the day?" row beneath
Relationship: a four-option dropdown (Home · Work · School · Other) and, unless
Home is chosen, an address field.

Choosing Home hides the address field and shows "Uses your home address."

The address field reuses `AddressAutocompleteInput` unchanged — suggestions,
TomTom verification, and the verified indicator already work there.

### Scenarios page

A new `RendezvousPanel.vue` below the existing two-column grid, on the same
route.

- **Plan incomplete:** the panel explains what is missing, rendering
  `missing_sections` from the simulation response, with a link to the plan.
  The names come from `PlanCompletionService`, so they cannot drift from the
  progress bar on Overview.
- **Ready:** names the destination and offers "Run simulation".
- **Result:** a horizontal bar per member scaled to travel time, the household
  total, waiting times, the warnings, and the timestamp.

The bars make the bottleneck visible without reading the numbers.

`ScenarioList` and `TestResultPanel` are not reused: both are shaped around
`ScenarioCheck` pass/fail and bending them is the same mistake as bending
`ScenarioTestResult`.

The existing caveat on `ScenarioTesterView` — *"Hypothetical planning
exercises. Not evacuation advice — for that, follow the CFA."* — covers this
panel and matters more here, because "47 minutes" reads as a promise in a way
that "pass" does not. The result restates that it is an estimate against
current traffic.

## Testing

The repository has pytest for the backend and, since the TomTom migration, a
frontend test runner (`frontend/tests/`).

- **Provider:** request shape, response parsing, timeout and error paths mapped
  to `ExternalDataUnavailable`, against a stubbed HTTP client — no live calls.
- **Service:** each precondition; `home` coordinate substitution; the max and
  waiting arithmetic; each warning rule; the routing failure path. Uses
  `MockRoutingClient`.
- **Completion:** `member_locations` complete and incomplete; the other six
  sections unaffected.
- **API:** all four response cases.
- **Frontend:** the store's status transitions across ready / not_applicable /
  unavailable.

## Privacy

`docs/security/privacy-requirements.md` must gain an entry for member usual
locations before this ships:

- User-declared *hypothetical* locations, not tracked positions; no device
  geolocation is involved.
- Optional; the rest of the plan works without them.
- Same handling as home address: server-side only, never logged, never
  committed as sample data.

The document explicitly forbids adding fields without a feature requirement,
and its checklist includes "Frontend collects no fields outside the contract."

## Out of scope

- AI commentary on results — deferred until the AI infrastructure merges.
- Pickup legs and adult-to-dependant assignment.
- Walking, cycling, or public transport modes.
- Routing to backup destinations.
- Storing or comparing past runs.
- Upgrading `meeting_point` to a coordinate-bearing place.
