"""Real Windows TCP state, real production transport; no device connections."""
import asyncio
import http.server
import socket
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.FacilityData.drivers.spot_http_transport import SpotHttpRequest, SpotHttpTransport, SpotRequestKind
from backend.FacilityData.drivers.spot_port_quarantine import (
    SourcePortLeasePool, SpotPortPoolError, SpotPortPoolExhausted, SystemGuardSocketFactory,
)
from backend.tests.test_spot_port_quarantine import _Clock, _SocketFactory


class OccupiedFactory(_SocketFactory):
    def __init__(self):
        super().__init__()
        self.occupied = set()
        self.queries = 0
        self.query_error = None

    def occupied_ports(self):
        self.queries += 1
        if self.query_error:
            raise self.query_error
        return set(self.occupied)


class TcpReuseTests(unittest.TestCase):
    def test_slow_os_query_cannot_issue_a_lease_after_positive_deadline(self):
        factory, clock = OccupiedFactory(), _Clock()
        def slow_query():
            clock.now += 6
            return set()
        factory.occupied_ports = slow_query
        pool = SourcePortLeasePool(capacity=2, socket_factory=factory, monotonic=clock)
        pool.initialize()
        old = pool.acquire(); pool.mark_connect_started(old); pool.release(old)
        clock.now = 77
        try:
            with self.assertRaises(SpotPortPoolExhausted):
                pool.acquire(timeout_seconds=5)
            self.assertEqual(pool.diagnostics()['source_port_pool_leased_count'], 0)
            self.assertEqual(len(factory.guards), 2)
            self.assertFalse(factory.guards[-1].closed)
        finally:
            pool.close()

    def test_concurrent_acquire_does_not_rebind_another_callers_lease(self):
        entered, release = threading.Event(), threading.Event()
        factory, clock = OccupiedFactory(), _Clock()
        count_lock = threading.Lock()
        calls = 0
        def query():
            nonlocal calls
            with count_lock:
                calls += 1
                first = calls == 1
            if first:
                entered.set()
                if not release.wait(3):
                    raise AssertionError('synthetic query was not released')
            return set()
        factory.occupied_ports = query
        pool = SourcePortLeasePool(capacity=2, socket_factory=factory, monotonic=clock)
        pool.initialize()
        old = pool.acquire(); pool.mark_connect_started(old); pool.release(old)
        clock.now = 77
        leases, errors = [], []
        def acquire():
            try: leases.append(pool.acquire())
            except Exception as exc: errors.append(exc)
        waiting = threading.Thread(target=acquire)
        waiting.start()
        try:
            self.assertTrue(entered.wait(1))
            other = pool.acquire()
            self.assertEqual(other.port, old.port)
            pool.mark_connect_started(other)
            release.set(); waiting.join(2)
            self.assertFalse(waiting.is_alive()); self.assertEqual(errors, [])
            self.assertEqual(len(leases), 1); self.assertNotEqual(leases[0].port, other.port)
            self.assertEqual(len(factory.guards), 3)
            pool.release(other); pool.release(leases[0])
        finally:
            release.set(); waiting.join(3); pool.close()
            self.assertFalse(waiting.is_alive())

    def test_stalled_os_query_keeps_close_bounded_and_cannot_revive_closed_pool(self):
        entered, release, close_returned = threading.Event(), threading.Event(), threading.Event()
        factory, clock = OccupiedFactory(), _Clock()

        def blocked_query():
            entered.set()
            if not release.wait(5):
                raise AssertionError('test failed to release OS query')
            return set()

        factory.occupied_ports = blocked_query
        pool = SourcePortLeasePool(capacity=2, socket_factory=factory, monotonic=clock)
        pool.initialize()
        lease = pool.acquire(); pool.mark_connect_started(lease); pool.release(lease)
        clock.now = 77
        transport = SpotHttpTransport(pool=pool)
        transport.start()
        worker, watchdog = transport._executor._thread, transport._response_deadline_thread
        # Releases the synthetic stall if the old implementation blocks the event loop.
        def emergency_release():
            close_returned.wait(2)
            release.set()
        safety = threading.Thread(target=emergency_release)
        safety.start()

        async def exercise():
            request = SpotHttpRequest(SpotRequestKind.TEMPERATURE, 'GET',
                                     'http://127.0.0.1:9/never-connect', {}, None, 1, 1)
            task = asyncio.create_task(transport.request(request))
            ticks = []
            async def heartbeat():
                while not close_returned.is_set():
                    ticks.append(time.monotonic())
                    await asyncio.sleep(.005)
            heartbeat_task = asyncio.create_task(heartbeat())
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 1))
                started = time.monotonic()
                self.assertFalse(await transport.close(timeout_sec=.05))
                elapsed = time.monotonic() - started
                self.assertLess(elapsed, .5)
                self.assertGreaterEqual(len(ticks), 3)
                self.assertTrue(worker.is_alive())  # Unfinished ownership cannot be called drained.
                self.assertFalse(pool.active)
                self.assertEqual(len(factory.guards), 2)
            finally:
                close_returned.set(); release.set()
                await heartbeat_task
                await asyncio.gather(task, return_exceptions=True)
                await asyncio.to_thread(worker.join, 2)
                self.assertTrue(await transport.close(timeout_sec=.1))
                self.assertFalse(worker.is_alive()); self.assertFalse(watchdog.is_alive())
                self.assertEqual(len(factory.guards), 2)  # No late rebind after close.
                self.assertTrue(all(guard.closed for guard in factory.guards))
        try:
            asyncio.run(exercise())
        finally:
            close_returned.set(); release.set(); safety.join(3)
            self.assertFalse(safety.is_alive())

    def test_system_query_uses_all_local_ports_including_pidless_time_wait(self):
        entries = [SimpleNamespace(laddr=SimpleNamespace(port=41000), raddr=SimpleNamespace(port=80),
                    status='TIME_WAIT', pid=None),
                   SimpleNamespace(laddr=SimpleNamespace(port=41001), raddr=None, status='LISTEN', pid=10)]
        with patch('backend.FacilityData.drivers.spot_port_quarantine.psutil.net_connections', return_value=entries) as query:
            self.assertEqual(SystemGuardSocketFactory().occupied_ports(), {41000, 41001})
            query.assert_called_once_with(kind='tcp4')

    def test_system_query_errors_and_invalid_rows_are_not_empty_success(self):
        for entry in (SimpleNamespace(laddr=None), SimpleNamespace(laddr=SimpleNamespace(port=0)),
                      SimpleNamespace(laddr=SimpleNamespace(port=True))):
            with self.subTest(entry=entry), patch(
                'backend.FacilityData.drivers.spot_port_quarantine.psutil.net_connections', return_value=[entry]
            ), self.assertRaises(OSError):
                SystemGuardSocketFactory().occupied_ports()
        with patch('backend.FacilityData.drivers.spot_port_quarantine.psutil.net_connections',
                   side_effect=PermissionError('synthetic denied')), self.assertRaises(PermissionError):
            SystemGuardSocketFactory().occupied_ports()

    def test_all_os_busy_times_out_without_early_reuse_and_close_still_works(self):
        factory, clock = OccupiedFactory(), _Clock()
        pool = SourcePortLeasePool(capacity=2, socket_factory=factory, monotonic=clock, acquire_timeout_seconds=0)
        pool.initialize()
        for _ in range(2):
            lease = pool.acquire(); pool.mark_connect_started(lease); pool.release(lease)
            factory.occupied.add(lease.port)
        clock.now = 77
        try:
            with self.assertRaises(SpotPortPoolExhausted): pool.acquire()
            self.assertEqual(pool.diagnostics()['source_port_pool_rebind_pending_count'], 2)
            self.assertEqual(pool.diagnostics()['source_port_reuse_violation_count'], 0)
            self.assertEqual(pool.diagnostics()['source_port_pool_leased_count'], 0)
        finally:
            pool.close()
            self.assertTrue(all(guard.closed for guard in factory.guards))

    def test_ready_ports_still_in_os_table_are_not_leased_and_later_recover(self):
        factory, clock = OccupiedFactory(), _Clock()
        pool = SourcePortLeasePool(capacity=3, socket_factory=factory, monotonic=clock, acquire_timeout_seconds=0)
        pool.initialize()
        try:
            first = pool.acquire(); pool.mark_connect_started(first); pool.release(first)
            second = pool.acquire(); pool.mark_connect_started(second); pool.release(second)
            factory.occupied = {first.port, second.port}
            clock.now = 77
            fresh = pool.acquire()
            self.assertNotIn(fresh.port, factory.occupied)
            self.assertEqual(factory.queries, 1)  # One OS snapshot for all due rebinds.
            self.assertEqual(pool.diagnostics()['source_port_pool_rebind_pending_count'], 2)
            pool.release(fresh)
            with self.assertRaises(SpotPortPoolExhausted): pool.acquire()
            factory.occupied.clear(); clock.now = 78
            recovered = pool.acquire(); pool.mark_connect_started(recovered)
            self.assertEqual(recovered.port, first.port)
            self.assertEqual(pool.diagnostics()['source_port_minimum_reuse_interval_seconds'], 78)
            pool.release(recovered)
        finally: pool.close()

    def test_os_query_failure_cannot_promote_any_port_and_retry_is_supported(self):
        factory, clock = OccupiedFactory(), _Clock()
        pool = SourcePortLeasePool(capacity=2, socket_factory=factory, monotonic=clock, acquire_timeout_seconds=0)
        pool.initialize()
        try:
            lease = pool.acquire(); pool.mark_connect_started(lease); pool.release(lease)
            clock.now = 77; factory.query_error = OSError('synthetic OS query failure')
            with self.assertRaises(SpotPortPoolError): pool.acquire()
            self.assertEqual(pool.diagnostics()['source_port_pool_leased_count'], 0)
            factory.query_error = None
            recovered = pool.acquire(); pool.release(recovered)
        finally: pool.close()

    @unittest.skipUnless(sys.platform == 'win32' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'), 'Native Windows TCP test')
    def test_native_client_close_time_wait_does_not_consume_bind_retry_budget(self):
        import psutil
        peers = []
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def do_GET(self):
                peers.append(self.client_address[1])
                self.send_response(200); self.send_header('Content-Length', '3'); self.end_headers()
                self.wfile.write(b'500')  # Client actively closes after the full body.
            def log_message(self, *_args): pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever); thread.start()
        offset = [0.0]
        pool = SourcePortLeasePool(capacity=12, monotonic=lambda: time.monotonic() + offset[0])
        transport = SpotHttpTransport(pool=pool)
        worker = watchdog = None
        try:
            transport.start()
            worker = transport._executor._thread; watchdog = transport._response_deadline_thread
            request = SpotHttpRequest(SpotRequestKind.TEMPERATURE, 'GET',
                f'http://127.0.0.1:{server.server_port}/temperature', {}, None, 1, 1)
            for _ in range(8): self.assertEqual(transport.request_sync(request).body, b'500')
            first_ports = set(peers)
            # Confirm actual OS state rather than merely asserting a fake busy flag.
            until = time.monotonic() + 2
            while True:
                busy = {c.laddr.port for c in psutil.net_connections(kind='tcp4')
                        if c.status == 'TIME_WAIT' and c.laddr and c.raddr and c.raddr.port == server.server_port}
                if first_ports <= busy or time.monotonic() >= until: break
                threading.Event().wait(.01)
            self.assertEqual(len(first_ports), 8); self.assertTrue(first_ports <= busy)
            offset[0] += 77.2  # Accelerates only the pool's eligibility clock, not OS TCP state.
            self.assertEqual(transport.request_sync(request).body, b'500')
            self.assertNotIn(peers[-1], first_ports)
            diag = transport.diagnostics()
            self.assertEqual(diag['source_port_bind_collision_count'], 0)
            self.assertEqual(diag['source_port_transport_failure_count'], 0)
            self.assertEqual(diag['source_port_pool_rebind_pending_count'], 8)
        finally:
            closed = asyncio.run(transport.close())
            server.shutdown(); server.server_close(); thread.join(3)
            self.assertTrue(closed); self.assertFalse(thread.is_alive())
            if worker: self.assertFalse(worker.is_alive())
            if watchdog: self.assertFalse(watchdog.is_alive())


if __name__ == '__main__': unittest.main()
