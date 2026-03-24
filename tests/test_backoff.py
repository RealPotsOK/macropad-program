from macropad.backoff import ExponentialBackoff


def test_backoff_sequence_respects_cap() -> None:
    backoff = ExponentialBackoff(
        initial=1.0,
        max_delay=5.0,
        factor=2.0,
        jitter_low=1.0,
        jitter_high=1.0,
        random_fn=lambda _low, _high: 1.0,
    )

    delays = [backoff.next_delay() for _ in range(5)]
    assert delays == [1.0, 2.0, 4.0, 5.0, 5.0]


def test_backoff_reset_restarts_sequence() -> None:
    backoff = ExponentialBackoff(
        initial=1.0,
        max_delay=30.0,
        factor=2.0,
        jitter_low=1.0,
        jitter_high=1.0,
        random_fn=lambda _low, _high: 1.0,
    )

    _ = backoff.next_delay()
    _ = backoff.next_delay()
    backoff.reset()

    assert backoff.next_delay() == 1.0


def test_backoff_does_not_overflow_after_many_attempts() -> None:
    backoff = ExponentialBackoff(
        initial=1.0,
        max_delay=5.0,
        factor=2.0,
        jitter_low=1.0,
        jitter_high=1.0,
        random_fn=lambda _low, _high: 1.0,
    )

    last_delay = 0.0
    for _ in range(5000):
        last_delay = backoff.next_delay()

    assert last_delay == 5.0
