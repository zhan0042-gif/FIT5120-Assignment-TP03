from app.services.rate_limit import AskRateLimit


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def limiter(clock: Clock, **kwargs) -> AskRateLimit:
    return AskRateLimit(clock=clock, **kwargs)


def test_the_defaults_leave_room_for_the_other_feature_on_the_shared_quota() -> None:
    default = AskRateLimit()

    assert default.per_household == 6
    assert default.overall == 30
    assert default.window_seconds == 60.0


def test_a_household_is_allowed_up_to_its_limit_and_then_blocked() -> None:
    clock = Clock()
    guard = limiter(clock, per_household=3, overall=100)

    assert [guard.allow("hh_a") for _ in range(4)] == [True, True, True, False]


def test_households_are_counted_separately() -> None:
    clock = Clock()
    guard = limiter(clock, per_household=1, overall=100)

    assert guard.allow("hh_a") is True
    assert guard.allow("hh_a") is False
    assert guard.allow("hh_b") is True


def test_the_overall_limit_blocks_every_household() -> None:
    clock = Clock()
    guard = limiter(clock, per_household=10, overall=2)

    assert guard.allow("hh_a") is True
    assert guard.allow("hh_b") is True
    assert guard.allow("hh_c") is False


def test_a_request_blocked_by_the_household_limit_does_not_use_overall_quota() -> None:
    clock = Clock()
    guard = limiter(clock, per_household=2, overall=3)

    assert guard.allow("hh_a") is True
    assert guard.allow("hh_a") is True
    assert guard.allow("hh_a") is False  # refused, so it must not count towards overall
    assert guard.allow("hh_b") is True  # the third overall slot is still free


def test_a_request_blocked_by_the_overall_limit_does_not_use_household_quota() -> None:
    clock = Clock()
    guard = limiter(clock, per_household=2, overall=2)

    clock.now = 0.0
    assert guard.allow("hh_a") is True
    clock.now = 30.0
    assert guard.allow("hh_b") is True  # overall is now used up
    clock.now = 31.0
    assert guard.allow("hh_b") is False  # refused by the overall limit, so not recorded
    clock.now = 61.0  # hh_a's question has left the window; hh_b's first is still in it
    assert guard.allow("hh_b") is True  # would be refused if the 31s attempt had been counted


def test_the_window_slides() -> None:
    clock = Clock()
    guard = limiter(clock, per_household=2, overall=100)

    assert guard.allow("hh_a") is True
    assert guard.allow("hh_a") is True
    clock.now = 59.0
    assert guard.allow("hh_a") is False
    clock.now = 60.0
    assert guard.allow("hh_a") is True


def test_old_households_are_forgotten_so_memory_does_not_grow_without_bound() -> None:
    clock = Clock()
    guard = limiter(clock, per_household=2, overall=1000, sweep_above=3)

    for number in range(5):
        guard.allow(f"hh_{number}")
    clock.now = 61.0
    guard.allow("hh_new")

    # Only the newcomer and the overall counter remain.
    assert len(guard._events) == 2
