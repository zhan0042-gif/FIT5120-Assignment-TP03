# Rendezvous Simulation Implementation Plan

**Goal:** From a fully completed plan, estimate how long each household member takes to reach the primary evacuation destination from where they usually are during the day, and report the slowest as the moment the household is together.

**Architecture:** A new `RoutingClient` provider boundary wraps TomTom Matrix Routing in its own module (Places and Routing authenticate differently). `RendezvousSimulationService` reads the saved plan, refuses unless `PlanCompletionService` reports 100%, makes one routing call for the whole household, and returns per-member ETAs plus deterministic warnings. Results are not persisted — they depend on traffic at call time.

**Tech Stack:** FastAPI · Pydantic v2 · SQLAlchemy Core + MySQL · httpx · pytest · Vue 3 + Pinia · Node built-in test runner

**Spec:** `docs/design/specs/2026-09-10-rendezvous-simulation-design.md`

## Global Constraints

- Branch: `experiment/rendezvous-simulation`. Do not merge to `main` without raising the completion change with the team.
- Migration file is numbered `008`. `007` is taken by `feature/ai-scenario-recommendations`.
- Never fabricate a travel figure. On any routing failure the result is `status: "unavailable"` — never a straight-line estimate.
- Routing timeout is 8 seconds.
- One routing request per simulation, never one per member.
- Backend tests run keyless: `APP_DATA_MODE=mock APP_REPOSITORY_MODE=memory`.
- Backend tests: `cd backend && python3 -m pytest`. Frontend tests: `cd frontend && npm test`.
- All user-facing copy is Australian English, matching existing strings.
- The service reads the plan and never mutates it, matching `BasicScenarioService`.

---

### Task 1: Member usual location schema

**Files:**
- Modify: `backend/app/schemas/households.py:71-78`
- Modify: `docs/security/privacy-requirements.md`
- Test: `backend/tests/test_member_usual_location.py`

**Interfaces:**
- Consumes: nothing
- Produces: `MemberUsualLocation(kind, address, latitude, longitude, verification_status)`; `HouseholdMember.usual_location: MemberUsualLocation | None`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_member_usual_location.py`:

```python
from copy import deepcopy

from app.schemas.households import HouseholdPlan, MemberUsualLocation


def test_member_without_usual_location_still_validates(complete_plan_data: dict) -> None:
    plan = HouseholdPlan.model_validate(deepcopy(complete_plan_data))

    assert plan.members[0].usual_location is None


def test_home_kind_needs_no_address() -> None:
    location = MemberUsualLocation(kind="home")

    assert location.address == ""
    assert location.latitude is None
    assert location.verification_status == "unverified"


def test_verified_work_location_round_trips(complete_plan_data: dict) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {
        "kind": "work",
        "address": "200 Bourke Street, Melbourne VIC 3000",
        "latitude": -37.8125,
        "longitude": 144.9665,
        "verification_status": "verified",
    }

    plan = HouseholdPlan.model_validate(data)

    assert plan.members[0].usual_location.kind == "work"
    assert plan.members[0].usual_location.latitude == -37.8125
    assert plan.members[0].usual_location.verification_status == "verified"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_member_usual_location.py -v`
Expected: FAIL — `ImportError: cannot import name 'MemberUsualLocation'`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/schemas/households.py`, above `class HouseholdMember`:

```python
class MemberUsualLocation(BaseModel):
    """Where a member usually is during the day, declared by the user.

    This is a hypothetical starting point for simulations, not a tracked
    position. `kind="home"` carries no address; the simulation substitutes the
    household's own verified coordinates.
    """

    kind: Literal["home", "work", "school", "other"]
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    verification_status: Literal["verified", "unverified"] = "unverified"
```

Add the field to `HouseholdMember`:

```python
    usual_location: MemberUsualLocation | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_member_usual_location.py -v`
Expected: 3 passed

- [ ] **Step 5: Confirm nothing else broke**

Run: `cd backend && python3 -m pytest -q`
Expected: all existing tests still pass — the field is optional.

- [ ] **Step 6: Record the new field in the privacy document**

In `docs/security/privacy-requirements.md`, add to the data inventory list (the block of `- **Field** — Source: … — **Sensitivity** — rule` lines):

```markdown
- **Member usual location (work / school / other address)** — Source: Frontend form (PUT plan) — **High** sensitivity — PII + geolocation, same handling as home address: resolved lat/lng stored server-side only, never in logs or error messages. User-declared *hypothetical* locations for simulation only; no device geolocation is collected and no position is tracked. Optional — the rest of the plan works without them.
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/households.py backend/tests/test_member_usual_location.py docs/security/privacy-requirements.md
git commit -m "feat(backend): add declared usual location to household members"
```

---

### Task 2: Persist usual location

**Files:**
- Create: `database/migrations/008_member_usual_location.sql`
- Modify: `backend/app/repositories/mysql.py` (member INSERT in `save_plan`, member SELECT in `get_plan`)
- Test: `backend/tests/test_mysql_repository.py`

**Interfaces:**
- Consumes: `MemberUsualLocation` from Task 1
- Produces: usual location survives `save_plan` → `get_plan` on the MySQL repository

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_mysql_repository.py`, following the fixtures already used in that file:

```python
def test_member_usual_location_round_trips(mysql_repository, complete_plan_data) -> None:
    household_id = mysql_repository.create_household()
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {
        "kind": "work",
        "address": "200 Bourke Street, Melbourne VIC 3000",
        "latitude": -37.8125,
        "longitude": 144.9665,
        "verification_status": "verified",
    }
    data["members"][1]["usual_location"] = {"kind": "home"}

    mysql_repository.save_plan(household_id, HouseholdPlan.model_validate(data))
    saved = mysql_repository.get_plan(household_id)

    assert saved.members[0].usual_location.kind == "work"
    assert saved.members[0].usual_location.latitude == -37.8125
    assert saved.members[0].usual_location.verification_status == "verified"
    assert saved.members[1].usual_location.kind == "home"
    assert saved.members[1].usual_location.address == ""


def test_member_without_usual_location_stays_none(mysql_repository, complete_plan_data) -> None:
    household_id = mysql_repository.create_household()

    mysql_repository.save_plan(
        household_id, HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    )

    assert mysql_repository.get_plan(household_id).members[0].usual_location is None
```

> If `test_mysql_repository.py` skips without a live MySQL, these tests skip too. Task 6 covers the same behaviour against the in-memory repository, which always runs.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_mysql_repository.py -k usual_location -v`
Expected: FAIL — the columns do not exist, or `usual_location` comes back `None`.

- [ ] **Step 3: Write the migration**

Create `database/migrations/008_member_usual_location.sql`:

```sql
-- 008_member_usual_location.sql
-- Adds the declared day-to-day location used by the rendezvous simulation.
-- All columns are nullable: existing plans are unaffected.

ALTER TABLE household_member
    ADD COLUMN usual_location_kind        VARCHAR(20)   NULL,
    ADD COLUMN usual_location_address     VARCHAR(255)  NULL,
    ADD COLUMN usual_latitude             DECIMAL(9,6)  NULL,
    ADD COLUMN usual_longitude            DECIMAL(9,6)  NULL,
    ADD COLUMN usual_verification_status  VARCHAR(20)   NULL;
```

Mirror the same five columns into the `household_member` table in `database/init/001_initial_schema.sql` so a fresh database matches a migrated one.

- [ ] **Step 4: Write the repository changes**

In `save_plan`, extend the member INSERT column list and values with the five new columns:

```python
                            usual_location_kind, usual_location_address,
                            usual_latitude, usual_longitude,
                            usual_verification_status
```

```python
                            :usual_location_kind, :usual_location_address,
                            :usual_latitude, :usual_longitude,
                            :usual_verification_status
```

and add to the parameter dict:

```python
                        "usual_location_kind": (
                            member.usual_location.kind if member.usual_location else None
                        ),
                        "usual_location_address": (
                            member.usual_location.address if member.usual_location else None
                        ),
                        "usual_latitude": (
                            member.usual_location.latitude if member.usual_location else None
                        ),
                        "usual_longitude": (
                            member.usual_location.longitude if member.usual_location else None
                        ),
                        "usual_verification_status": (
                            member.usual_location.verification_status
                            if member.usual_location
                            else None
                        ),
```

In `get_plan`, add the five columns to the member SELECT and build the nested model:

```python
            usual_location = (
                MemberUsualLocation(
                    kind=row.usual_location_kind,
                    address=row.usual_location_address or "",
                    latitude=(
                        float(row.usual_latitude) if row.usual_latitude is not None else None
                    ),
                    longitude=(
                        float(row.usual_longitude) if row.usual_longitude is not None else None
                    ),
                    verification_status=row.usual_verification_status or "unverified",
                )
                if row.usual_location_kind
                else None
            )
```

and pass `usual_location=usual_location` when constructing each `HouseholdMember`. Import `MemberUsualLocation` at the top of the module.

- [ ] **Step 5: Run tests**

Run: `cd backend && python3 -m pytest tests/test_mysql_repository.py -v`
Expected: PASS (or SKIP if no MySQL is available locally)

- [ ] **Step 6: Commit**

```bash
git add database/migrations/008_member_usual_location.sql database/init/001_initial_schema.sql backend/app/repositories/mysql.py backend/tests/test_mysql_repository.py
git commit -m "feat(database): persist member usual location"
```

---

### Task 3: Completion gains a member_locations section

**Files:**
- Modify: `backend/app/schemas/households.py:21-28` (`CompletionSectionName`)
- Modify: `backend/app/services/plans.py:160-202` (`PlanCompletionService`)
- Modify: `frontend/src/components/completion/CompletionOverview.vue:4`
- Modify: `docs/iteration1-integration-contract.md`
- Test: `backend/tests/test_member_locations_completion.py`

**Interfaces:**
- Consumes: `HouseholdMember.usual_location` from Task 1
- Produces: `"member_locations"` as a valid `CompletionSectionName`; `PlanCompletion.sections` has seven entries

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_member_locations_completion.py`:

```python
from copy import deepcopy

from app.schemas.households import HouseholdPlan
from app.services.plans import PlanCompletionService


def _section(completion, name):
    return next(item for item in completion.sections if item.section == name)


def test_member_locations_needs_information_when_absent(complete_plan_data: dict) -> None:
    plan = HouseholdPlan.model_validate(deepcopy(complete_plan_data))

    completion = PlanCompletionService().evaluate(plan)

    assert len(completion.sections) == 7
    assert _section(completion, "member_locations").status == "needs_information"
    assert completion.overall_status == "needs_information"


def test_member_locations_complete_when_every_member_has_one(complete_plan_data: dict) -> None:
    data = deepcopy(complete_plan_data)
    for member in data["members"]:
        member["usual_location"] = {"kind": "home"}

    completion = PlanCompletionService().evaluate(HouseholdPlan.model_validate(data))

    assert _section(completion, "member_locations").status == "complete"


def test_one_member_missing_a_location_blocks_the_section(complete_plan_data: dict) -> None:
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {"kind": "home"}

    completion = PlanCompletionService().evaluate(HouseholdPlan.model_validate(data))

    assert _section(completion, "member_locations").status == "needs_information"


def test_plan_with_no_members_is_not_complete_for_locations() -> None:
    completion = PlanCompletionService().evaluate(HouseholdPlan())

    assert _section(completion, "member_locations").status == "needs_information"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_member_locations_completion.py -v`
Expected: FAIL — only six sections; `StopIteration` looking for `member_locations`.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/schemas/households.py`, add to `CompletionSectionName`:

```python
    "member_locations",
```

In `backend/app/services/plans.py`, add to `PlanCompletionService.SECTION_ORDER` after `"household_profile"`:

```python
        "member_locations",
```

and add to the `statuses` dict in `evaluate`:

```python
            "member_locations": bool(plan.members)
            and all(member.usual_location is not None for member in plan.members),
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_member_locations_completion.py -v`
Expected: 4 passed

- [ ] **Step 5: Fix the existing tests this deliberately breaks**

Run: `cd backend && python3 -m pytest -q`

Tests asserting six sections or `overall_status == "complete"` on the shared fixture now fail — this is the intended contract change, not a regression. For each failure, either add `"usual_location": {"kind": "home"}` to the fixture members used by that test, or update the expected section count. Do not weaken the new rule to make old tests pass.

- [ ] **Step 6: Add the frontend label**

In `frontend/src/components/completion/CompletionOverview.vue:4`, add to the `labels` object:

```javascript
member_locations: 'Member locations',
```

The component counts `sections.length` and falls back to the raw key, so no other change is needed.

- [ ] **Step 7: Update the integration contract**

In `docs/iteration1-integration-contract.md`, find the completion section list and add `member_locations` with a note:

```markdown
- `member_locations` — complete when every household member has a declared usual location. Added 2026-09-10 for the rendezvous simulation; `GET /completion` now returns seven sections, and plans saved before this change report 86% until a location is added to each member.
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/households.py backend/app/services/plans.py backend/tests/ frontend/src/components/completion/CompletionOverview.vue docs/iteration1-integration-contract.md
git commit -m "feat(backend): add member_locations completion section"
```

---

### Task 4: Routing boundary and mock

**Files:**
- Modify: `backend/app/providers/interfaces.py`
- Modify: `backend/app/providers/mock.py`
- Test: `backend/tests/test_mock_routing_client.py`

**Interfaces:**
- Consumes: nothing
- Produces: `RouteLeg(origin_index, travel_seconds, distance_meters, traffic_delay_seconds)`; `RoutingClient` protocol with `travel_times(origins, destination) -> list[RouteLeg]`; `MockRoutingClient`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_mock_routing_client.py`:

```python
from app.providers.mock import MockRoutingClient


def test_returns_one_leg_per_origin_in_order() -> None:
    legs = MockRoutingClient().travel_times(
        origins=[(-37.8136, 144.9631), (-37.7963, 144.9524)],
        destination=(-37.8100, 144.9700),
    )

    assert [leg.origin_index for leg in legs] == [0, 1]


def test_a_further_origin_takes_longer() -> None:
    legs = MockRoutingClient().travel_times(
        origins=[(-37.8100, 144.9705), (-37.9500, 145.2000)],
        destination=(-37.8100, 144.9700),
    )

    assert legs[1].travel_seconds > legs[0].travel_seconds


def test_no_origins_returns_no_legs() -> None:
    assert MockRoutingClient().travel_times(origins=[], destination=(-37.81, 144.97)) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_mock_routing_client.py -v`
Expected: FAIL — `ImportError: cannot import name 'MockRoutingClient'`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/providers/interfaces.py`:

```python
class RouteLeg(BaseModel):
    """One origin's travel estimate to the shared destination."""

    origin_index: int
    travel_seconds: int
    distance_meters: int
    traffic_delay_seconds: int = 0


class RoutingClient(Protocol):
    """Estimate travel time from several origins to one destination."""

    def travel_times(
        self,
        origins: list[tuple[float, float]],
        destination: tuple[float, float],
    ) -> list[RouteLeg]: ...
```

In `backend/app/providers/mock.py`:

```python
class MockRoutingClient:
    """Straight-line estimates for tests and APP_DATA_MODE=mock.

    Deterministic and offline. Never used in live mode: a straight line is not
    a travel time, and the service must never present one as if it were.
    """

    AVERAGE_SPEED_METRES_PER_SECOND = 11.0  # ~40 km/h urban average

    def travel_times(
        self,
        origins: list[tuple[float, float]],
        destination: tuple[float, float],
    ) -> list[RouteLeg]:
        legs: list[RouteLeg] = []
        for index, origin in enumerate(origins):
            metres = int(_haversine_metres(origin, destination))
            legs.append(
                RouteLeg(
                    origin_index=index,
                    travel_seconds=int(metres / self.AVERAGE_SPEED_METRES_PER_SECOND),
                    distance_meters=metres,
                    traffic_delay_seconds=0,
                )
            )
        return legs


def _haversine_metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    earth_radius_metres = 6_371_000.0
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    d_lat, d_lon = lat2 - lat1, lon2 - lon1
    h = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    return 2 * earth_radius_metres * asin(sqrt(h))
```

Add `from math import asin, cos, radians, sin, sqrt` and import `RouteLeg` at the top of `mock.py`.

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_mock_routing_client.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers/interfaces.py backend/app/providers/mock.py backend/tests/test_mock_routing_client.py
git commit -m "feat(backend): add routing client boundary and mock"
```

---

### Task 5: TomTom routing client, wired in

**Files:**
- Create: `backend/app/providers/tomtom_routing.py`
- Modify: `backend/app/core/config.py:16-19` (`ExternalProviders`), `:58-70` (`build_external_providers`)
- Modify: `backend/app/core/dependencies.py`
- Test: `backend/tests/test_tomtom_routing_provider.py`

**Interfaces:**
- Consumes: `RouteLeg`, `RoutingClient` from Task 4
- Produces: `TomTomRoutingClient(api_key=..., timeout_seconds=8.0)`; `ExternalProviders.routing`; `get_routing_client()` in `dependencies.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_tomtom_routing_provider.py`:

```python
import httpx
import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.providers.tomtom_routing import TomTomRoutingClient

MATRIX_RESPONSE = {
    "data": [
        {"originIndex": 0, "destinationIndex": 0,
         "routeSummary": {"lengthInMeters": 1167, "travelTimeInSeconds": 389,
                          "trafficDelayInSeconds": 0}},
        {"originIndex": 1, "destinationIndex": 0,
         "routeSummary": {"lengthInMeters": 2977, "travelTimeInSeconds": 727,
                          "trafficDelayInSeconds": 12}},
    ]
}

ORIGINS = [(-37.8136, 144.9631), (-37.7963, 144.9524)]
DESTINATION = (-37.8100, 144.9700)


def _client(handler) -> TomTomRoutingClient:
    return TomTomRoutingClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_requires_an_api_key() -> None:
    with pytest.raises(RuntimeError, match="TOMTOM_API_KEY"):
        TomTomRoutingClient(api_key=None)


def test_sends_every_origin_and_one_destination_in_a_single_request() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=MATRIX_RESPONSE)

    _client(handler).travel_times(origins=ORIGINS, destination=DESTINATION)

    assert len(seen["body"]["origins"]) == 2
    assert len(seen["body"]["destinations"]) == 1
    assert seen["body"]["origins"][0]["point"] == {
        "latitude": -37.8136, "longitude": 144.9631
    }
    assert "key=test-key" in seen["url"]


def test_parses_legs_in_origin_order() -> None:
    legs = _client(lambda request: httpx.Response(200, json=MATRIX_RESPONSE)).travel_times(
        origins=ORIGINS, destination=DESTINATION
    )

    assert [leg.origin_index for leg in legs] == [0, 1]
    assert legs[0].travel_seconds == 389
    assert legs[1].distance_meters == 2977
    assert legs[1].traffic_delay_seconds == 12


def test_http_error_becomes_external_data_unavailable() -> None:
    client = _client(lambda request: httpx.Response(503, json={"error": "busy"}))

    with pytest.raises(ExternalDataUnavailable):
        client.travel_times(origins=ORIGINS, destination=DESTINATION)


def test_timeout_becomes_external_data_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(ExternalDataUnavailable):
        _client(handler).travel_times(origins=ORIGINS, destination=DESTINATION)


def test_malformed_payload_becomes_external_data_unavailable() -> None:
    client = _client(lambda request: httpx.Response(200, json={"data": [{"nope": 1}]}))

    with pytest.raises(ExternalDataUnavailable):
        client.travel_times(origins=ORIGINS, destination=DESTINATION)


def test_no_origins_short_circuits_without_calling_the_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call TomTom with no origins")

    assert _client(handler).travel_times(origins=[], destination=DESTINATION) == []
```

Add `import json` at the top of the test file.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_tomtom_routing_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.providers.tomtom_routing'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/providers/tomtom_routing.py`:

```python
"""TomTom Matrix Routing adapter for the rendezvous simulation.

Matrix Routing lives on the legacy v2 API and authenticates with a `key` query
parameter, unlike the Orbis Places endpoints used by TomTomAddressClient, which
authenticate by header. Orbis exposes no matrix endpoint, so this is a separate
module rather than a branch inside the address client.
"""

from typing import Any

import httpx

from app.core.exceptions import ExternalDataUnavailable
from app.providers.interfaces import RouteLeg

TOMTOM_MATRIX_URL = "https://api.tomtom.com/routing/matrix/2"


class TomTomRoutingClient:
    """Estimate travel time from several origins to one destination."""

    def __init__(
        self,
        *,
        api_key: str | None,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise RuntimeError("TOMTOM_API_KEY is required when APP_DATA_MODE=live.")
        self._api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx.Client(
            timeout=timeout_seconds, follow_redirects=True
        )

    def travel_times(
        self,
        origins: list[tuple[float, float]],
        destination: tuple[float, float],
    ) -> list[RouteLeg]:
        """Return one leg per origin, in the order the origins were given.

        The whole household travels in a single request: cheaper, faster, and
        atomic, so a partial failure cannot leave some members with figures and
        others without.
        """
        if not origins:
            return []

        payload = {
            "origins": [
                {"point": {"latitude": latitude, "longitude": longitude}}
                for latitude, longitude in origins
            ],
            "destinations": [
                {"point": {"latitude": destination[0], "longitude": destination[1]}}
            ],
        }
        try:
            response = self.http_client.post(
                TOMTOM_MATRIX_URL,
                params={
                    "key": self._api_key,
                    "routeType": "fastest",
                    "travelMode": "car",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalDataUnavailable(
                "Travel time estimates are temporarily unavailable."
            ) from exc

        return self._legs(body, expected=len(origins))

    @staticmethod
    def _legs(body: dict[str, Any], *, expected: int) -> list[RouteLeg]:
        legs: list[RouteLeg] = []
        try:
            for entry in body["data"]:
                summary = entry["routeSummary"]
                legs.append(
                    RouteLeg(
                        origin_index=int(entry["originIndex"]),
                        travel_seconds=int(summary["travelTimeInSeconds"]),
                        distance_meters=int(summary["lengthInMeters"]),
                        traffic_delay_seconds=int(
                            summary.get("trafficDelayInSeconds", 0)
                        ),
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise ExternalDataUnavailable(
                "The travel time response could not be read."
            ) from exc

        if len(legs) != expected:
            raise ExternalDataUnavailable(
                "The travel time response was incomplete."
            )
        legs.sort(key=lambda leg: leg.origin_index)
        return legs
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_tomtom_routing_provider.py -v`
Expected: 7 passed

- [ ] **Step 5: Wire it into the runtime**

In `backend/app/core/config.py`, add to `ExternalProviders`:

```python
    routing: RoutingClient
```

In `build_external_providers`, add `routing=MockRoutingClient()` to the mock branch and to the live branch:

```python
            routing=TomTomRoutingClient(api_key=os.getenv("TOMTOM_API_KEY")),
```

Import `RoutingClient`, `MockRoutingClient`, and `TomTomRoutingClient` at the top.

In `backend/app/core/dependencies.py`:

```python
def get_routing_client() -> RoutingClient:
    return _external_providers.routing
```

Import `RoutingClient` from `app.providers.interfaces`.

- [ ] **Step 6: Verify the app still imports in both modes**

Run:
```bash
cd backend && APP_DATA_MODE=mock APP_REPOSITORY_MODE=memory APP_SPATIAL_MODE=mock \
  python3 -c "from app.main import app; print('mock mode OK')"
```
Expected: `mock mode OK`

Run: `cd backend && python3 -m pytest -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/providers/tomtom_routing.py backend/app/core/config.py backend/app/core/dependencies.py backend/tests/test_tomtom_routing_provider.py
git commit -m "feat(backend): add TomTom matrix routing provider"
```

---

### Task 6: Rendezvous simulation service

**Files:**
- Create: `backend/app/schemas/rendezvous.py`
- Create: `backend/app/services/rendezvous.py`
- Test: `backend/tests/test_rendezvous_simulation.py`

**Interfaces:**
- Consumes: `RoutingClient`, `MockRoutingClient` (Task 4); `MemberUsualLocation` (Task 1); `member_locations` completion (Task 3)
- Produces: `MemberEta`, `RendezvousResult`; `RendezvousSimulationService(repository, routing_client).simulate(household_id) -> RendezvousResult`

- [ ] **Step 1: Write the schemas**

Create `backend/app/schemas/rendezvous.py`:

```python
"""Rendezvous simulation API contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.households import CompletionSectionName


class MemberEta(BaseModel):
    """One member's estimated journey to the shared destination."""

    member_id: str
    display_name: str
    origin_kind: Literal["home", "work", "school", "other"]
    travel_seconds: int
    distance_meters: int
    waiting_seconds: int


class RendezvousResult(BaseModel):
    """Estimated moment the household is together, or why it cannot be estimated.

    Not persisted: the figures depend on traffic at the time of the call.
    """

    status: Literal["ready", "unavailable", "not_applicable"]
    unavailable_reason: str | None = None
    missing_sections: list[CompletionSectionName] = []
    destination_name: str = ""
    member_etas: list[MemberEta] = []
    everyone_together_seconds: int | None = None
    slowest_member_id: str | None = None
    warnings: list[str] = []
    simulated_at: datetime
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_rendezvous_simulation.py`:

```python
from copy import deepcopy

import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.providers.interfaces import RouteLeg
from app.providers.mock import MockRoutingClient
from app.repositories.households import InMemoryHouseholdRepository
from app.schemas.households import HouseholdLocation, HouseholdPlan
from app.services.rendezvous import RendezvousSimulationService

HOME = (-37.8136, 144.9631)


class StubRoutingClient:
    """Returns fixed travel times so arithmetic and rules can be asserted exactly."""

    def __init__(self, seconds: list[int]) -> None:
        self.seconds = seconds
        self.calls = 0

    def travel_times(self, origins, destination):
        self.calls += 1
        return [
            RouteLeg(
                origin_index=index,
                travel_seconds=self.seconds[index],
                distance_meters=self.seconds[index] * 10,
                traffic_delay_seconds=0,
            )
            for index in range(len(origins))
        ]


class UnavailableRoutingClient:
    def travel_times(self, origins, destination):
        raise ExternalDataUnavailable("Travel time estimates are unavailable.")


def _ready_plan_data(complete_plan_data: dict) -> dict:
    """The shared fixture, made simulation-ready: locations and a placed destination."""
    data = deepcopy(complete_plan_data)
    data["members"][0]["usual_location"] = {"kind": "home"}
    data["members"][1]["usual_location"] = {
        "kind": "work",
        "address": "200 Bourke Street, Melbourne VIC 3000",
        "latitude": -37.8125,
        "longitude": 144.9665,
        "verification_status": "verified",
    }
    destination = data["arrangements"]["primary_destination"]
    destination["latitude"] = -37.8100
    destination["longitude"] = 144.9700
    return data


@pytest.fixture
def ready_household(complete_plan_data: dict):
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_location(
        household_id,
        HouseholdLocation(
            address="1 Home Street, Melbourne VIC 3000",
            latitude=HOME[0],
            longitude=HOME[1],
            verification_status="verified",
        ),
    )
    repository.save_plan(
        household_id, HouseholdPlan.model_validate(_ready_plan_data(complete_plan_data))
    )
    return repository, household_id


def test_slowest_member_sets_the_household_time(ready_household) -> None:
    repository, household_id = ready_household
    routing = StubRoutingClient([720, 2820])

    result = RendezvousSimulationService(repository, routing).simulate(household_id)

    assert result.status == "ready"
    assert result.everyone_together_seconds == 2820
    assert result.slowest_member_id == "m_002"
    assert routing.calls == 1


def test_waiting_time_is_the_gap_to_the_slowest(ready_household) -> None:
    repository, household_id = ready_household

    result = RendezvousSimulationService(
        repository, StubRoutingClient([720, 2820])
    ).simulate(household_id)

    etas = {eta.member_id: eta for eta in result.member_etas}
    assert etas["m_001"].waiting_seconds == 2100
    assert etas["m_002"].waiting_seconds == 0


def test_home_members_start_from_the_household_location(ready_household) -> None:
    repository, household_id = ready_household
    seen: dict = {}

    class RecordingRoutingClient(StubRoutingClient):
        def travel_times(self, origins, destination):
            seen["origins"] = origins
            seen["destination"] = destination
            return super().travel_times(origins, destination)

    RendezvousSimulationService(
        repository, RecordingRoutingClient([720, 2820])
    ).simulate(household_id)

    assert seen["origins"][0] == HOME
    assert seen["origins"][1] == (-37.8125, 144.9665)
    assert seen["destination"] == (-37.8100, 144.9700)


def test_incomplete_plan_is_not_applicable_and_names_the_gaps(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_plan(
        household_id, HouseholdPlan.model_validate(deepcopy(complete_plan_data))
    )

    result = RendezvousSimulationService(
        repository, StubRoutingClient([100])
    ).simulate(household_id)

    assert result.status == "not_applicable"
    assert "member_locations" in result.missing_sections
    assert result.member_etas == []


def test_destination_without_coordinates_is_not_applicable(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    data = _ready_plan_data(complete_plan_data)
    data["arrangements"]["primary_destination"]["latitude"] = None
    data["arrangements"]["primary_destination"]["longitude"] = None
    repository.save_plan(household_id, HouseholdPlan.model_validate(data))

    result = RendezvousSimulationService(
        repository, StubRoutingClient([100, 200])
    ).simulate(household_id)

    assert result.status == "not_applicable"
    assert "destination" in (result.unavailable_reason or "").lower()


def test_home_member_without_a_verified_household_location_is_not_applicable(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_plan(
        household_id,
        HouseholdPlan.model_validate(_ready_plan_data(complete_plan_data)),
    )

    result = RendezvousSimulationService(
        repository, StubRoutingClient([100, 200])
    ).simulate(household_id)

    assert result.status == "not_applicable"
    assert "home address" in (result.unavailable_reason or "").lower()


def test_routing_failure_is_unavailable_and_carries_no_figures(ready_household) -> None:
    repository, household_id = ready_household

    result = RendezvousSimulationService(
        repository, UnavailableRoutingClient()
    ).simulate(household_id)

    assert result.status == "unavailable"
    assert result.everyone_together_seconds is None
    assert result.member_etas == []


def test_dependant_member_raises_a_collection_warning(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_location(
        household_id,
        HouseholdLocation(
            address="1 Home Street", latitude=HOME[0], longitude=HOME[1],
            verification_status="verified",
        ),
    )
    data = _ready_plan_data(complete_plan_data)
    data["members"][1]["is_dependant"] = True
    repository.save_plan(household_id, HouseholdPlan.model_validate(data))

    result = RendezvousSimulationService(
        repository, StubRoutingClient([720, 2820])
    ).simulate(household_id)

    assert any("Alex" in warning and "collect" in warning for warning in result.warnings)


def test_member_who_drives_nothing_raises_a_car_assumption_warning(
    complete_plan_data: dict,
) -> None:
    repository = InMemoryHouseholdRepository()
    household_id = repository.create_household()
    repository.save_location(
        household_id,
        HouseholdLocation(
            address="1 Home Street", latitude=HOME[0], longitude=HOME[1],
            verification_status="verified",
        ),
    )
    data = _ready_plan_data(complete_plan_data)
    for transport in data["transports"]:
        transport["driver_member_ids"] = ["m_001"]
    repository.save_plan(household_id, HouseholdPlan.model_validate(data))

    result = RendezvousSimulationService(
        repository, StubRoutingClient([720, 2820])
    ).simulate(household_id)

    assert any("Alex" in warning and "car" in warning.lower() for warning in result.warnings)


def test_bottleneck_warning_names_the_slowest_member(ready_household) -> None:
    repository, household_id = ready_household

    result = RendezvousSimulationService(
        repository, StubRoutingClient([720, 2820])
    ).simulate(household_id)

    assert any("Alex" in warning and "47" in warning for warning in result.warnings)


def test_mock_routing_client_satisfies_the_service(ready_household) -> None:
    repository, household_id = ready_household

    result = RendezvousSimulationService(repository, MockRoutingClient()).simulate(
        household_id
    )

    assert result.status == "ready"
    assert len(result.member_etas) == 2
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_rendezvous_simulation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.rendezvous'`

- [ ] **Step 4: Write minimal implementation**

Create `backend/app/services/rendezvous.py`:

```python
"""Estimate when a scattered household is finally together."""

from datetime import datetime, timezone

from app.core.exceptions import ExternalDataUnavailable, LocationNotFound
from app.providers.interfaces import RoutingClient
from app.repositories.households import HouseholdRepository
from app.schemas.households import HouseholdMember, HouseholdPlan
from app.schemas.rendezvous import MemberEta, RendezvousResult
from app.services.plans import PlanCompletionService


class _MemberLocationUnusable(Exception):
    """A member's declared location cannot be turned into coordinates."""


class RendezvousSimulationService:
    """Estimate the moment every member reaches the primary destination.

    Reads the saved plan and mutates nothing, like BasicScenarioService. Travel
    figures come from the routing provider; this service never estimates a
    distance itself, and reports "unavailable" rather than guessing.
    """

    def __init__(
        self, repository: HouseholdRepository, routing_client: RoutingClient
    ) -> None:
        self.repository = repository
        self.routing_client = routing_client

    def simulate(self, household_id: str) -> RendezvousResult:
        plan = self.repository.get_plan(household_id)

        completion = PlanCompletionService().evaluate(plan)
        if completion.overall_status != "complete":
            return self._not_applicable(
                "Finish your plan before running this simulation.",
                missing_sections=[
                    section.section
                    for section in completion.sections
                    if section.status != "complete"
                ],
            )

        destination = plan.arrangements.primary_destination
        if (
            destination is None
            or destination.latitude is None
            or destination.longitude is None
        ):
            return self._not_applicable(
                "Add a verified primary destination before running this simulation."
            )

        try:
            origins = self._origins(household_id, plan.members)
        except LocationNotFound:
            return self._not_applicable(
                "Verify your home address before running this simulation."
            )
        except _MemberLocationUnusable as exc:
            return self._not_applicable(str(exc))

        try:
            legs = self.routing_client.travel_times(
                origins=[point for _, point in origins],
                destination=(destination.latitude, destination.longitude),
            )
        except ExternalDataUnavailable as exc:
            return RendezvousResult(
                status="unavailable",
                unavailable_reason=str(exc),
                destination_name=destination.display_name,
                simulated_at=datetime.now(timezone.utc),
            )

        slowest = max(leg.travel_seconds for leg in legs)
        etas = [
            MemberEta(
                member_id=origins[leg.origin_index][0].member_id,
                display_name=origins[leg.origin_index][0].display_name,
                origin_kind=origins[leg.origin_index][0].usual_location.kind,
                travel_seconds=leg.travel_seconds,
                distance_meters=leg.distance_meters,
                waiting_seconds=slowest - leg.travel_seconds,
            )
            for leg in legs
        ]
        slowest_eta = max(etas, key=lambda eta: eta.travel_seconds)

        return RendezvousResult(
            status="ready",
            destination_name=destination.display_name,
            member_etas=etas,
            everyone_together_seconds=slowest,
            slowest_member_id=slowest_eta.member_id,
            warnings=self._warnings(plan, etas, slowest_eta),
            simulated_at=datetime.now(timezone.utc),
        )

    def _origins(
        self, household_id: str, members: list[HouseholdMember]
    ) -> list[tuple[HouseholdMember, tuple[float, float]]]:
        """Pair each member with the coordinates they start from."""
        household_point: tuple[float, float] | None = None
        origins: list[tuple[HouseholdMember, tuple[float, float]]] = []

        for member in members:
            location = member.usual_location
            if location is None:
                raise _MemberLocationUnusable(
                    f"{member.display_name or 'A member'} has no usual location recorded."
                )
            if location.kind == "home":
                if household_point is None:
                    household_point = self._household_point(household_id)
                origins.append((member, household_point))
                continue
            if location.latitude is None or location.longitude is None:
                raise _MemberLocationUnusable(
                    f"{member.display_name or 'A member'} has an unverified usual address."
                )
            origins.append((member, (location.latitude, location.longitude)))
        return origins

    def _household_point(self, household_id: str) -> tuple[float, float]:
        location = self.repository.get_location(household_id)
        if location.latitude is None or location.longitude is None:
            raise LocationNotFound("The household location is not verified.")
        return (location.latitude, location.longitude)

    @staticmethod
    def _warnings(
        plan: HouseholdPlan, etas: list[MemberEta], slowest: MemberEta
    ) -> list[str]:
        """Deterministic rules over data the plan already holds. No AI."""
        warnings: list[str] = []
        members = {member.member_id: member for member in plan.members}
        drivers = {
            member_id
            for transport in plan.transports
            for member_id in transport.driver_member_ids
        }

        for eta in etas:
            member = members[eta.member_id]
            name = member.display_name or "A member"
            if member.is_dependant or member.mobility_support_required:
                warnings.append(
                    f"{name} cannot travel independently. Assign an adult to collect them."
                )
            if member.member_id not in drivers:
                warnings.append(
                    f"{name} cannot drive any transport in your plan. "
                    "These estimates assume car travel."
                )

        waiting = [eta.waiting_seconds for eta in etas if eta.member_id != slowest.member_id]
        if waiting:
            average_wait = sum(waiting) // len(waiting)
            warnings.append(
                f"{slowest.display_name or 'One member'} takes the longest at "
                f"{slowest.travel_seconds // 60} minutes. The others wait about "
                f"{average_wait // 60} minutes at the destination."
            )
        return warnings

    @staticmethod
    def _not_applicable(
        reason: str, missing_sections: list[str] | None = None
    ) -> RendezvousResult:
        return RendezvousResult(
            status="not_applicable",
            unavailable_reason=reason,
            missing_sections=missing_sections or [],
            simulated_at=datetime.now(timezone.utc),
        )
```

`LocationNotFound` is defined at `backend/app/core/exceptions.py:16` and is what `InMemoryHouseholdRepository.get_location` raises when no location is stored (`repositories/households.py:88-92`).

- [ ] **Step 5: Run tests**

Run: `cd backend && python3 -m pytest tests/test_rendezvous_simulation.py -v`
Expected: 12 passed

- [ ] **Step 6: Run the whole backend suite**

Run: `cd backend && python3 -m pytest -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/rendezvous.py backend/app/services/rendezvous.py backend/tests/test_rendezvous_simulation.py
git commit -m "feat(backend): add rendezvous simulation service"
```

---

### Task 7: Simulation endpoint

**Files:**
- Modify: `backend/app/api/routes/households.py`
- Modify: `docs/iteration1-integration-contract.md`
- Test: `backend/tests/test_rendezvous_endpoint.py`

**Interfaces:**
- Consumes: `RendezvousSimulationService`, `RendezvousResult` (Task 6); `get_routing_client` (Task 5)
- Produces: `POST /api/v1/households/{household_id}/rendezvous-simulation`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_rendezvous_endpoint.py`. There is no shared `client`
fixture in `conftest.py`; `test_api_v1.py` defines its own `api` fixture at
line 26, and this file follows the same pattern with the routing client
overridden as well:

```python
import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_household_repository, get_routing_client
from app.main import app
from app.providers.mock import MockRoutingClient
from app.repositories.households import InMemoryHouseholdRepository


@pytest.fixture
def api() -> tuple[TestClient, InMemoryHouseholdRepository]:
    repository = InMemoryHouseholdRepository()
    app.dependency_overrides[get_household_repository] = lambda: repository
    app.dependency_overrides[get_routing_client] = lambda: MockRoutingClient()
    with TestClient(app) as client:
        yield client, repository
    app.dependency_overrides.clear()


def test_simulation_returns_not_applicable_for_a_fresh_household(api) -> None:
    client, _ = api
    household_id = client.post("/api/v1/households").json()["household_id"]
    client.put(f"/api/v1/households/{household_id}/plan", json={})

    response = client.post(f"/api/v1/households/{household_id}/rendezvous-simulation")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_applicable"
    assert body["member_etas"] == []
    assert "member_locations" in body["missing_sections"]


def test_simulation_returns_404_for_an_unknown_household(api) -> None:
    client, _ = api

    response = client.post("/api/v1/households/hh_does_not_exist/rendezvous-simulation")

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_rendezvous_endpoint.py -v`
Expected: FAIL — 405 or 404 from a route that does not exist

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/routes/households.py`, beside the existing dependency aliases:

```python
RoutingDependency = Annotated[RoutingClient, Depends(get_routing_client)]
```

and add the route after the scenario test routes:

```python
@router.post(
    "/{household_id}/rendezvous-simulation", response_model=RendezvousResult
)
def simulate_rendezvous(
    household_id: str,
    repository: RepositoryDependency,
    routing_client: RoutingDependency,
) -> RendezvousResult:
    """Estimate when every member reaches the primary evacuation destination."""
    return RendezvousSimulationService(repository, routing_client).simulate(household_id)
```

Import `RoutingClient`, `get_routing_client`, `RendezvousResult`, and `RendezvousSimulationService` at the top of the module.

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_rendezvous_endpoint.py -v`
Expected: 2 passed

- [ ] **Step 5: Document the endpoint in the contract**

In `docs/iteration1-integration-contract.md`, add an entry alongside the other household endpoints:

```markdown
### POST /households/{household_id}/rendezvous-simulation

Estimates when every household member reaches the primary evacuation
destination from their declared usual location. Requires a 100% complete plan.
Results are not stored — figures reflect traffic at the time of the call.

Always `200` unless the household is unknown (`404`). `status` is one of:

- `ready` — `member_etas`, `everyone_together_seconds`, `slowest_member_id`, `warnings`
- `not_applicable` — `unavailable_reason`, and `missing_sections` when the plan is incomplete
- `unavailable` — the routing provider failed; no figures are returned
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/households.py backend/tests/test_rendezvous_endpoint.py docs/iteration1-integration-contract.md
git commit -m "feat(backend): expose the rendezvous simulation endpoint"
```

---

### Task 8: Frontend API client and store

**Files:**
- Modify: `frontend/src/api/client.js:130-142`
- Create: `frontend/src/stores/rendezvous.js`
- Test: `frontend/tests/rendezvousStore.test.js`

**Interfaces:**
- Consumes: `POST /households/{id}/rendezvous-simulation` (Task 7)
- Produces: `api.simulateRendezvous(householdId)`; `useRendezvousStore()` exposing `result`, `status`, `error`, `runSimulation()`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/rendezvousStore.test.js`, following the structure of `frontend/tests/localContextStore.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'

import { createRendezvousStore } from '../src/stores/rendezvous.js'

const READY = {
  status: 'ready',
  destination_name: "Relative's House",
  member_etas: [
    { member_id: 'm_001', display_name: 'Maya', origin_kind: 'home',
      travel_seconds: 720, distance_meters: 7200, waiting_seconds: 2100 },
  ],
  everyone_together_seconds: 2820,
  slowest_member_id: 'm_002',
  warnings: [],
  simulated_at: '2026-09-10T04:32:00Z',
}

test('a successful run stores the result and reports success', async () => {
  const store = createRendezvousStore({ simulate: async () => READY })

  await store.runSimulation('hh_1')

  assert.equal(store.status.value, 'success')
  assert.equal(store.result.value.everyone_together_seconds, 2820)
  assert.equal(store.error.value, null)
})

test('a not_applicable response is a result, not an error', async () => {
  const store = createRendezvousStore({
    simulate: async () => ({
      status: 'not_applicable',
      unavailable_reason: 'Finish your plan before running this simulation.',
      missing_sections: ['member_locations'],
      member_etas: [],
      warnings: [],
      simulated_at: '2026-09-10T04:32:00Z',
    }),
  })

  await store.runSimulation('hh_1')

  assert.equal(store.status.value, 'success')
  assert.equal(store.result.value.status, 'not_applicable')
  assert.equal(store.error.value, null)
})

test('a thrown request sets an error and clears any stale result', async () => {
  const store = createRendezvousStore({
    simulate: async () => { throw new Error('network down') },
  })
  store.result.value = READY

  await store.runSimulation('hh_1')

  assert.equal(store.status.value, 'error')
  assert.equal(store.result.value, null)
  assert.match(store.error.value, /network down/)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — cannot find `../src/stores/rendezvous.js`

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/api/client.js`, add to the `api` object:

```javascript
  simulateRendezvous: (householdId) =>
    request(`/households/${encodeURIComponent(householdId)}/rendezvous-simulation`, {
      method: 'POST',
    }),
```

Create `frontend/src/stores/rendezvous.js`:

```javascript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'

// The factory takes its transport so tests can drive it without a network.
export function createRendezvousStore(transport) {
  const result = ref(null)
  const status = ref('idle')
  const error = ref(null)

  async function runSimulation(householdId) {
    // not_applicable and unavailable are answers, not failures: they carry the
    // reason the user needs to see, so only a thrown request is an error.
    status.value = 'loading'
    error.value = null
    try {
      result.value = await transport.simulate(householdId)
      status.value = 'success'
    } catch (thrown) {
      result.value = null
      status.value = 'error'
      error.value = thrown instanceof Error ? thrown.message : 'The simulation could not run.'
    }
  }

  return { result, status, error, runSimulation }
}

export const useRendezvousStore = defineStore('rendezvous', () =>
  createRendezvousStore({ simulate: (householdId) => api.simulateRendezvous(householdId) }),
)
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test`
Expected: all pass, including the existing `localContextStore` tests

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.js frontend/src/stores/rendezvous.js frontend/tests/rendezvousStore.test.js
git commit -m "feat(frontend): add the rendezvous simulation store"
```

---

### Task 9: Usual location field in the People step

**Files:**
- Modify: `frontend/src/components/household/HouseholdMembersForm.vue` (member card, after the relationship field around line 97-106)

**Interfaces:**
- Consumes: `MemberUsualLocation` shape (Task 1)
- Produces: members in the plan draft carry `usual_location`

- [ ] **Step 1: Add the field to the member card**

In the member card template, after the relationship block:

```vue
          <div class="field">
            <label :for="`${member.member_id}-usual-kind`">Where are they during the day?</label>
            <select
              :id="`${member.member_id}-usual-kind`"
              :value="member.usual_location?.kind ?? ''"
              @change="setUsualKind(member, $event.target.value)"
            >
              <option value="">Not recorded</option>
              <option value="home">Home</option>
              <option value="work">Work</option>
              <option value="school">School</option>
              <option value="other">Somewhere else</option>
            </select>
          </div>

          <p v-if="member.usual_location?.kind === 'home'" class="hint">
            Uses your home address.
          </p>

          <AddressAutocompleteInput
            v-else-if="member.usual_location"
            label="Address"
            :model-value="member.usual_location.address"
            :helper-text="usualLocationHelperText(member)"
            @update:model-value="setUsualAddress(member, $event)"
            @select="selectUsualAddress(member, $event)"
          />
```

- [ ] **Step 2: Add the handlers**

In the `<script setup>` block:

```javascript
import AddressAutocompleteInput from '../common/AddressAutocompleteInput.vue'

function setUsualKind(member, kind) {
  // Changing kind discards any coordinates: they belonged to the old place.
  member.usual_location = kind
    ? { kind, address: '', latitude: null, longitude: null, verification_status: 'unverified' }
    : null
}

function setUsualAddress(member, address) {
  // Typing invalidates verification until a suggestion is selected again.
  member.usual_location.address = address
  member.usual_location.latitude = null
  member.usual_location.longitude = null
  member.usual_location.verification_status = 'unverified'
}

function selectUsualAddress(member, suggestion) {
  member.usual_location.address = suggestion.address ?? suggestion.label ?? ''
  member.usual_location.latitude = suggestion.latitude ?? null
  member.usual_location.longitude = suggestion.longitude ?? null
  member.usual_location.verification_status =
    suggestion.latitude != null && suggestion.longitude != null ? 'verified' : 'unverified'
}

function usualLocationHelperText(member) {
  if (!member.usual_location?.address) return ''
  return member.usual_location.verification_status === 'verified'
    ? 'Verified address'
    : 'Address saved but not verified'
}
```

Check the payload the `select` event emits in `AddressAutocompleteInput.vue` and in `ArrangementsForm.vue:145`, which already consumes it, and match the property names exactly rather than assuming them.

- [ ] **Step 3: Verify in the browser**

Run: `cd frontend && npm run dev`, then in a browser:

1. Open `/plan`, step 1. Each member shows "Where are they during the day?".
2. Choose **Home** — the address field is replaced by "Uses your home address."
3. Choose **Work** — the address field appears; typing shows suggestions; selecting one shows "Verified address".
4. Choose **Not recorded** — the field disappears and the value clears.
5. Save the plan, reload, return to step 1 — the selections survive.

- [ ] **Step 4: Confirm the build is clean**

Run: `cd frontend && npm run build`
Expected: builds without errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/household/HouseholdMembersForm.vue
git commit -m "feat(frontend): capture each member's usual daytime location"
```

---

### Task 10: Rendezvous panel on the scenarios page

**Files:**
- Create: `frontend/src/components/scenario/RendezvousPanel.vue`
- Modify: `frontend/src/views/ScenarioTesterView.vue`

**Interfaces:**
- Consumes: `useRendezvousStore` (Task 8); `RendezvousResult` shape (Task 6)
- Produces: the simulation UI

- [ ] **Step 1: Create the panel**

Create `frontend/src/components/scenario/RendezvousPanel.vue`:

```vue
<script setup>
import { computed } from 'vue'
import { useRendezvousStore } from '../../stores/rendezvous'
import { useHouseholdStore } from '../../stores/household'

const rendezvousStore = useRendezvousStore()
const householdStore = useHouseholdStore()

const SECTION_LABELS = {
  household_profile: 'Household profile',
  member_locations: 'Member locations',
  transport: 'Transport',
  backup_transport: 'Backup transport',
  primary_destination: 'Primary destination',
  backup_destination: 'Backup destination',
  responsibilities: 'Responsibilities',
}

const result = computed(() => rendezvousStore.result)
const isReady = computed(() => result.value?.status === 'ready')
const longestSeconds = computed(() =>
  Math.max(1, ...(result.value?.member_etas ?? []).map((eta) => eta.travel_seconds)),
)

function minutes(seconds) {
  return `${Math.round(seconds / 60)} min`
}

function barWidth(seconds) {
  return `${Math.round((seconds / longestSeconds.value) * 100)}%`
}

function run() {
  rendezvousStore.runSimulation(householdStore.householdId)
}
</script>

<template>
  <section class="card rendezvous">
    <h2>How long until everyone is together?</h2>

    <p v-if="!result" class="subhead">
      Estimates how long each person takes to reach your primary destination.
    </p>

    <template v-if="result?.status === 'not_applicable'">
      <p class="subhead">{{ result.unavailable_reason }}</p>
      <ul v-if="result.missing_sections.length" class="missing">
        <li v-for="section in result.missing_sections" :key="section">
          {{ SECTION_LABELS[section] ?? section }}
        </li>
      </ul>
      <router-link class="btn btn-primary btn-sm" to="/plan">Finish my plan</router-link>
    </template>

    <p v-else-if="result?.status === 'unavailable'" class="field-error">
      {{ result.unavailable_reason }}
    </p>

    <template v-else-if="isReady">
      <p class="headline-figure">
        Everyone together after
        <strong>{{ minutes(result.everyone_together_seconds) }}</strong>
        at {{ result.destination_name }}
      </p>

      <ul class="etas">
        <li v-for="eta in result.member_etas" :key="eta.member_id">
          <span class="eta-name">{{ eta.display_name }}</span>
          <span class="eta-origin">{{ eta.origin_kind }}</span>
          <span class="eta-bar"><span :style="{ width: barWidth(eta.travel_seconds) }" /></span>
          <span class="eta-time">{{ minutes(eta.travel_seconds) }}</span>
        </li>
      </ul>

      <ul v-if="result.warnings.length" class="warnings">
        <li v-for="warning in result.warnings" :key="warning">⚠️ {{ warning }}</li>
      </ul>

      <p class="caveat">
        An estimate against traffic at the time it was run, not a guarantee.
      </p>
    </template>

    <p v-if="rendezvousStore.error" class="field-error">{{ rendezvousStore.error }}</p>

    <button
      class="btn btn-accent"
      type="button"
      :disabled="rendezvousStore.status === 'loading'"
      @click="run"
    >
      {{ rendezvousStore.status === 'loading'
          ? 'Simulating…'
          : result ? 'Run again' : 'Run simulation' }}
    </button>
  </section>
</template>

<style scoped>
.rendezvous { margin-top: 1.5rem; }
.headline-figure { font-size: 1.15rem; margin: 0.5rem 0 1rem; }
.etas { list-style: none; margin: 0 0 1rem; padding: 0; }
.etas li {
  display: grid;
  grid-template-columns: minmax(4rem, 8rem) minmax(3rem, 5rem) minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.6rem;
  padding: 0.4rem 0;
}
.eta-origin { color: var(--color-text-muted); font-size: 0.85rem; }
.eta-bar { background: var(--color-bg-card-muted); border-radius: 999px; height: 0.6rem; }
.eta-bar > span { background: var(--color-accent); border-radius: 999px; display: block; height: 100%; }
.eta-time { font-variant-numeric: tabular-nums; font-weight: 600; }
.warnings, .missing { list-style: none; margin: 0 0 1rem; padding: 0; }
.warnings li, .missing li { padding: 0.3rem 0; }
.caveat { color: var(--color-text-muted); font-size: 0.85rem; }

@media (max-width: 520px) {
  .etas li { grid-template-columns: minmax(0, 1fr) auto; }
  .eta-origin, .eta-bar { display: none; }
}
</style>
```

- [ ] **Step 2: Mount it on the scenarios page**

In `frontend/src/views/ScenarioTesterView.vue`, import the panel and place it after the closing `</div>` of `.tester-grid`, inside the `v-else` branch so it shares the same "plan exists" guard as the rest of the page:

```vue
<RendezvousPanel />
```

- [ ] **Step 3: Verify in the browser**

Run: `cd frontend && npm run dev`, then:

1. With an incomplete plan, open `/scenarios`. The panel lists the missing sections and links to `/plan`.
2. Complete every section including a usual location for each member and a verified primary destination. Save.
3. Return to `/scenarios` and run the simulation. Bars appear in proportion, the slowest member's bar is full width, and the total equals the slowest member's time.
4. Mark a member as a dependant, save, and re-run — the collection warning appears.
5. Narrow the window to phone width — rows collapse to name and time without horizontal scrolling.

- [ ] **Step 4: Confirm the build and tests are clean**

Run: `cd frontend && npm run build && npm test`
Expected: builds and all tests pass

Run: `cd backend && python3 -m pytest -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/scenario/RendezvousPanel.vue frontend/src/views/ScenarioTesterView.vue
git commit -m "feat(frontend): show the rendezvous simulation on the scenarios page"
```

---

## Before merging to main

This branch changes shared behaviour. Raise these with the team first:

1. `GET /completion` returns **seven** sections. Every existing plan drops from 100% to 86% until each member has a usual location. Nothing breaks and no data is lost, but users will see it.
2. `docs/security/privacy-requirements.md` gains a High-sensitivity field. The privacy checklist should be re-run.
3. Migration `008` must be applied. `feature/ai-scenario-recommendations` holds `007`; if both land, confirm the ordering.
4. Live mode now requires `TOMTOM_API_KEY` to carry Routing access as well as Places. Verified working on the current key, 2026-09-10.
