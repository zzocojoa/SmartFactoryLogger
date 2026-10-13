"""Resource contract faults plus actual Windows counters and shared HTTP origin."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import ctypes
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

import psutil

import field_http_sampling as http
import field_resource_sampling as resource
from test_field_http_sampling import local_server


ROOT = Path(os.environ['SFL_RESOURCE_TEST_ROOT'])


def fixture_row(sequence=0):
    started = 1_000_000_000 + sequence * 5_000_000_000
    process = dict(pid=12, created=123.0, exe='C:\\fixture.exe', started_ns=started,
                   finished_ns=started + 1_000_000, rss_bytes=100, vms_bytes=200, threads=2, handles=3,
                   cpu_user_seconds=sequence * .5, cpu_system_seconds=sequence * .5,
                   io_read_bytes=sequence * 100, io_write_bytes=sequence * 200)
    disk = dict(name='PhysicalDrive0', storage_device_number=0, storage_manager='PARTMGR',
                started_ns=started + 1_000_000, finished_ns=started + 2_000_000,
                read_bytes=sequence * 1000, write_bytes=sequence * 2000,
                read_time_100ns=sequence * 100_000, write_time_100ns=sequence * 200_000,
                idle_time_100ns=sequence * 10_000_000, read_count=sequence * 5,
                write_count=sequence * 10, queue_depth=1, split_count=sequence,
                query_time_100ns_since_1601=1000 + sequence)
    process['exe'] = os.path.normcase(process['exe'])
    return dict(kind='sample', sequence=sequence, scheduled_ns=started, started_ns=started,
                finished_ns=started + 2_000_000,
                process=dict(root=dict(pid=12, created=123.0, exe=process['exe']),
                             records=[process], errors=[]),
                disk=dict(names=['PhysicalDrive0'], records=[disk], errors=[]))


def verify_manifest(path):
    manifest = json.loads((path / 'manifest.json').read_text())
    assert set(manifest['files']) == {p.name for p in path.iterdir()} - {'manifest.json'}
    for name, item in manifest['files'].items():
        raw = (path / name).read_bytes()
        assert len(raw) == item['bytes']
        assert hashlib.sha256(raw).hexdigest() == item['sha256']


class ResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.output = ROOT / self._testMethodName

    def review(self, rows, duration=420):
        return resource.summarize_resources(rows, origin_ns=1_000_000_000,
                                            duration_seconds=duration, logical_cpus=4)

    def test_native_structure_offsets(self):
        self.assertEqual(ctypes.sizeof(resource.DiskPerformance), 88)
        expected = dict(BytesRead=0, BytesWritten=8, ReadTime=16, WriteTime=24, IdleTime=32,
                        ReadCount=40, WriteCount=44, QueueDepth=48, SplitCount=52,
                        QueryTime=56, StorageDeviceNumber=64, StorageManagerName=68)
        self.assertEqual({key: getattr(resource.DiskPerformance, key).offset for key in expected}, expected)

    def test_real_disk_bytes_and_psutil_time_scale(self):
        reader = resource.WindowsDiskReader()
        before = psutil.disk_io_counters(perdisk=True, nowrap=False)
        raw = reader.snapshot()
        after = psutil.disk_io_counters(perdisk=True, nowrap=False)
        self.assertFalse(raw['errors'])
        self.assertTrue(raw['records'])
        for row in raw['records']:
            name = row['name']
            native = resource.DiskPerformance.from_buffer_copy(bytes.fromhex(row['raw_hex']))
            self.assertEqual(native.ReadTime, row['read_time_100ns'])
            for key in ('read_bytes', 'write_bytes', 'read_count', 'write_count'):
                self.assertLessEqual(getattr(before[name], key), row[key])
                self.assertLessEqual(row[key], getattr(after[name], key))
            # The exact installed 7.2.2 Windows implementation truncates to seconds.
            self.assertEqual(psutil.__version__, '7.2.2')
            for key in ('read_time', 'write_time'):
                self.assertLessEqual(getattr(before[name], key), row[key + '_100ns'] // 10_000_000)
                self.assertLessEqual(row[key + '_100ns'] // 10_000_000, getattr(after[name], key))
        self.output.with_suffix('.json').write_text(json.dumps({
            'native': raw, 'psutil_before': {k: v._asdict() for k, v in before.items()},
            'psutil_after': {k: v._asdict() for k, v in after.items()}}, indent=2))

    def test_disk_names_do_not_accept_arbitrary_paths(self):
        with self.assertRaises(ValueError):
            resource.WindowsDiskReader().read('C:\\')

    def test_disk_failure_preserved(self):
        with patch.object(resource.WindowsDiskReader, 'names', return_value=['PhysicalDrive0']), \
                patch.object(resource.WindowsDiskReader, 'read', side_effect=PermissionError('fixture denied')):
            value = resource.WindowsDiskReader().snapshot()
        self.assertEqual(value['errors'][0]['type'], 'PermissionError')
        self.assertEqual(value['names'], ['PhysicalDrive0'])
        self.assertFalse(value['records'])

    def test_empty_and_changed_disk_topology(self):
        for names in (([],), (['PhysicalDrive0'], ['PhysicalDrive0', 'PhysicalDrive1'])):
            with self.subTest(names=names), patch.object(resource.WindowsDiskReader, 'names', side_effect=names), \
                    patch.object(resource.WindowsDiskReader, 'read', return_value=fixture_row()['disk']['records'][0]):
                self.assertTrue(resource.WindowsDiskReader().snapshot()['errors'])

    def test_root_identity_mismatch_and_process_gone(self):
        identity = resource.ProcessIdentity.read(os.getpid())
        wrong = replace(identity, created=identity.created + 1)
        self.assertTrue(resource.process_snapshot(wrong)['errors'])
        with patch.object(resource.ProcessIdentity, 'read', side_effect=psutil.NoSuchProcess(identity.pid)):
            self.assertTrue(resource.process_snapshot(identity)['errors'])

    def test_actual_owned_child_tree_and_normal_exit(self):
        code = ('import subprocess,sys,json; '
                'p=subprocess.Popen([sys.executable,"-c","import os,sys; print(os.getpid(),flush=True); sys.stdin.readline()"],'
                'stdin=subprocess.PIPE,stdout=subprocess.PIPE); '
                'ready=int(p.stdout.readline()); print(json.dumps({"child":p.pid,"child_runtime":ready}),flush=True); sys.stdin.readline(); '
                'p.communicate(b"done\\n",timeout=10); sys.exit(p.returncode)')
        child = subprocess.Popen([sys.executable, '-u', '-c', code], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            data = json.loads(child.stdout.readline())
            identity = resource.ProcessIdentity.read(child.pid)
            snapshot = resource.process_snapshot(identity)
            self.output.with_suffix('.json').write_text(json.dumps(snapshot, indent=2))
            self.assertFalse(snapshot['errors'])
            pids = {p['pid'] for p in snapshot['records']}
            # Windows venv launchers can each have a base-interpreter child.
            self.assertTrue({child.pid, data['child'], data['child_runtime']} <= pids)
            self.assertTrue(all(p['ppid'] in pids for p in snapshot['records'] if p['pid'] != child.pid))
        finally:
            stdout, stderr = child.communicate('done\n', timeout=15)
        self.assertEqual((child.returncode, stdout, stderr), (0, '', ''))

    def test_delta_units(self):
        result = resource.interval_metrics(fixture_row(0), fixture_row(1), 4)
        self.assertEqual(result['status'], 'MEASURED')
        self.assertEqual(result['process']['12:123.0']['cpu_percent_machine_capacity'], 5)
        disk = result['disk']['PhysicalDrive0']
        self.assertEqual(disk['read_time_delta_ms'], 10)
        self.assertEqual(disk['write_time_delta_ms'], 20)
        self.assertEqual(disk['read_bytes_per_second'], 200)

    def test_counter_reset_nan_boolean_and_missing(self):
        for group, key, value in [('disk', 'read_bytes', -1), ('process', 'cpu_user_seconds', float('nan')),
                                  ('process', 'handles', True), ('disk', 'read_count', None)]:
            with self.subTest(group=group, key=key):
                a, b = fixture_row(0), fixture_row(1)
                b[group]['records'][0][key] = value
                self.assertEqual(resource.interval_metrics(a, b, 4)['status'], 'NOT_MEASURED')
        a, b = fixture_row(1), fixture_row(2)
        b['disk']['records'][0]['read_bytes'] = 1
        self.assertIn('disk-counter-reset-or-time-invalid', resource.interval_metrics(a, b, 4)['reasons'])

    def test_member_change_pid_reuse_and_disk_identity(self):
        for group, key, value in [('process', 'created', 456), ('disk', 'storage_device_number', 1)]:
            a, b = fixture_row(0), fixture_row(1)
            b[group]['records'][0][key] = value
            self.assertEqual(resource.interval_metrics(a, b, 4)['status'], 'NOT_MEASURED')

    def test_missing_duplicate_and_denied_samples(self):
        for mode in ('duplicate', 'missing', 'denied'):
            a, b = fixture_row(0), fixture_row(1)
            if mode == 'duplicate':
                b['process']['records'].append(deepcopy(b['process']['records'][0]))
            elif mode == 'missing':
                b['disk']['records'] = []
            else:
                b['process']['errors'] = [{'type': 'AccessDenied'}]
            self.assertEqual(resource.interval_metrics(a, b, 4)['status'], 'NOT_MEASURED')

    def test_missing_identity_and_wrong_counter_types(self):
        for group, key, value in [('disk', 'name', None), ('disk', 'storage_manager', ''),
                                  ('disk', 'read_count', 1.5), ('process', 'created', float('nan')),
                                  ('process', 'exe', 'C:\\other.exe')]:
            a, b = fixture_row(0), fixture_row(1)
            if value is None:
                del b[group]['records'][0][key]
            else:
                b[group]['records'][0][key] = value
            self.assertEqual(resource.interval_metrics(a, b, 4)['status'], 'NOT_MEASURED')

    def test_slow_reader_preserves_missed_slots(self):
        def slow_read(_reader):
            time.sleep(.12)
            return fixture_row()['disk']
        with patch.object(resource.WindowsDiskReader, 'snapshot', slow_read):
            result = resource.collect_resource_window(resource.ProcessIdentity.read(os.getpid()), self.output,
                                                      duration_seconds=.3, cadence_seconds=.05)
        self.assertEqual(result['recording_status'], 'INCOMPLETE')
        rows = [json.loads(p.read_text()) for p in self.output.glob('resource-*.json')]
        self.assertTrue(any(r['kind'] == 'missed_slot' for r in rows))
        verify_manifest(self.output)

    def test_invalid_time_and_cpu_count(self):
        a, b = fixture_row(0), fixture_row(1)
        b['process']['records'][0]['started_ns'] = a['process']['records'][0]['started_ns']
        self.assertEqual(resource.interval_metrics(a, b, 4)['status'], 'NOT_MEASURED')
        self.assertEqual(resource.interval_metrics(a, fixture_row(1), 0)['status'], 'NOT_MEASURED')

    def test_full_contract_and_long_window_coverage(self):
        result = self.review([fixture_row(i) for i in range(181)], duration=900)
        self.assertEqual(result['recording_status'], 'COMPLETE')
        self.assertEqual(result['resource_coverage_status'], 'SUFFICIENT')
        self.assertEqual([(w['start_seconds'], w['end_seconds'], w['count']) for w in result['windows']],
                         [(120, 420, 61), (420, 720, 61), (600, 900, 61)])
        self.assertEqual(result['resource_performance_gate'], 'NOT_EVALUATED')
        self.assertFalse(result['promotion_allowed'])

    def test_short_window_missing_reordered_and_gap(self):
        self.assertEqual(self.review([fixture_row(i) for i in range(25)], 120)['resource_coverage_status'], 'NOT_MEASURED')
        for mode in ('gap', 'duplicate', 'wrong-origin', 'root-change'):
            rows = [fixture_row(i) for i in range(85)]
            if mode == 'gap':
                rows[50] = dict(kind='missed_slot', sequence=50, scheduled_ns=rows[50]['scheduled_ns'])
            elif mode == 'duplicate':
                rows[50] = deepcopy(rows[49])
            elif mode == 'wrong-origin':
                rows[50]['scheduled_ns'] += 1
            else:
                rows[50]['process']['root']['exe'] = 'C:\\different.exe'
            self.assertEqual(self.review(rows)['recording_status'], 'INCOMPLETE')

    def test_shared_origin_actual_http_and_resources(self):
        origin = time.perf_counter_ns() + 500_000_000
        identity = resource.ProcessIdentity.read(os.getpid())
        self.output.mkdir()
        with local_server() as server, ThreadPoolExecutor(max_workers=2) as pool:
            http_future = pool.submit(http.collect_http_window, server.server_port, self.output / 'http',
                                      duration_seconds=.5, origin_ns=origin,
                                      endpoints=tuple(replace(e, interval_seconds=.1) for e in http.ENDPOINTS))
            resource_future = pool.submit(resource.collect_resource_window, identity, self.output / 'resource',
                                          duration_seconds=.5, cadence_seconds=.1, origin_ns=origin)
            http_result, result = http_future.result(), resource_future.result()
        self.assertEqual(http_result['origin_ns'], result['origin_ns'])
        self.assertEqual(http_result['origin_ns'], origin)
        self.assertEqual(result['recording_status'], 'COMPLETE')
        self.assertEqual(result['valid_samples'], 6)
        for name in ('http', 'resource'):
            verify_manifest(self.output / name)

    def test_cancellation_retains_raw_manifest(self):
        stop = threading.Event()
        stop.set()
        result = resource.collect_resource_window(resource.ProcessIdentity.read(os.getpid()), self.output,
                                                  duration_seconds=900, stop_event=stop)
        self.assertEqual(result['recording_status'], 'INCOMPLETE')
        self.assertEqual(result['expected_slots'], 181)
        verify_manifest(self.output)

    def test_slow_durable_write_is_timed_separately_from_http(self):
        original = os.fsync

        def slow_fsync(fd):
            time.sleep(.12)
            return original(fd)

        with local_server() as server, patch.object(http.os, 'fsync', slow_fsync):
            result = http.collect_http_window(server.server_port, self.output, duration_seconds=.4,
                                              endpoints=(replace(http.ENDPOINTS[0], interval_seconds=.1),),
                                              origin_ns=time.perf_counter_ns() + 500_000_000)
        self.assertEqual(result['http_component_status'], 'PASS')
        self.assertEqual(result['channels']['health']['missed_slots'], 0)
        self.assertEqual(result['channels']['health']['requests'], 4)
        self.assertEqual(result['persistence']['submitted_records'], result['persistence']['persisted_records'])
        self.assertEqual(result['persistence']['pending_bytes'], 0)
        self.assertEqual(result['persistence']['pending_records'], 0)
        self.assertGreater(result['persistence_drain_ms'], 100)
        self.assertGreaterEqual(result['file_persistence_max_ms'], 120)
        trace = json.loads((self.output / 'writes.json').read_text())
        self.assertTrue(any(r['file'].endswith('.body') for r in trace['writes']))
        for row in trace['writes']:
            self.assertEqual(row['file_persistence_ms'], (row['finished_ns'] - row['started_ns']) / 1e6)
            self.assertGreaterEqual(row['file_persistence_ms'], 120)
        verify_manifest(self.output)

    def test_pending_budgets_fail_without_dropping_a_pass(self):
        original = os.fsync

        def slow_fsync(fd):
            time.sleep(.12)
            return original(fd)

        self.output.mkdir()
        for key, value in [('pending_byte_budget', 1), ('pending_record_budget', 1)]:
            target = self.output / key
            with local_server() as server, patch.object(http.os, 'fsync', slow_fsync):
                result = http.collect_http_window(server.server_port, target, duration_seconds=.4,
                                                  endpoints=(replace(http.ENDPOINTS[0], interval_seconds=.05),),
                                                  origin_ns=time.perf_counter_ns() + 500_000_000,
                                                  **{key: value})
            self.assertEqual(result['http_component_status'], 'FAIL')
            self.assertTrue(result['worker_errors'])
            self.assertIn(key.replace('_', '-'), result['worker_errors'][0]['reason'])
            self.assertEqual(result['persistence']['pending_records'], 0)
            self.assertEqual(result['persistence']['pending_bytes'], 0)
            verify_manifest(target)

    def test_persistence_failure_preserves_partial_evidence(self):
        original = os.fsync
        counts = {'requests': 0}

        def fail_first_request(fd):
            if threading.current_thread().name == 'field-http-persistence':
                counts['requests'] += 1
                if counts['requests'] == 1:
                    raise OSError('injected durable write failure')
            return original(fd)

        with local_server() as server, patch.object(http.os, 'fsync', fail_first_request):
            result = http.collect_http_window(server.server_port, self.output, duration_seconds=.5,
                                              endpoints=(replace(http.ENDPOINTS[0], interval_seconds=.1),))
        self.assertEqual(result['http_component_status'], 'FAIL')
        self.assertTrue(result['persistence_errors'])
        self.assertGreater(result['persistence']['discarded_records'], 0)
        self.assertEqual(result['channels']['health']['requests'], 0)
        manifest = json.loads((self.output / 'manifest.json').read_text())
        self.assertTrue(manifest['files']['health-00000.body']['failed_write'])
        verify_manifest(self.output)

    def test_cancellation_drains_accepted_records(self):
        original = os.fsync
        stop = threading.Event()

        def cancel_during_request(fd):
            if threading.current_thread().name == 'field-http-persistence':
                stop.set()
            return original(fd)

        with local_server() as server, patch.object(http.os, 'fsync', cancel_during_request):
            result = http.collect_http_window(server.server_port, self.output, duration_seconds=.5,
                                              endpoints=(replace(http.ENDPOINTS[0], interval_seconds=.1),), stop_event=stop)
        self.assertEqual(result['http_component_status'], 'FAIL')
        self.assertEqual(result['persistence']['submitted_records'], result['persistence']['persisted_records'])
        self.assertEqual(result['persistence']['discarded_records'], 0)
        self.assertEqual(result['persistence']['pending_records'], 0)
        verify_manifest(self.output)

    def test_invalid_pending_budgets_before_output(self):
        for args in ({'pending_byte_budget': 0}, {'pending_byte_budget': 256 * 1024**2 + 1},
                     {'pending_record_budget': 0}, {'pending_record_budget': True}, {'pending_record_budget': 4097}):
            with self.assertRaises(ValueError):
                http.collect_http_window(1, self.output, duration_seconds=1, **args)
            self.assertFalse(self.output.exists())

    def test_default_channels_survive_one_second_durable_stall(self):
        original = os.fsync
        stalled = threading.Event()

        def stall_once(fd):
            if threading.current_thread().name == 'field-http-persistence' and not stalled.is_set():
                stalled.set()
                time.sleep(1)
            return original(fd)

        with local_server() as server, patch.object(http.os, 'fsync', stall_once):
            result = http.collect_http_window(server.server_port, self.output, duration_seconds=6.2)
        self.assertEqual(result['http_component_status'], 'PASS')
        self.assertEqual({name: r['requests'] for name, r in result['channels'].items()},
                         {'health': 4, 'data': 2, 'image': 25})
        self.assertTrue(all(r['missed_slots'] == 0 for r in result['channels'].values()))
        self.assertGreaterEqual(result['persistence']['peak_pending_records'], 4)
        self.assertGreaterEqual(result['file_persistence_max_ms'], 1000)
        self.assertEqual(result['persistence']['submitted_records'], 31)
        self.assertEqual(result['persistence']['persisted_records'], 31)
        verify_manifest(self.output)

    def test_invalid_contracts_rejected_before_write(self):
        for values in ({'duration_seconds': 0}, {'duration_seconds': float('nan')},
                       {'duration_seconds': 7201}, {'duration_seconds': 100, 'cadence_seconds': .01},
                       {'duration_seconds': 1, 'origin_ns': 0}, {'duration_seconds': 1, 'origin_ns': True},
                       {'duration_seconds': 1, 'origin_ns': time.perf_counter_ns() + 31_000_000_000}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                resource.collect_resource_window(resource.ProcessIdentity.read(os.getpid()), self.output, **values)
            self.assertFalse(self.output.exists())
        for origin in (0, True, time.perf_counter_ns() + 31_000_000_000):
            with self.assertRaises(ValueError):
                http.collect_http_window(1, self.output, duration_seconds=1, origin_ns=origin)
            self.assertFalse(self.output.exists())

    def test_existing_output_not_overwritten(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            resource.collect_resource_window(resource.ProcessIdentity.read(os.getpid()), self.output, duration_seconds=1)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_resource_filename_path_budget(self):
        output = ROOT / ('x' * (240 - len(str(ROOT)) - len('\\resource-00000.json')))
        self.assertEqual(len(str(output / 'resource-00000.json')), 241)
        with self.assertRaises(ValueError):
            resource.collect_resource_window(resource.ProcessIdentity.read(os.getpid()), output, duration_seconds=1)
        self.assertFalse(output.exists())

    def test_final_sample_overrun_cannot_be_complete(self):
        rows = [fixture_row(i) for i in range(85)]
        rows[-1]['finished_ns'] = rows[-1]['scheduled_ns'] + 5_000_000_000
        self.assertEqual(self.review(rows)['recording_status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main(verbosity=2)
