import unittest

from backend.FacilityData.drivers.spot_port_quarantine import (
    POLICY_VERSION,
    SourcePortLeasePool,
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

    def close(self) -> None:
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
            quarantine_seconds=75.0,
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

    def test_exact_quarantine_boundary_controls_reuse(self) -> None:
        pool, _factory, clock = self.make_pool()
        first = pool.acquire()
        pool.mark_connect_started(first)
        pool.release(first)

        clock.now = 74.999
        with self.assertRaises(SpotPortPoolExhausted):
            pool.acquire()

        clock.now = 75.0
        second = pool.acquire()
        self.assertEqual(second.port, first.port)
        pool.mark_connect_started(second)
        diagnostics = pool.diagnostics()

        self.assertEqual(diagnostics["source_port_minimum_reuse_interval_seconds"], 75.0)
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

        clock.now = 75.0
        reacquired = [pool.acquire() for _ in range(3)]
        self.assertEqual({lease.port for lease in reacquired}, {lease.port for lease in leases})

    def test_rebind_failure_never_returns_port_to_available_queue(self) -> None:
        pool, factory, clock = self.make_pool()
        lease = pool.acquire()
        pool.mark_connect_started(lease)
        pool.release(lease)
        factory.fail_rebind_count = 1

        clock.now = 75.0
        with self.assertRaises(SpotPortPoolExhausted):
            pool.acquire()
        diagnostics = pool.diagnostics()
        self.assertEqual(diagnostics["source_port_pool_rebind_pending_count"], 1)
        self.assertEqual(diagnostics["source_port_rebind_retry_count"], 1)

        clock.now = 76.0
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

        clock.now = 75.0
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
        self.assertEqual(diagnostics["source_port_pool_capacity"], 2)
        self.assertFalse(any("port_list" in key for key in diagnostics))
        self.assertFalse(any(isinstance(value, list) for value in diagnostics.values()))


if __name__ == "__main__":
    unittest.main()
