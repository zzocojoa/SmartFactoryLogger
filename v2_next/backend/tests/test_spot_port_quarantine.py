import math
import unittest
from unittest.mock import patch

from backend.FacilityData.drivers.spot_port_quarantine import (
    CAPACITY_PLANNING_MAX_REQUESTS_PER_SECOND,
    MINIMUM_REQUIRED_POOL_CAPACITY,
    MINIMUM_REQUIRED_REUSE_INTERVAL_SECONDS,
    POLICY_VERSION,
    POOL_CAPACITY,
    QUARANTINE_SAFETY_MARGIN_SECONDS,
    QUARANTINE_SECONDS,
    SourcePortLeasePool,
    SpotPortPoolError,
    SpotPortPoolExhausted,
    SpotPortPoolInitError,
    SpotPortReuseViolation,
)


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _Guard:
    def __init__(self) -> None:
        self.closed = False
        self.close_error: Exception | None = None

    def close(self) -> None:
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class _SocketFactory:
    supported = True

    def __init__(
        self,
        *,
        fail_create_at: int | None = None,
        fixed_port: int | None = None,
    ) -> None:
        self._next_port = 41000
        self._create_count = 0
        self.fail_create_at = fail_create_at
        self.fixed_port = fixed_port
        self.fail_rebind_count = 0
        self.guards: list[_Guard] = []

    def create_guard(self, _local_host: str, port: int = 0) -> tuple[_Guard, int]:
        self._create_count += 1
        if self.fail_create_at == self._create_count:
            raise OSError("simulated init failure")
        if port and self.fail_rebind_count:
            self.fail_rebind_count -= 1
            raise OSError("simulated rebind failure")
        actual_port = port or self.fixed_port or self._next_port
        if not port and self.fixed_port is None:
            self._next_port += 1
        guard = _Guard()
        self.guards.append(guard)
        return guard, actual_port


class SourcePortLeasePoolTests(unittest.TestCase):
    def test_invalid_pool_configuration_is_rejected(self) -> None:
        invalid_cases = (
            {"capacity": 0},
            {"capacity": -1},
            {"capacity": 0.5},
            {"capacity": True},
            {"quarantine_seconds": 0.0},
            {"quarantine_seconds": float("nan")},
            {"acquire_timeout_seconds": -1.0},
            {"acquire_timeout_seconds": float("inf")},
            {"rebind_retry_interval_seconds": 0.0},
            {"rebind_retry_interval_seconds": float("nan")},
        )

        for kwargs in invalid_cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                SourcePortLeasePool(socket_factory=_SocketFactory(), **kwargs)

    def make_pool(
        self,
        *,
        capacity: int = 1,
        factory: _SocketFactory | None = None,
        clock: _Clock | None = None,
    ) -> tuple[SourcePortLeasePool, _SocketFactory, _Clock]:
        selected_factory = factory or _SocketFactory()
        selected_clock = clock or _Clock()
        pool = SourcePortLeasePool(
            capacity=capacity,
            quarantine_seconds=QUARANTINE_SECONDS,
            acquire_timeout_seconds=0.0,
            rebind_retry_interval_seconds=1.0,
            socket_factory=selected_factory,
            monotonic=selected_clock,
        )
        pool.initialize()
        return pool, selected_factory, selected_clock

    def test_acquire_rejects_invalid_timeout_overrides(self) -> None:
        pool, _factory, _clock = self.make_pool()
        lease = pool.acquire()

        try:
            for timeout_seconds in (
                -1.0,
                float("nan"),
                float("inf"),
                float("-inf"),
            ):
                with self.subTest(timeout_seconds=timeout_seconds):
                    with self.assertRaisesRegex(
                        ValueError,
                        "finite and non-negative",
                    ):
                        pool.acquire(timeout_seconds)
        finally:
            pool.release(lease)

    def test_guard_close_failure_fails_pool_without_losing_guard(self) -> None:
        pool, factory, _clock = self.make_pool()
        guard = factory.guards[0]
        guard.close_error = OSError("simulated close failure")

        with self.assertRaisesRegex(
            SpotPortPoolError,
            "failed to release source-port guard socket",
        ):
            pool.acquire()

        diagnostics = pool.diagnostics()
        self.assertEqual(diagnostics["source_port_pool_guarded_count"], 1)
        self.assertEqual(diagnostics["source_port_pool_leased_count"], 0)
        with self.assertRaises(SpotPortPoolError):
            pool.acquire()

        guard.close_error = None
        pool.close()
        self.assertTrue(guard.closed)

    def test_close_attempts_all_guards_and_retries_failed_closes(self) -> None:
        pool, factory, _clock = self.make_pool(capacity=2)
        failed_guard, healthy_guard = factory.guards
        failed_guard.close_error = OSError("simulated shutdown close failure")

        with self.assertRaisesRegex(
            SpotPortPoolError,
            "failed to close source-port guard sockets",
        ):
            pool.close()

        self.assertFalse(failed_guard.closed)
        self.assertTrue(healthy_guard.closed)
        failed_guard.close_error = None

        pool.close()

        self.assertTrue(failed_guard.closed)
        with self.assertRaises(SpotPortPoolError):
            pool.acquire()

    def test_exact_quarantine_boundary_controls_reuse(self) -> None:
        pool, _factory, clock = self.make_pool()
        first = pool.acquire()
        pool.mark_connect_started(first)
        pool.release(first)

        clock.now = 76.999
        with self.assertRaises(SpotPortPoolExhausted):
            pool.acquire()

        clock.now = 77.0
        second = pool.acquire()
        self.assertEqual(second.port, first.port)
        pool.mark_connect_started(second)
        diagnostics = pool.diagnostics()

        self.assertEqual(diagnostics["source_port_minimum_reuse_interval_seconds"], 77.0)
        self.assertEqual(diagnostics["source_port_reuse_violation_count"], 0)
        pool.release(second)

    def test_success_failure_and_timeout_release_share_quarantine_state(self) -> None:
        pool, _factory, clock = self.make_pool(capacity=3)
        leases = [pool.acquire() for _ in range(3)]
        for lease in leases:
            pool.mark_connect_started(lease)
            pool.release(lease)

        diagnostics = pool.diagnostics()
        self.assertEqual(diagnostics["source_port_pool_quarantined_count"], 3)
        self.assertEqual(diagnostics["source_port_pool_guarded_count"], 0)

        clock.now = 77.0
        reacquired = [pool.acquire() for _ in range(3)]
        self.assertEqual({lease.port for lease in reacquired}, {lease.port for lease in leases})

    def test_rounded_down_deadline_keeps_lease_quarantined_until_full_interval(self) -> None:
        # Monotonic clock samples never go backwards. Addition and subtraction
        # disagree at these offsets even though diagnostics round both to 77.0.
        for started_at in (32691.003, 32691.007, 32691.01):
            with self.subTest(started_at=started_at):
                pool, factory, clock = self.make_pool()
                self.addCleanup(pool.close)
                clock.now = started_at
                first = pool.acquire()
                pool.mark_connect_started(first)
                pool.release(first)

                rounded_deadline = started_at + QUARANTINE_SECONDS
                self.assertLess(rounded_deadline - started_at, QUARANTINE_SECONDS)
                clock.now = rounded_deadline
                with self.assertRaises(SpotPortPoolExhausted):
                    pool.acquire()
                self.assertEqual(len(factory.guards), 1)
                self.assertTrue(pool.active)
                self.assertEqual(pool.diagnostics()["source_port_reuse_violation_count"], 0)

                clock.now = math.nextafter(rounded_deadline, math.inf)
                self.assertGreaterEqual(clock.now - started_at, QUARANTINE_SECONDS)
                second = pool.acquire()
                self.assertEqual(second.port, first.port)
                pool.mark_connect_started(second)
                pool.release(second)

                clock.now += 1000.0
                third = pool.acquire()
                pool.mark_connect_started(third)
                pool.release(third)
                self.assertTrue(pool.active)
                self.assertEqual(pool.diagnostics()["source_port_reuse_violation_count"], 0)

    def test_rounded_deadline_uses_release_time_not_connect_start(self) -> None:
        pool, _factory, clock = self.make_pool()
        self.addCleanup(pool.close)
        clock.now = 32600.0
        first = pool.acquire()
        pool.mark_connect_started(first)
        released_at = 32691.003
        clock.now = released_at
        pool.release(first)

        clock.now = released_at + QUARANTINE_SECONDS
        with self.assertRaises(SpotPortPoolExhausted):
            pool.acquire()

        clock.now = math.nextafter(clock.now, math.inf)
        second = pool.acquire()
        pool.mark_connect_started(second)
        pool.release(second)
        self.assertTrue(pool.active)

    def test_waiting_acquire_advances_past_rounded_down_deadline(self) -> None:
        pool, _factory, clock = self.make_pool()
        self.addCleanup(pool.close)
        clock.now = 32691.003
        first = pool.acquire()
        pool.mark_connect_started(first)
        pool.release(first)
        clock.now += QUARANTINE_SECONDS
        safe_deadline = math.nextafter(clock.now, math.inf)

        def advance_clock(*, timeout: float) -> None:
            self.assertGreater(timeout, 0.0)
            self.assertLessEqual(timeout, 5.0)
            clock.now = safe_deadline

        with patch.object(pool._condition, "wait", side_effect=advance_clock) as wait:
            second = pool.acquire(timeout_seconds=5.0)
        wait.assert_called_once()
        pool.mark_connect_started(second)
        pool.release(second)
        self.assertTrue(pool.active)
        self.assertEqual(pool.diagnostics()["source_port_pool_exhaustion_count"], 0)
        self.assertEqual(pool.diagnostics()["source_port_reuse_violation_count"], 0)

    def test_fractional_clock_offsets_do_not_create_false_reuse_violations(self) -> None:
        for boundary in (77.0, 2.0**15, 2.0**16, 2.0**24, 2.0**32):
            for milliseconds in range(1000):
                started_at = boundary - QUARANTINE_SECONDS + milliseconds / 1000.0
                with self.subTest(started_at=started_at):
                    pool, _factory, clock = self.make_pool()
                    try:
                        clock.now = started_at
                        first = pool.acquire()
                        pool.mark_connect_started(first)
                        pool.release(first)

                        clock.now = started_at + QUARANTINE_SECONDS
                        if clock.now - started_at < QUARANTINE_SECONDS:
                            with self.assertRaises(SpotPortPoolExhausted):
                                pool.acquire()
                            clock.now = math.nextafter(clock.now, math.inf)

                        self.assertGreaterEqual(clock.now - started_at, QUARANTINE_SECONDS)
                        second = pool.acquire()
                        pool.mark_connect_started(second)
                        pool.release(second)
                        self.assertTrue(pool.active)
                        self.assertEqual(pool.diagnostics()["source_port_reuse_violation_count"], 0)
                    finally:
                        pool.close()

    def test_rounded_deadline_preserves_rebind_retry(self) -> None:
        pool, factory, clock = self.make_pool()
        self.addCleanup(pool.close)
        clock.now = 32691.003
        first = pool.acquire()
        pool.mark_connect_started(first)
        pool.release(first)
        factory.fail_rebind_count = 1

        clock.now += QUARANTINE_SECONDS
        with self.assertRaises(SpotPortPoolExhausted):
            pool.acquire()
        self.assertEqual(pool.diagnostics()["source_port_rebind_retry_count"], 0)

        clock.now = math.nextafter(clock.now, math.inf)
        with self.assertRaises(SpotPortPoolExhausted):
            pool.acquire()
        self.assertEqual(pool.diagnostics()["source_port_rebind_retry_count"], 1)
        self.assertEqual(pool.diagnostics()["source_port_pool_rebind_pending_count"], 1)

        clock.now += 1.0
        second = pool.acquire()
        pool.mark_connect_started(second)
        pool.release(second)
        self.assertTrue(pool.active)

    def test_sub_77_interval_still_latches_violation_even_if_diagnostics_round_up(self) -> None:
        pool, _factory, clock = self.make_pool()
        self.addCleanup(pool.close)
        started_at = 32691.003
        clock.now = started_at
        first = pool.acquire()
        pool.mark_connect_started(first)
        pool.release(first)

        rounded_deadline = started_at + QUARANTINE_SECONDS
        clock.now = math.nextafter(rounded_deadline, math.inf)
        second = pool.acquire()
        # Deliberately break the clock after acquisition to exercise the
        # independent invariant check; do not tolerate even this small deficit.
        clock.now = rounded_deadline
        with self.assertRaises(SpotPortReuseViolation):
            pool.mark_connect_started(second)
        pool.release(second)
        clock.now += 1000.0
        pool.initialize()
        with self.assertRaises(SpotPortReuseViolation):
            pool.acquire()
        self.assertFalse(pool.active)
        self.assertEqual(pool.diagnostics()["source_port_reuse_violation_count"], 1)
        self.assertEqual(pool.diagnostics()["source_port_minimum_reuse_interval_seconds"], 77.0)

    def test_rebind_failure_never_returns_port_to_available_queue(self) -> None:
        pool, factory, clock = self.make_pool()
        lease = pool.acquire()
        pool.mark_connect_started(lease)
        pool.release(lease)
        factory.fail_rebind_count = 1

        clock.now = 77.0
        with self.assertRaises(SpotPortPoolExhausted):
            pool.acquire()
        diagnostics = pool.diagnostics()
        self.assertEqual(diagnostics["source_port_pool_rebind_pending_count"], 1)
        self.assertEqual(diagnostics["source_port_rebind_retry_count"], 1)

        clock.now = 78.0
        recovered = pool.acquire()
        self.assertEqual(recovered.port, lease.port)

    def test_pool_exhaustion_is_fail_closed(self) -> None:
        pool, _factory, _clock = self.make_pool()
        lease = pool.acquire()

        with self.assertRaises(SpotPortPoolExhausted):
            pool.acquire()

        diagnostics = pool.diagnostics()
        self.assertEqual(diagnostics["source_port_pool_exhaustion_count"], 1)
        self.assertEqual(diagnostics["source_port_pool_acquire_wait_count"], 1)
        pool.release(lease)

    def test_invariant_violation_blocks_future_acquires(self) -> None:
        pool, _factory, clock = self.make_pool()
        first = pool.acquire()
        pool.mark_connect_started(first)
        pool.release(first)

        clock.now = 77.0
        second = pool.acquire()
        clock.now = 74.0
        with self.assertRaises(SpotPortReuseViolation):
            pool.mark_connect_started(second)
        pool.release(second)

        with self.assertRaises(SpotPortReuseViolation):
            pool.acquire()
        self.assertEqual(pool.diagnostics()["source_port_reuse_violation_count"], 1)

    def test_partial_initialization_closes_every_created_guard(self) -> None:
        factory = _SocketFactory(fail_create_at=3)
        pool = SourcePortLeasePool(
            capacity=4,
            socket_factory=factory,
            monotonic=_Clock(),
        )

        with self.assertRaises(SpotPortPoolInitError):
            pool.initialize()

        self.assertEqual(len(factory.guards), 2)
        self.assertTrue(all(guard.closed for guard in factory.guards))
        self.assertFalse(pool.active)

    def test_duplicate_guard_port_closes_every_created_guard(self) -> None:
        factory = _SocketFactory(fixed_port=41000)
        pool = SourcePortLeasePool(
            capacity=2,
            socket_factory=factory,
            monotonic=_Clock(),
        )

        with self.assertRaisesRegex(
            SpotPortPoolInitError,
            "duplicate source port",
        ):
            pool.initialize()

        self.assertEqual(len(factory.guards), 2)
        self.assertTrue(all(guard.closed for guard in factory.guards))
        self.assertFalse(pool.active)

    def test_diagnostics_are_aggregate_only(self) -> None:
        pool, _factory, _clock = self.make_pool(capacity=2)
        diagnostics = pool.diagnostics()

        self.assertEqual(diagnostics["source_port_policy_version"], POLICY_VERSION)
        self.assertEqual(
            diagnostics["source_port_minimum_required_reuse_interval_seconds"],
            MINIMUM_REQUIRED_REUSE_INTERVAL_SECONDS,
        )
        self.assertEqual(
            diagnostics["source_port_quarantine_safety_margin_seconds"],
            QUARANTINE_SAFETY_MARGIN_SECONDS,
        )
        self.assertEqual(
            diagnostics["source_port_quarantine_seconds"],
            QUARANTINE_SECONDS,
        )
        self.assertEqual(
            diagnostics["source_port_minimum_required_pool_capacity"],
            MINIMUM_REQUIRED_POOL_CAPACITY,
        )
        self.assertEqual(diagnostics["source_port_pool_capacity"], 2)
        self.assertFalse(any("port_list" in key for key in diagnostics))
        self.assertFalse(any(isinstance(value, list) for value in diagnostics.values()))

    def test_production_pool_covers_six_requests_per_second_for_full_quarantine(self) -> None:
        self.assertEqual(CAPACITY_PLANNING_MAX_REQUESTS_PER_SECOND, 6.0)
        self.assertEqual(MINIMUM_REQUIRED_POOL_CAPACITY, 462)
        self.assertGreaterEqual(POOL_CAPACITY, MINIMUM_REQUIRED_POOL_CAPACITY)

        pool, _factory, clock = self.make_pool(
            capacity=POOL_CAPACITY,
        )
        for request_index in range(POOL_CAPACITY * 2):
            clock.now = (
                request_index
                / CAPACITY_PLANNING_MAX_REQUESTS_PER_SECOND
            )
            lease = pool.acquire()
            pool.mark_connect_started(lease)
            pool.release(lease)

        diagnostics = pool.diagnostics()
        self.assertEqual(diagnostics["source_port_pool_acquire_wait_count"], 0)
        self.assertEqual(diagnostics["source_port_pool_exhaustion_count"], 0)
        self.assertEqual(diagnostics["source_port_reuse_violation_count"], 0)
        self.assertGreaterEqual(
            diagnostics["source_port_minimum_reuse_interval_seconds"],
            QUARANTINE_SECONDS,
        )


if __name__ == "__main__":
    unittest.main()
