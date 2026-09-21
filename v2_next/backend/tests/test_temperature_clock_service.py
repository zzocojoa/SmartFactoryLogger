"""C1: run the real service producer/consumer loops with isolated I/O and clocks."""
import os
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.FacilityData import service as module
from backend.FacilityData.operator_metadata import OperatorMetadataStore
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData.schemas import FactoryData


class LoopBoundary(BaseException):
    pass


class IndependentClock:
    def __init__(self):
        self.wall = 1_800_000_000.0
        self.mono = 1000.0

    def time(self):
        return self.wall

    def monotonic(self):
        return self.mono

    def advance(self, elapsed, jump=0):
        self.mono += elapsed
        self.wall += elapsed + jump


class ObservedStop:
    def __init__(self):
        self.event = threading.Event()
        self.driver_wait = threading.Event()
        self.consumer_wait = threading.Event()
        self.waits = []

    def clear(self):
        self.event.clear()
        self.driver_wait.clear()
        self.consumer_wait.clear()

    def set(self):
        self.event.set()

    def is_set(self):
        return self.event.is_set()

    def wait(self, timeout):
        if '_driver_loop' in threading.current_thread().name:
            self.waits.append(timeout)
            self.driver_wait.set()
        else:
            self.consumer_wait.set()
        return self.event.wait(timeout)


class ServiceClockTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.dict(os.environ, {'V2_MODE': 'MOCK'}))
        self.stack.enter_context(patch.object(module.config, 'APP_DATA_DIR', self.root))
        self.stack.enter_context(patch.object(module, 'operator_metadata_store', OperatorMetadataStore(self.root/'metadata.json')))
        self.service = module.PLCService(operator_metadata_runtime_state_path=self.root/'runtime.json')
        self.logger = CSVLoggerService()
        self.logger.apply_config(log_path=self.root)
        self.logger.running = True  # Observe the real enqueue without starting disk I/O.
        self.stack.enter_context(patch.object(module, 'logger_service', self.logger))

    def produce(self, jumps, *, elapsed=.01, consume=False, failed_reads=()):
        clock = IndependentClock()
        starts, waits, stamps = [], [], []
        count = 0
        self.service.interval_sec = .2
        stop = ObservedStop()
        self.service._stop_event = stop

        def read():
            nonlocal count
            starts.append(clock.mono)
            clock.advance(elapsed, jumps[count])
            count += 1
            if count in failed_reads:
                raise OSError('synthetic read failure')
            stamps.append(clock.wall)
            return FactoryData(Time=str(clock.wall), Count=count, Speed=1, Press=30, Spot=500)

        def boundary(_):
            raise LoopBoundary()

        def wait(timeout):
            waits.append(timeout)
            if consume:
                # Only the wait boundary is replaced. Both loop bodies and enqueue run.
                with patch.object(stop, 'wait', side_effect=boundary), patch.object(fake_time, 'sleep', side_effect=boundary):
                    try:
                        self.service._loop()
                    except LoopBoundary:
                        pass
            clock.advance(timeout)
            if count >= len(jumps):
                self.service.running = False
            return False

        fake_time = SimpleNamespace(time=clock.time, monotonic=clock.monotonic, sleep=wait)
        self.service.driver = SimpleNamespace(read_data=read)
        self.service.running = True
        with patch.object(module, 'time', fake_time), patch.object(stop, 'wait', side_effect=wait):
            self.service._driver_loop()
        return starts, waits, stamps

    def test_real_driver_loop_normal_wall_backward_forward_and_repeated(self):
        for jumps in [[0]*4, [-60]*4, [60]*4, [-60, 60, -60, 60]]:
            with self.subTest(jumps=jumps):
                starts, waits, _ = self.produce(jumps)
                self.assertEqual(len(starts), 4)
                for value in waits:
                    self.assertAlmostEqual(value, .19, places=6)
                for first, second in zip(starts, starts[1:]):
                    self.assertAlmostEqual(second-first, .2, places=6)

    def test_actual_consumer_enqueues_new_samples_with_equal_and_reversed_utc(self):
        # read advances .01 but wall resets by -.21 from the previous .2 cycle.
        # Equal public UTC must not mean the new acquisition is the old sample.
        _, _, stamps = self.produce([0, -.2, -60, 60], consume=True)
        rows = [self.logger.queue.get_nowait() for _ in range(self.logger.queue.qsize())]
        self.assertEqual([row.Count for row in rows], [1, 2, 3, 4])
        self.assertEqual([row.Time for row in rows], [str(value) for value in stamps])
        self.assertEqual(self.service.last_update, stamps[-1])

    def test_overrun_preserves_existing_zero_wait_policy(self):
        for elapsed in [.2, .5]:
            with self.subTest(elapsed=elapsed):
                starts, waits, _ = self.produce([-60, 60, -60], elapsed=elapsed)
                for value in waits:
                    self.assertAlmostEqual(value, 0, places=6)
                for first, second in zip(starts, starts[1:]):
                    self.assertAlmostEqual(second-first, elapsed, places=6)

    def test_exception_retry_one_second_then_recovers_into_enqueue(self):
        starts, waits, _ = self.produce([-60, 60, 0], consume=True, failed_reads=(1,))
        self.assertEqual(waits[0], 1.0)
        self.assertAlmostEqual(starts[1]-starts[0], 1.01, places=6)
        self.assertAlmostEqual(waits[1], .19, places=6)
        self.assertEqual([self.logger.queue.get_nowait().Count for _ in range(self.logger.queue.qsize())], [2, 3])
        self.assertIsNone(self.service.driver_last_error)

    def test_stop_interrupts_normal_and_retry_wait_and_restart(self):
        for error in [False, True]:
            with self.subTest(error=error):
                stop = ObservedStop()
                self.service._stop_event = stop
                calls = []
                def read():
                    calls.append('read')
                    if error:
                        raise OSError('synthetic read failure')
                    return FactoryData(Time='', Count=20, Speed=1, Press=30)
                self.service.driver = SimpleNamespace(read_data=read, connect=lambda: True, close=lambda: True)
                self.service.interval_sec = 5
                fake_time = SimpleNamespace(time=time.time, monotonic=time.monotonic, sleep=stop.wait)
                with patch.object(module, 'time', fake_time):
                    try:
                        for _ in range(2):
                            before = len(calls)
                            self.service.start()
                            original_thread = self.service.driver_thread
                            self.service.start()
                            self.assertIs(self.service.driver_thread, original_thread)
                            self.assertTrue(stop.driver_wait.wait(1))
                            if error:
                                self.assertIsNotNone(self.service.driver_last_error)
                                self.assertEqual(stop.waits[-1], 1.0)
                            else:
                                self.assertIsNone(self.service.driver_last_error)
                                self.assertGreater(stop.waits[-1], 4.5)
                                self.assertLessEqual(stop.waits[-1], 5.0)
                            started = time.monotonic()
                            self.assertTrue(self.service.stop())
                            self.assertLess(time.monotonic()-started, .5)
                            self.assertGreater(len(calls), before)
                            self.assertFalse(original_thread.is_alive())
                    finally:
                        self.service.running = False
                        stop.set()
                        for worker in [self.service.thread, self.service.driver_thread]:
                            if worker:
                                worker.join(2)

    def test_blocked_io_reports_stop_failure_and_prevents_duplicate_restart(self):
        entered, release = threading.Event(), threading.Event()
        def read():
            entered.set()
            release.wait(5)
            return FactoryData(Time='', Count=20, Speed=1, Press=30)
        self.service.driver = SimpleNamespace(read_data=read, connect=lambda: True, close=lambda: True)
        self.service.start()
        try:
            self.assertTrue(entered.wait(1))
            original_thread = self.service.driver_thread
            self.assertFalse(self.service.stop())
            with self.assertRaises(RuntimeError):
                self.service.start()
            self.assertIs(self.service.driver_thread, original_thread)
        finally:
            self.service.running = False
            release.set()
            for worker in [self.service.thread, self.service.driver_thread]:
                if worker:
                    worker.join(2)

    def test_stop_interrupts_consumer_retry_wait(self):
        stop = ObservedStop()
        self.service._stop_event = stop
        self.service.interval_sec = 5
        self.service.driver = SimpleNamespace(read_data=lambda: FactoryData(Time='', Count=20, Speed=1, Press=30),
                                             connect=lambda: True, close=lambda: True)
        enqueue_attempted = threading.Event()
        def fail_enqueue(data):
            enqueue_attempted.set()
            raise OSError('synthetic queue failure')
        with patch.object(self.logger, 'enqueue', side_effect=fail_enqueue):
            self.service.start()
            try:
                self.assertTrue(enqueue_attempted.wait(1))
                self.assertTrue(stop.consumer_wait.wait(1))
                started = time.monotonic()
                self.assertTrue(self.service.stop())
                self.assertLess(time.monotonic()-started, .5)
            finally:
                self.service.running = False
                stop.set()
                for worker in [self.service.thread, self.service.driver_thread]:
                    if worker:
                        worker.join(2)
