"""L1: real service/driver lifecycle and loops, synthetic device boundaries only."""
import os
import tempfile
import threading
import time
import unittest
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend import app as backend_app
from backend.FacilityData import service as service_module
from backend.FacilityData.drivers import real_plc as driver_module
from backend.FacilityData.drivers.csv_replay import CsvReplayDriver
from backend.FacilityData.drivers.mock_plc import MockPLCDriver
from backend.FacilityData.operator_metadata import OperatorMetadataStore
from backend.FacilityData.repository import CSVLoggerService


class ObservedEvent:
    def __init__(self):
        self.event = threading.Event()
        self.was_set = threading.Event()
        self.clear_count = 0

    def clear(self):
        self.clear_count += 1
        self.event.clear()

    def set(self):
        self.event.set()
        self.was_set.set()

    def is_set(self):
        return self.event.is_set()

    def wait(self, timeout=None):
        return self.event.wait(timeout)


class DeviceBoundary:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.calls = Counter()
        self.lock = threading.Lock()

    def read(self, value):
        with self.lock:
            self.calls[threading.current_thread()] += 1
        self.entered.set()
        if not self.release.wait(30):
            raise AssertionError('test did not release synthetic device read')
        return value


class FakeSocket:
    def __init__(self):
        self.connections = 0
        self.closes = 0
        self.fail_close = False
        self.fail_connect = False
        self.close_entered = threading.Event()
        self.close_release = threading.Event()
        self.close_release.set()

    def setsockopt(self, *args):
        pass

    def setblocking(self, *args):
        pass

    def settimeout(self, *args):
        pass

    def connect_ex(self, *args):
        self.connections += 1
        if self.fail_connect:
            raise OSError('synthetic offline PLC')
        return 0

    def connect(self, *args):
        self.connect_ex(*args)

    def close(self):
        self.closes += 1
        self.close_entered.set()
        if not self.close_release.wait(30):
            raise AssertionError('test did not release synthetic socket close')
        if self.fail_close:
            raise OSError('synthetic socket close failure')


class WorkerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.dict(os.environ, {'V2_MODE': 'MOCK'}))
        self.stack.enter_context(patch.object(service_module.config, 'APP_DATA_DIR', self.root))
        self.stack.enter_context(patch.object(service_module.config, 'INTERVAL_SEC', .25))
        self.stack.enter_context(patch.object(service_module, 'operator_metadata_store',
                                            OperatorMetadataStore(self.root/'metadata.json')))
        self.service = service_module.PLCService(use_mock=False,
            operator_metadata_runtime_state_path=self.root/'runtime.json')
        self.driver = self.service.driver
        self.driver._worker_stop = ObservedEvent()
        self.service._stop_event = ObservedEvent()
        self.logger = CSVLoggerService()
        self.logger.apply_config(log_path=self.root)
        self.logger.running = True  # Real enqueue, no unrelated writer owner.
        self.stack.enter_context(patch.object(service_module, 'logger_service', self.logger))
        self.devices = {name: DeviceBoundary() for name in ('ext', 'ls', 'spot')}
        self.stack.enter_context(patch.object(self.driver, '_read_extruder',
            side_effect=lambda deadline: self.devices['ext'].read({'Count': 20, 'Speed': 1, 'Press': 30})))
        self.stack.enter_context(patch.object(self.driver, '_read_ls',
            side_effect=lambda deadline: self.devices['ls'].read({'Temp_F': 450})))
        # Keep production _read_spot, worker loop, snapshot update and read_data.
        self.stack.enter_context(patch.object(driver_module, 'get_cached_spot_temp',
            side_effect=lambda: self.devices['spot'].read(500)))
        self.stack.enter_context(patch.object(driver_module, 'get_spot_diagnostics', return_value={
            'spot_temperature_effective_c': 500, 'spot_poll_status': 'success',
            'temperature_value_origin': 'current_observation'}))
        self.sockets = []
        self.offline = False
        self.connect_entered = threading.Event()
        self.connect_release = threading.Event()
        self.connect_release.set()
        def socket_factory(*args, **kwargs):
            self.connect_entered.set()
            if not self.connect_release.wait(30):
                raise AssertionError('test did not release socket creation')
            item = FakeSocket()
            item.fail_connect = self.offline
            self.sockets.append(item)
            return item
        # All socket creation is replaced: no real PLC/SPOT network access.
        self.socket_factory = self.stack.enter_context(patch.object(driver_module.socket, 'socket',
                                                                    side_effect=socket_factory))
        self.extra_threads = []
        self.addCleanup(self.cleanup_threads)

    def cleanup_threads(self):
        self.service.running = False
        self.service._stop_event.set()
        self.driver._worker_stop.set()
        self.connect_release.set()
        for boundary in self.devices.values():
            boundary.release.set()
        for sock in self.sockets:
            sock.fail_close = False
            sock.close_release.set()
        threads = self.owned_threads() | set(self.extra_threads)
        for boundary in self.devices.values():
            threads.update(boundary.calls)
        for thread in threads:
            if thread.ident is not None:
                thread.join(4)
            self.assertFalse(thread.is_alive(), f'leaked test thread: {thread.name}')
        self.driver.close()

    def owned_threads(self):
        return set(self.driver._worker_threads) | {
            t for t in (self.service.driver_thread, self.service.thread) if t is not None}

    def start_ready(self):
        self.service.start()
        for boundary in self.devices.values():
            self.assertTrue(boundary.entered.wait(2))
        self.assertEqual(len(self.driver._worker_threads), 3)
        self.assertTrue(all(t.is_alive() for t in self.driver._worker_threads))

    def test_normal_stop_duplicate_start_and_repeated_restart(self):
        generations = []
        for _ in range(2):
            self.start_ready()
            threads = self.owned_threads()
            generations.append(threads)
            attempts = self.socket_factory.call_count
            self.service.start()
            self.driver._start_workers()
            self.assertEqual(self.owned_threads(), threads)
            self.assertEqual(self.socket_factory.call_count, attempts)
            self.assertTrue(self.service.stop())
            self.assertTrue(all(not t.is_alive() for t in threads))
            self.assertEqual(self.driver._worker_threads, [])
            self.assertTrue(self.driver.close())
            self.assertTrue(self.service.stop())
        self.assertTrue(generations[0].isdisjoint(generations[1]))

    def test_blocked_children_preserve_ownership_and_reject_every_restart(self):
        for role in ('spot', 'ext', 'ls'):
            with self.subTest(role=role):
                boundary = self.devices[role]
                boundary.entered.clear()
                boundary.release.clear()
                self.start_ready()
                old = next(t for t in self.driver._worker_threads if t in boundary.calls and t.is_alive())
                try:
                    started = time.monotonic()
                    stopped = self.service.stop()
                    print(f'L1 blocked {role}: stop={stopped}, alive={old.is_alive()}, '
                          f'owned={old in self.driver._worker_threads}')
                    self.assertFalse(stopped)
                    self.assertLess(time.monotonic()-started, 3.5)
                    self.assertFalse(self.service.driver_thread.is_alive())
                    self.assertFalse(self.service.thread.is_alive())
                    self.assertTrue(old.is_alive())
                    self.assertIn(old, self.driver._worker_threads)
                    event = self.driver._worker_stop
                    counts = (event.clear_count, self.service._stop_event.clear_count,
                              self.socket_factory.call_count)
                    for entry in (self.service.start, self.driver.connect, self.driver._start_workers):
                        with self.assertRaises(RuntimeError):
                            entry()
                        self.assertIs(self.driver._worker_stop, event)
                        self.assertTrue(event.is_set())
                        self.assertEqual(counts, (event.clear_count, self.service._stop_event.clear_count,
                                                 self.socket_factory.call_count))
                        self.assertIn(old, self.driver._worker_threads)
                    self.assertFalse(self.service.apply_connection_config())
                    self.assertFalse(self.driver.close())
                    self.assertIn(old, self.driver._worker_threads)
                    cycles = boundary.calls[old]
                    boundary.release.set()
                    old.join(2)
                    self.assertFalse(old.is_alive())
                    self.assertEqual(boundary.calls[old], cycles)
                    self.assertEqual(self.socket_factory.call_count, counts[2])
                    self.assertFalse(self.service.running)
                    self.assertTrue(self.service.stop())
                    self.assertTrue(self.driver.close())
                    self.start_ready()
                    self.assertNotIn(old, self.driver._worker_threads)
                    self.assertEqual(boundary.calls[old], cycles)
                    self.assertTrue(self.service.stop())
                finally:
                    boundary.release.set()
                    self.service.running = False
                    self.service._stop_event.set()
                    self.driver._worker_stop.set()
                    old.join(3)
                    self.assertFalse(old.is_alive())

    def test_socket_close_failure_is_reported_and_retryable(self):
        self.devices['spot'].release.clear()
        self.start_ready()
        sock = self.sockets[0]
        sock.fail_close = True
        with self.assertLogs('SmartFactoryLoggerV2', level='WARNING'):
            self.assertFalse(self.service.stop())
        self.assertIs(self.driver.sock_ext, sock)
        self.devices['spot'].release.set()
        for worker in self.driver._worker_threads:
            worker.join(2)
        with self.assertLogs('SmartFactoryLoggerV2', level='WARNING'):
            self.assertFalse(self.service.stop())
        self.assertEqual(sock.closes, 1)
        self.assertIs(self.driver.sock_ext, sock)
        with self.assertRaises(RuntimeError):
            self.service.start()
        sock.fail_close = False
        self.assertTrue(self.service.stop())
        self.assertIsNone(self.driver.sock_ext)
        self.start_ready()
        self.assertTrue(self.service.stop())

    def test_late_worker_socket_creation_is_retained_until_reconfirmed_close(self):
        # Execute production _read_extruder -> _connect_extruder. The transport
        # socket factory pauses before publishing self.sock_ext, not the loop.
        self.connect_release.clear()
        original_read = driver_module.RealPLCDriver._read_extruder.__get__(self.driver)
        with patch.object(self.driver, '_read_extruder', original_read), \
             patch.object(self.driver, '_melsec_read', return_value=[]):
            self.driver._start_workers()
            workers = tuple(self.driver._worker_threads)
            self.assertTrue(self.connect_entered.wait(2))
            self.assertIsNone(self.driver.sock_ext)
            self.assertFalse(self.driver.close())
            old = next(t for t in workers if t.name == 'RealPLC-Extruder')
            self.assertTrue(old.is_alive())
            self.assertIn(old, self.driver._worker_threads)
            self.connect_release.set()
            old.join(2)
            self.assertFalse(old.is_alive())
            late_socket = self.driver.sock_ext
            self.assertIsNotNone(late_socket)
            self.assertEqual(late_socket.connections, 1)
            self.assertEqual(late_socket.closes, 0)
            before = self.socket_factory.call_count
            with self.assertRaises(RuntimeError):
                self.driver.connect()
            self.assertEqual(self.socket_factory.call_count, before)
            self.assertTrue(self.driver.close())
            self.assertEqual(late_socket.closes, 1)
            self.assertIsNone(self.driver.sock_ext)
            for worker in workers:
                worker.join(2)
                self.assertFalse(worker.is_alive())

    def test_concurrent_close_and_all_start_entries_are_serialized(self):
        self.start_ready()
        old = self.owned_threads()
        sock = self.sockets[0]
        sock.close_release.clear()
        results, errors = [], []
        def invoke(fn):
            try:
                results.append(fn())
            except BaseException as exc:
                errors.append(exc)
        stopper = threading.Thread(target=lambda: invoke(self.service.stop))
        self.extra_threads.append(stopper)
        stopper.start()
        self.assertTrue(sock.close_entered.wait(3))
        gates = [threading.Event() for _ in range(3)]
        entries = (self.service.start, self.driver.connect, self.driver._start_workers)
        callers = []
        for gate, entry in zip(gates, entries):
            def call(gate=gate, entry=entry):
                gate.set()
                invoke(entry)
            thread = threading.Thread(target=call)
            callers.append(thread)
            self.extra_threads.append(thread)
            thread.start()
        for gate in gates:
            self.assertTrue(gate.wait(1))
        attempts = self.socket_factory.call_count
        self.assertEqual(attempts, 2)
        sock.close_release.set()
        for thread in [stopper, *callers]:
            thread.join(4)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertIn(True, results)
        self.assertTrue(all(not t.is_alive() for t in old))
        self.assertEqual(len(self.driver._worker_threads), 3)
        self.assertEqual(len(set(self.driver._worker_threads)), 3)
        self.assertTrue(self.service.stop())

    def test_partial_driver_thread_creation_and_start_failures_keep_ownership(self):
        for fail_start in (False, True):
            with self.subTest(fail_start=fail_start):
                self.devices['ext'].entered.clear()
                self.devices['ext'].release.clear()
                made = []
                class CannotStart(threading.Thread):
                    def start(self):
                        raise RuntimeError('synthetic thread start failure')
                def factory(*args, **kwargs):
                    if made:
                        self.assertTrue(self.devices['ext'].entered.wait(2))
                        if not fail_start:
                            raise RuntimeError('synthetic thread construction failure')
                        worker = CannotStart(*args, **kwargs)
                    else:
                        worker = threading.Thread(*args, **kwargs)
                    made.append(worker)
                    self.extra_threads.append(worker)
                    return worker
                proxy = SimpleNamespace(Thread=factory, current_thread=threading.current_thread)
                with patch.object(driver_module, 'threading', proxy):
                    with self.assertRaisesRegex(RuntimeError, 'synthetic thread'):
                        self.service.start()
                self.assertFalse(self.service.running)
                self.assertTrue(made[0].is_alive())
                self.assertIn(made[0], self.driver._worker_threads)
                self.assertTrue(self.driver._worker_stop.is_set())
                with self.assertRaises(RuntimeError):
                    self.driver.connect()
                self.assertFalse(self.service.stop())
                self.devices['ext'].release.set()
                made[0].join(2)
                self.assertFalse(made[0].is_alive())
                self.assertEqual(self.devices['ext'].calls[made[0]], 1)
                self.assertTrue(self.service.stop())

    def test_direct_partial_start_requires_close_even_after_last_worker_exits(self):
        # No PLCService.start exception cleanup: exercise the driver's own gate.
        for fail_start in (False, True):
            with self.subTest(fail_start=fail_start):
                boundary = self.devices['ext']
                boundary.entered.clear()
                boundary.release.clear()
                made, factory_calls = [], []
                class CannotStart(threading.Thread):
                    def start(self):
                        raise RuntimeError('synthetic direct thread start failure')
                def factory(*args, **kwargs):
                    factory_calls.append(kwargs['name'])
                    if made:
                        self.assertTrue(boundary.entered.wait(2))
                        if not fail_start:
                            raise RuntimeError('synthetic direct thread construction failure')
                        worker = CannotStart(*args, **kwargs)
                    else:
                        worker = threading.Thread(*args, **kwargs)
                    made.append(worker)
                    self.extra_threads.append(worker)
                    return worker
                proxy = SimpleNamespace(Thread=factory, current_thread=threading.current_thread)
                try:
                    with patch.object(driver_module, 'threading', proxy):
                        with self.assertRaisesRegex(RuntimeError, 'synthetic direct thread'):
                            self.driver._start_workers()
                        old = made[0]
                        event = self.driver._worker_stop
                        self.assertTrue(old.is_alive())
                        self.assertIn(old, self.driver._worker_threads)
                        self.assertTrue(event.is_set())
                        self.assertFalse(self.driver.connected)
                        self.assertFalse(self.service.running)
                        before = (event.clear_count, self.service._stop_event.clear_count,
                                  self.socket_factory.call_count, len(factory_calls))
                        for released in (False, True):
                            if released:
                                boundary.release.set()
                                old.join(2)
                                self.assertFalse(old.is_alive())
                            # Alive and later dead must both stay blocked until
                            # explicit close confirms failed-start cleanup.
                            for entry in (self.driver.connect, self.driver._start_workers):
                                with self.assertRaises(RuntimeError):
                                    entry()
                                self.assertIs(self.driver._worker_stop, event)
                                self.assertTrue(event.is_set())
                                self.assertEqual(before, (event.clear_count,
                                    self.service._stop_event.clear_count,
                                    self.socket_factory.call_count, len(factory_calls)))
                            if not released:
                                self.assertIn(old, self.driver._worker_threads)
                        self.assertEqual(boundary.calls[old], 1)
                        print(f'L1 direct partial start: fail_start={fail_start}, '
                              f'old_alive={old.is_alive()}, old_cycles={boundary.calls[old]}, '
                              'restart_blocked_before_close=True')
                    self.assertTrue(self.driver.close())
                    self.assertTrue(self.service.stop())
                    self.assertEqual(self.driver._worker_threads, [])
                    for worker in made:
                        self.assertFalse(worker.is_alive())
                    boundary.entered.clear()
                    self.start_ready()
                    self.assertTrue(set(made).isdisjoint(self.driver._worker_threads))
                    self.assertEqual(boundary.calls[old], 1)
                    self.assertTrue(self.service.stop())
                finally:
                    boundary.release.set()
                    self.driver._worker_stop.set()
                    for worker in made:
                        if worker.ident is not None:
                            worker.join(3)
                        self.assertFalse(worker.is_alive())

    def test_start_in_progress_and_concurrent_stop_finish_without_orphans(self):
        self.connect_release.clear()
        results, errors = [], []
        def invoke(fn):
            try:
                results.append(fn())
            except BaseException as exc:
                errors.append(exc)
        starter = threading.Thread(target=lambda: invoke(self.service.start))
        stop_entered = threading.Event()
        def stop():
            stop_entered.set()
            invoke(self.service.stop)
        stopper = threading.Thread(target=stop)
        self.extra_threads.extend((starter, stopper))
        starter.start()
        self.assertTrue(self.connect_entered.wait(2))
        stopper.start()
        self.assertTrue(stop_entered.wait(1))
        self.assertEqual(self.driver._worker_stop.clear_count, 0)
        self.assertEqual(self.service._stop_event.clear_count, 0)
        self.connect_release.set()
        for thread in (starter, stopper):
            thread.join(4)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertIn(True, results)
        self.assertFalse(self.service.running)
        self.assertEqual(self.driver._worker_threads, [])
        self.assertTrue(all(not t.is_alive() for t in self.owned_threads()))
        self.assertEqual(self.socket_factory.call_count, 2)

    def test_partial_service_start_failure_keeps_blocked_producer_owned(self):
        entered, release = threading.Event(), threading.Event()
        original_read = self.driver._read_cached_snapshot_with_metadata
        def read_boundary():
            entered.set()
            if not release.wait(30):
                raise AssertionError('test did not release integrated snapshot read')
            return original_read()
        made = []
        def factory(*args, **kwargs):
            if made:
                self.assertTrue(entered.wait(2))
                raise RuntimeError('synthetic service thread construction failure')
            worker = threading.Thread(*args, **kwargs)
            made.append(worker)
            self.extra_threads.append(worker)
            return worker
        proxy = SimpleNamespace(Thread=factory, current_thread=threading.current_thread)
        try:
            with patch.object(self.driver, '_read_cached_snapshot_with_metadata', side_effect=read_boundary), \
                 patch.object(service_module, 'threading', proxy):
                with self.assertRaisesRegex(RuntimeError, 'synthetic service thread'):
                    self.service.start()
                self.assertFalse(self.service.running)
                self.assertTrue(self.service._stop_event.is_set())
                self.assertIs(self.service.driver_thread, made[0])
                self.assertTrue(made[0].is_alive())
                self.assertFalse(self.service.stop())
                before = self.socket_factory.call_count
                with self.assertRaises(RuntimeError):
                    self.service.start()
                self.assertEqual(self.socket_factory.call_count, before)
                release.set()
                made[0].join(2)
                self.assertFalse(made[0].is_alive())
            self.assertTrue(self.service.stop())
            self.start_ready()
            self.assertTrue(self.service.stop())
        finally:
            release.set()
            for worker in made:
                worker.join(3)
                self.assertFalse(worker.is_alive())

    def test_offline_connect_false_still_starts_existing_retry_workers(self):
        self.offline = True
        self.start_ready()
        self.assertTrue(self.service.running)
        self.assertEqual(self.driver.ext_connect_failures, 1)
        self.assertEqual(self.driver.ls_connect_failures, 1)
        self.assertTrue(self.service.stop())

    def test_reconnect_api_preserves_failed_stop_and_separate_shutdown_owners(self):
        self.devices['spot'].release.clear()
        self.start_ready()
        workers = tuple(self.driver._worker_threads)
        attempts = self.socket_factory.call_count
        with patch.object(backend_app, 'plc_service', self.service):
            with self.assertRaises(backend_app.HTTPException) as raised:
                backend_app.reconnect()
            self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(self.socket_factory.call_count, attempts)
        self.assertTrue(self.driver._worker_stop.is_set())
        self.assertTrue(any(t.is_alive() for t in workers))
        status = {'spot_poll_loop_stopped': False, 'spot_observation_fact_drained': False}
        self.assertFalse(backend_app._run_control_shutdown_stage(
            stage='plc_service', status_key='plc_service_stopped',
            stopper=self.service.stop, status=status))
        self.assertFalse(status['plc_service_stopped'])
        self.assertFalse(status['spot_poll_loop_stopped'])
        self.assertFalse(status['spot_observation_fact_drained'])
        self.devices['spot'].release.set()
        for worker in workers:
            worker.join(2)
        self.assertTrue(self.service.stop())
        # Other shutdown owners retain their own completion checks. This test
        # exercises only the synchronous reconnect route; closeout suites cover
        # the independent HTTP/fact/image shutdown orchestration.

    def test_config_apply_waits_for_service_stop_and_rejects_lingering_read(self):
        entered, release = threading.Event(), threading.Event()
        original = self.driver._read_cached_snapshot_with_metadata
        def read_boundary():
            entered.set()
            if not release.wait(30):
                raise AssertionError('test did not release snapshot adoption')
            return original()
        results = {}
        callers = []
        try:
            with patch.object(self.driver, '_read_cached_snapshot_with_metadata', side_effect=read_boundary):
                self.start_ready()
                self.assertTrue(entered.wait(2))
                stopper = threading.Thread(target=lambda: results.update(stop=self.service.stop()))
                callers.append(stopper)
                self.extra_threads.append(stopper)
                stopper.start()
                self.assertTrue(self.service._stop_event.was_set.wait(1))
                apply_entered = threading.Event()
                def apply():
                    apply_entered.set()
                    results['apply'] = self.service.apply_connection_config()
                applier = threading.Thread(target=apply)
                callers.append(applier)
                self.extra_threads.append(applier)
                applier.start()
                self.assertTrue(apply_entered.wait(1))
                for caller in callers:
                    caller.join(4)
                    self.assertFalse(caller.is_alive())
                self.assertEqual(results, {'stop': False, 'apply': False})
                self.assertEqual([s.closes for s in self.sockets], [1, 1])
                self.assertTrue(self.service.driver_thread.is_alive())
                release.set()
                self.service.driver_thread.join(2)
                self.assertTrue(self.service.stop())
        finally:
            release.set()
            for caller in callers:
                caller.join(4)
                self.assertFalse(caller.is_alive())

    def test_mock_and_csv_replay_have_explicit_close_contract(self):
        csv = self.root/'input.csv'
        csv.write_text('Time,Count,Speed,Press\n2026-09-21T00:00:00,0,0,0\n', encoding='utf-8')
        for driver in (MockPLCDriver(), CsvReplayDriver(str(csv))):
            with self.subTest(driver=type(driver).__name__):
                self.service.driver = driver
                self.service.start()
                threads = {self.service.thread, self.service.driver_thread}
                self.assertTrue(self.service.stop())
                self.assertTrue(all(not t.is_alive() for t in threads))
                self.assertTrue(driver.close())
                self.assertFalse(driver.connected)


if __name__ == '__main__':
    unittest.main()
