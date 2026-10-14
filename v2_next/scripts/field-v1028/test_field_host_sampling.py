"""Host diagnostics counter semantics and one native read-only sample pair."""
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import psutil
import field_host_sampling as host


def sample(t, cpu, *, pid=10, created=1.0):
    return {'logical_cpus': 2, 'host': {'cpu_user_seconds': cpu, 'cpu_system_seconds': cpu,
            'cpu_idle_seconds': cpu * 2, 'counter_observed_ns': t}, 'processes': [
        {'pid': pid, 'created': created, 'name': 'fixture', 'status': 'CAPTURED',
         'started_ns': t, 'finished_ns': t, 'cpu_user_seconds': cpu,
         'cpu_system_seconds': 0.0, 'rss_bytes': 100, 'vms_bytes': 80}]}


class HostSamplingTests(unittest.TestCase):
    def test_cpu_counters_have_host_and_machine_capacity_denominators(self):
        result = host.compare_host(sample(1_000_000_000, 1), sample(3_000_000_000, 2))
        self.assertEqual(result['host_cpu_percent'], 50)
        self.assertEqual(result['process_intervals'][0]['cpu_percent_machine_capacity'], 25)
        self.assertFalse(result['partial'])
        self.assertEqual(result['resource_performance_gate'], 'NOT_EVALUATED')
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertFalse(result['promotion_allowed'])

    def test_pid_reuse_does_not_join_different_generations(self):
        result = host.compare_host(sample(1, 1), sample(2, 2, created=2.0))
        self.assertFalse(result['process_intervals'])
        self.assertTrue(result['partial'])
        self.assertEqual(len(result['unmeasured']), 2)

    def test_decreasing_component_cannot_hide_in_increasing_sum(self):
        before, after = sample(1, 1), sample(2, 2)
        before['processes'][0]['cpu_system_seconds'] = 3
        after['processes'][0]['cpu_user_seconds'] = 10
        result = host.compare_host(before, after)
        self.assertFalse(result['process_intervals'])

    def test_unknown_counter_is_not_zero_or_nonfinite(self):
        for value in [None, float('nan'), float('inf'), -1, True]:
            before, after = sample(1, 1), sample(2, 2)
            after['host']['cpu_user_seconds'] = value
            after['processes'][0]['cpu_user_seconds'] = value
            result = host.compare_host(before, after)
            self.assertIsNone(result['host_cpu_percent'])
            self.assertFalse(result['process_intervals'])

    def test_changed_cpu_count_and_reversed_time_are_unmeasured(self):
        before, after = sample(2, 1), sample(1, 2)
        self.assertFalse(host.compare_host(before, after)['process_intervals'])
        after['logical_cpus'] = 3
        result = host.compare_host(before, after)
        self.assertIsNone(result['host_cpu_percent'])
        self.assertTrue(result['partial'])

    def test_unavailable_process_and_truncation_are_explicit(self):
        before, after = sample(1, 1), sample(2, 2)
        after['processes'][0].update(status='UNAVAILABLE', reason='AccessDenied')
        after['truncated'] = True
        result = host.compare_host(before, after)
        self.assertFalse(result['process_intervals'])
        self.assertTrue(result['partial'])

    @unittest.skipUnless(os.name == 'nt', 'Native Windows observation')
    def test_native_process_counters_match_current_process_identity(self):
        reader = host.WindowsProcessReader()
        process = psutil.Process()
        cpu_before = process.cpu_times()
        row = reader.read(process.pid)
        cpu_after = process.cpu_times()
        self.assertEqual(row['status'], 'CAPTURED')
        self.assertAlmostEqual(row['created'], process.create_time(), places=5)
        self.assertEqual(row['name'], process.name())
        for key, attribute in [('cpu_user_seconds', 'user'), ('cpu_system_seconds', 'system')]:
            self.assertLessEqual(getattr(cpu_before, attribute), row[key])
            self.assertLessEqual(row[key], getattr(cpu_after, attribute))
        self.assertGreater(row['rss_bytes'], 0)
        self.assertEqual(reader.read(0)['reason'], 'idle-pseudo-process-excluded')

    def test_process_budget_is_enforced_without_extra_sampling(self):
        with patch.object(host.psutil, 'pids', return_value=list(range(5))), \
                patch.object(host.WindowsProcessReader, 'read', return_value={'status': 'CAPTURED'}) as snap:
            result = host.capture_host(process_limit=2)
        self.assertEqual(snap.call_count, 2)
        self.assertTrue(result['truncated'])

    @unittest.skipUnless(os.name == 'nt', 'Native Windows observation')
    def test_native_handle_is_closed_when_counter_read_fails(self):
        reader = host.WindowsProcessReader()
        closed = []
        reader.api = SimpleNamespace(OpenProcess=lambda *args: 123,
            GetProcessTimes=lambda *args: 0, CloseHandle=lambda handle: closed.append(handle) or 1)
        row = reader.read(10)
        self.assertEqual(row['status'], 'UNAVAILABLE')
        self.assertEqual(closed, [123])
        self.assertNotIn('name', row)

    def test_raw_creation_ticks_separate_same_float_timestamp(self):
        before, after = sample(1, 1), sample(2, 2)
        before['processes'][0]['created_100ns'] = 134000000000000001
        after['processes'][0]['created_100ns'] = 134000000000000002
        self.assertFalse(host.compare_host(before, after)['process_intervals'])

    @unittest.skipUnless(os.name == 'nt', 'Native Windows observation')
    def test_native_sample_pair_contains_own_process_and_no_sensitive_fields(self):
        before = host.capture_host()
        time.sleep(1)
        after = host.capture_host()
        result = host.compare_host(before, after)
        self.assertTrue(any(p['pid'] == os.getpid() for p in result['process_intervals']))
        self.assertIsNotNone(result['host_cpu_percent'])
        self.assertGreaterEqual(result['host_cpu_percent'], 0)
        self.assertLessEqual(result['host_cpu_percent'], 100)
        allowed = {'pid', 'name', 'created', 'cpu_user_seconds', 'cpu_system_seconds',
                   'rss_bytes', 'vms_bytes', 'status', 'reason', 'started_ns', 'finished_ns',
                   'created_100ns', 'cpu_observed_ns', 'winerror'}
        for snapshot in (before, after):
            self.assertFalse(snapshot['errors'])
            for row in snapshot['processes']:
                self.assertLessEqual(set(row), allowed)
        print({'native_processes': len(after['processes']),
               'sample_cost_ms': [before['capture_ms'], after['capture_ms']],
               'unavailable': after['unavailable_processes'], 'host_cpu_percent': result['host_cpu_percent']})


if __name__ == '__main__':
    unittest.main()
