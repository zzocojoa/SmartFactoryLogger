"""P2: production history/API paths with independent clocks and temporary state."""
import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import threading
import unittest

from fastapi.testclient import TestClient
import httpx
from backend import app as api
from backend.FacilityData import service as module
from backend.FacilityData.schemas import FactoryData, FactoryDataHistorySample
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

    def test_nested_snapshot_preserves_public_values_and_isolates_each_reader(self):
        original = FactoryData(
            Time='source-time', Count=1, Spot=500,
            operator_metadata_missing_fields=['Mold_No_operator'],
            diagnostics_missing_fields=['signalpc'],
            diagnostics_field_status={'signalpc': 'unknown'},
            Computed={'pressure': {'codes': ['first'], 'value': 162.5}},
            plc_source_completed_monotonic=90.0, plc_clock_domain_id='private-clock',
        )
        # Published observations may have updates after their initial validation.
        original.Speed = -1.0
        published = self.service._record_history_sample(original, self.wall)
        expected = json.loads(FactoryDataHistorySample(
            timestamp_ms=int(self.wall * 1000), sequence=1, data=published,
        ).model_dump_json())
        original.Computed['pressure']['codes'].append('original-mutation')
        published.diagnostics_missing_fields.append('published-mutation')
        published.diagnostics_field_status['signalpc'] = 'changed'
        self.assertEqual(self.query()['samples'], [expected])
        self.assertEqual(published.plc_source_completed_monotonic, 90.0)
        self.assertEqual(published.plc_clock_domain_id, 'private-clock')
        self.assertNotIn('plc_source_completed_monotonic', expected['data'])
        self.assertNotIn('plc_clock_domain_id', expected['data'])
        response = self.service.get_data_history(0, 10)
        response.samples[0].data.Computed['pressure']['codes'].append('reader-mutation')
        response.samples[0].data.operator_metadata_missing_fields.clear()
        self.assertEqual(self.query()['samples'], [expected])

    def test_decode_does_not_block_recording_and_keeps_response_generation_consistent(self):
        self.record(1)
        old_instance = self.service.history_instance_id
        entered, release = threading.Event(), threading.Event()
        decode = module._StoredHistorySample.to_sample

        def delayed_decode(row):
            entered.set()
            if not release.wait(5):
                raise TimeoutError('test decoder not released')
            return decode(row)

        def replace_history():
            self.service.clear_data_history()
            self.record(2)

        with patch.object(module._StoredHistorySample, 'to_sample', delayed_decode):
            with ThreadPoolExecutor(max_workers=2) as workers:
                future = workers.submit(self.service.get_data_history, 0, 10)
                try:
                    self.assertTrue(entered.wait(5))
                    workers.submit(replace_history).result(timeout=2)
                finally:
                    release.set()
                response = future.result(timeout=5)
        self.assertEqual(response.history_instance_id, old_instance)
        self.assertEqual(response.next_cursor, f'{old_instance}:1')
        self.assertEqual([s.data.Count for s in response.samples], [1])
        self.assertEqual(response.samples[0].data.history_instance_id, old_instance)
        current = self.query()
        self.assertNotEqual(current['history_instance_id'], old_instance)
        self.assertEqual([s['data']['Count'] for s in current['samples']], [2])

    def test_http_json_matches_model_bytes_for_pages_and_escaped_nested_values(self):
        self.service._record_history_sample(FactoryData(
            Time='한글 "line"\n\\', Count=1,
            Computed={'message': '한글\n"quoted"\\', 'nested': [None, True, {'x': '<>&'}]},
        ), self.wall)
        self.record(2, self.wall - 10)
        for since, limit, cursor in (
            (0, 36000, None), (0, 1, None), (int(self.wall * 1000) + 100000, 5, None),
            (0, 1, f'{self.service.history_instance_id}:0'),
            (0, 5, f'{self.service.history_instance_id}:999'),
        ):
            with self.subTest(since=since, limit=limit, cursor=cursor):
                expected = self.service.get_data_history(since, limit, cursor).model_dump_json().encode('utf-8')
                params = {'since_ms': since, 'limit': limit}
                if cursor is not None:
                    params['cursor'] = cursor
                response = self.client.get('/api/data/history', params=params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['content-type'], 'application/json')
                self.assertEqual(response.content, expected)

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
        envelopes = [harness.logger.queue.get_nowait() for _ in range(harness.logger.queue.qsize())]
        self.assertEqual([item.producer_seq for item in envelopes], [1, 2, 3, 4])
        rows = [FactoryData.model_validate_json(item.payload) for item in envelopes]
        self.assertEqual([r.Count for r in rows], [1, 2, 3, 4])
        self.assertTrue(all(r.history_sequence is None for r in rows))


class HistoryEndpointConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_waiting_history_worker_does_not_block_same_loop_health(self):
        entered, release = threading.Event(), threading.Event()
        loop_tid = threading.get_native_id()
        worker_tids = []
        body = b'{"samples":[]}'

        def delayed_history(*args):
            worker_tids.append(threading.get_native_id())
            entered.set()
            if not release.wait(5):
                raise TimeoutError('history worker not released')
            return body

        with patch.object(api.plc_service, 'get_data_history_json', side_effect=delayed_history), \
                patch.object(api, 'build_health_payload', return_value={'running': True}):
            transport = httpx.ASGITransport(app=api.app)
            async with httpx.AsyncClient(transport=transport, base_url='http://localhost') as client:
                history = asyncio.create_task(client.get('/api/data/history?since_ms=0'))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                    health = await asyncio.wait_for(client.get('/health'), timeout=2)
                    self.assertEqual(health.status_code, 200)
                    self.assertTrue(health.json()['running'])
                    self.assertFalse(history.done())
                    self.assertNotEqual(worker_tids, [loop_tid])
                finally:
                    release.set()
                    result = await asyncio.wait_for(history, timeout=5)
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.content, body)
