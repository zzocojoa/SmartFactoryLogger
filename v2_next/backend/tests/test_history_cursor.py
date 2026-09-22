"""P2: production history/API paths with independent clocks and temporary state."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import threading
import unittest

from fastapi.testclient import TestClient
from backend import app as api
from backend.FacilityData import service as module
from backend.FacilityData.schemas import FactoryData
from backend.tests import test_temperature_clock_service as clock_suite


class HistoryCursorTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.wall, self.mono = 1_800_000_000.0, 1000.0
        clock = SimpleNamespace(time=lambda: self.wall, monotonic=lambda: self.mono)
        self.stack.enter_context(patch.object(module, 'time', clock))
        self.service = module.PLCService(operator_metadata_runtime_state_path=root/'runtime.json')
        self.stack.enter_context(patch.object(api, 'plc_service', self.service))
        self.client = TestClient(api.app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def record(self, count, wall=None):
        if wall is not None:
            self.wall = wall
        self.mono += .1
        return self.service._record_history_sample(
            FactoryData(Time=f'original-utc-{count}', Count=count, Spot=500), self.wall)

    def query(self, cursor=None, **params):
        params.setdefault('since_ms', 0)
        if cursor is not None:
            params['cursor'] = cursor
        response = self.client.get('/api/data/history', params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_equal_utc_retains_distinct_acquisitions(self):
        self.record(1)
        self.record(2)
        rows = self.query()['samples']
        self.assertEqual([r['data']['Count'] for r in rows], [1, 2])
        self.assertEqual(rows[0]['timestamp_ms'], rows[1]['timestamp_ms'])
        self.assertEqual([r['sequence'] for r in rows], [1, 2])
        self.assertEqual([r['data']['Time'] for r in rows], ['original-utc-1', 'original-utc-2'])

    def test_cursor_finds_new_sample_after_wall_clock_reversal(self):
        self.record(1)
        previous_ms = int(self.wall * 1000)
        self.record(2, self.wall - 60)
        payload = self.query(f'{self.service.history_instance_id}:1', since_ms=previous_ms)
        self.assertEqual([r['data']['Count'] for r in payload['samples']], [2])
        self.assertEqual(payload['samples'][0]['timestamp_ms'], previous_ms - 60_000)
        self.assertFalse(payload['reset_required'])

    def test_retention_uses_elapsed_time_and_preserves_exact_boundary(self):
        self.record(1)
        recorded = self.mono
        self.wall += 7200
        self.assertEqual(len(self.query()['samples']), 1)
        self.wall -= 14_400
        self.mono = recorded + 3600
        self.assertEqual(len(self.query()['samples']), 1)
        self.mono += .001
        payload = self.query(f'{self.service.history_instance_id}:0')
        self.assertEqual(payload['samples'], [])
        self.assertTrue(payload['reset_required'])
        self.assertEqual(payload['next_cursor'], f'{self.service.history_instance_id}:1')

    def test_cursor_pages_in_acquisition_order_and_retries_are_idempotent(self):
        for count, offset in enumerate([0, 0, -60, 60, -120], 1):
            self.record(count, 1_800_000_000 + offset)
        cursor = f'{self.service.history_instance_id}:0'
        seen = []
        for _ in range(3):
            page = self.query(cursor, limit=2)
            self.assertEqual(self.query(cursor, limit=2), page)
            seen.extend(r['sequence'] for r in page['samples'])
            cursor = page['next_cursor']
        self.assertEqual(seen, [1, 2, 3, 4, 5])
        self.assertFalse(page['has_more'])
        self.assertEqual(self.query(cursor)['samples'], [])
        self.assertEqual(self.query()['oldest_timestamp_ms'], 1_799_999_880_000)
        self.assertEqual(self.query()['newest_timestamp_ms'], 1_800_000_060_000)

    def test_count_eviction_reports_gap_and_resync_pages_from_oldest_retained(self):
        self.service.history = deque(maxlen=3)
        cursor = f'{self.service.history_instance_id}:1'
        for count in range(1, 6):
            self.record(count)
        first = self.query(cursor, limit=2)
        self.assertTrue(first['reset_required'])
        self.assertTrue(first['truncated'])
        self.assertTrue(first['has_more'])
        self.assertEqual([r['sequence'] for r in first['samples']], [3, 4])
        second = self.query(first['next_cursor'], limit=2)
        self.assertFalse(second['reset_required'])
        self.assertEqual([r['sequence'] for r in second['samples']], [5])

    def test_instance_reset_and_future_sequence_require_resync(self):
        self.record(1)
        cursor = self.query()['next_cursor']
        self.service.clear_data_history()
        empty = self.query(cursor)
        self.assertTrue(empty['reset_required'])
        self.assertEqual(empty['samples'], [])
        self.record(2)
        for stale in [cursor, f'{self.service.history_instance_id}:999']:
            response = self.query(stale)
            self.assertTrue(response['reset_required'])
            self.assertEqual([r['sequence'] for r in response['samples']], [1])
            self.assertEqual(response['samples'][0]['data']['history_instance_id'], response['history_instance_id'])

    def test_legacy_since_ms_keeps_utc_filter_and_latest_limit(self):
        for count in range(1, 5):
            self.record(count, 1_800_000_000 + count)
        response = self.query(since_ms=1_800_000_001_000, limit=2)
        self.assertEqual([r['data']['Count'] for r in response['samples']], [3, 4])
        self.assertTrue(response['truncated'])  # limit omission is explicit
        self.assertFalse(response['has_more'])  # legacy mode remains latest-tail, not cursor pagination
        self.assertFalse(response['reset_required'])
        self.assertEqual(response['next_cursor'], f'{self.service.history_instance_id}:4')

    def test_bad_cursor_and_limit_rejected_without_mutation(self):
        self.record(1)
        before = self.query()
        for cursor in ['', 'bad', '../:1', f'{self.service.history_instance_id}:-1',
                       f'{self.service.history_instance_id}:9007199254740992']:
            with self.subTest(cursor=cursor):
                self.assertEqual(self.client.get('/api/data/history', params={'since_ms': 0, 'cursor': cursor}).status_code, 422)
        for limit in [0, 36001]:
            self.assertEqual(self.client.get('/api/data/history', params={'since_ms': 0, 'limit': limit}).status_code, 422)
        self.assertEqual(self.query(), before)

    def test_history_copy_cannot_be_changed_by_original_sample(self):
        original = FactoryData(Time='original', Count=1, Spot=500)
        published = self.service._record_history_sample(original, self.wall)
        original.Count = 2
        published.Count = 3
        self.assertEqual(self.query()['samples'][0]['data']['Count'], 1)
        self.assertNotIn('_recorded_monotonic', self.query()['samples'][0])

    def test_concurrent_recorders_assign_unique_ordered_sequences(self):
        release = threading.Event()
        def write(count):
            if not release.wait(5):
                raise TimeoutError('synthetic recorder gate not released')
            return self.service._record_history_sample(FactoryData(Time='same-utc', Count=count), self.wall)
        with ThreadPoolExecutor(max_workers=4) as workers:
            try:
                futures = [workers.submit(write, n) for n in range(40)]
                release.set()
                published = [f.result(timeout=5) for f in futures]
            finally:
                release.set()
        response = self.query(f'{self.service.history_instance_id}:0')
        self.assertEqual([r['sequence'] for r in response['samples']], list(range(1, 41)))
        self.assertEqual(sorted(x.history_sequence for x in published), list(range(1, 41)))
        self.assertEqual(sorted(r['data']['Count'] for r in response['samples']), list(range(40)))

    def test_new_service_instance_resynchronizes_old_cursor(self):
        self.record(1)
        previous = self.query()['next_cursor']
        with tempfile.TemporaryDirectory() as tmp:
            replacement = module.PLCService(operator_metadata_runtime_state_path=Path(tmp)/'runtime.json')
            replacement._record_history_sample(FactoryData(Time='restart', Count=2), self.wall)
            with patch.object(api, 'plc_service', replacement):
                response = self.query(previous)
        self.assertTrue(response['reset_required'])
        self.assertNotEqual(response['history_instance_id'], self.service.history_instance_id)
        self.assertEqual([r['data']['Count'] for r in response['samples']], [2])

    def test_real_producer_consumer_latest_and_history_share_identity_without_changing_csv(self):
        harness = clock_suite.ServiceClockTests()
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        _, _, stamps = harness.produce([0, -.2, -60, 60], consume=True)
        with patch.object(api, 'plc_service', harness.service):
            history = self.query(f'{harness.service.history_instance_id}:0')
            latest = self.client.get('/api/data').json()
        self.assertEqual([r['data']['Count'] for r in history['samples']], [1, 2, 3, 4])
        self.assertEqual([r['timestamp_ms'] for r in history['samples']], [int(t*1000) for t in stamps])
        self.assertEqual(latest['history_sequence'], 4)
        self.assertEqual(latest['history_instance_id'], history['history_instance_id'])
        rows = [harness.logger.queue.get_nowait() for _ in range(harness.logger.queue.qsize())]
        self.assertEqual([r.Count for r in rows], [1, 2, 3, 4])
        self.assertTrue(all(r.history_sequence is None for r in rows))
