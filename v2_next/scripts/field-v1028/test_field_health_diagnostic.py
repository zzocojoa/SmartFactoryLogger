"""Boundary rejection with explicit synthetic native/process/HTTP evidence."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import field_health_diagnostic as diagnostic
import field_installation_binding as binding
from field_resource_sampling import ProcessIdentity
from test_health_timing_validation import CREATED, PROBE, fixture


class BoundProbeTests(unittest.TestCase):
    def setUp(self):
        root = Path('C:/synthetic-health-test')
        self.payload = SimpleNamespace(active=True, root=root, candidate=binding.CANDIDATE_1029,
                                       receipt={'scope': 'SYNTHETIC_TEST_ONLY'})
        self.main = ProcessIdentity(99, 10.0, os.path.normcase(str(root / 'smart-factory.exe')))
        self.backend = ProcessIdentity(100, 11.0, os.path.normcase(str(root / binding.BACKEND)))
        self.sessions = {'spot_service_instance_id': '11111111-1111-4111-8111-111111111111',
                         'logger_service_instance_id': '22222222-2222-4222-8222-222222222222'}
        self.native = dict(status='CAPTURED', pid=100, created_100ns=CREATED)
        self.health = dict(app_version='1.0.29', runtime_kind='frozen', mode='REAL',
            executable_path=self.backend.exe, frontend_source='resources', frontend_static_ready=True,
            spot_temperature=dict(build_git_commit=binding.CANDIDATE_1029.commit, diagnostics_available=True,
                spot_service_instance_id=self.sessions['spot_service_instance_id'],
                v2_4_operational=dict(enabled=True, logger_service_instance_id=self.sessions['logger_service_instance_id'])))

    def capture(self, *, native=None, graph=None, health=None, record_change=None, **options):
        record, _ = fixture()
        raw = json.dumps(self.health if health is None else health).encode()
        record.update(body_bytes=len(raw), body_sha256=hashlib.sha256(raw).hexdigest())
        if record_change:
            record.update(record_change)
        args = dict(expected_created_filetime=CREATED, expected_sessions=self.sessions, probe_id=PROBE)
        args.update(options)
        with patch.object(diagnostic.binding, 'read_process_binding',
                          side_effect=graph or [{'fixture': True}, {'fixture': True}]), \
                patch.object(diagnostic, 'WindowsProcessReader') as reader, \
                patch.object(diagnostic.http, 'fetch_sample', return_value=(record, raw)) as request:
            reader.return_value.read.side_effect = native or [deepcopy(self.native), deepcopy(self.native)]
            result = diagnostic.capture_health_probe(self.payload, self.main, self.backend, 8000, **args)
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertEqual(result['field_gate'], 'NOT_EVALUATED')
        self.assertEqual(result['etw_coverage'], 'NOT_EVALUATED')
        self.assertFalse(result['promotion_allowed'])
        if request.call_count:
            self.assertEqual(result['health_record'], record)
            self.assertEqual(bytes.fromhex(result['health_body_hex']), raw)
        return result, request.call_count

    def test_bound_request_preserves_raw_evidence_and_does_not_grant_field_gate(self):
        result, count = self.capture()
        self.assertEqual(count, 1)
        self.assertEqual(result['status'], 'REQUEST_AND_RUNTIME_BOUND', result)
        self.assertEqual(result['validation']['status'], 'REQUEST_AND_NATIVE_CLOCK_BOUND')
        self.assertEqual(result['sessions'], self.sessions)

    def test_1030_probe_requires_1030_runtime_not_just_valid_native_timing(self):
        self.payload.candidate = binding.CANDIDATE_1030
        result, count = self.capture()
        self.assertEqual((result['status'], count), ('NOT_BOUND', 1))
        self.health['app_version'] = binding.CANDIDATE_1030.version
        self.health['spot_temperature']['build_git_commit'] = binding.CANDIDATE_1030.commit
        result, count = self.capture()
        self.assertEqual((result['status'], count), ('REQUEST_AND_RUNTIME_BOUND', 1))
        self.payload.candidate = binding.CANDIDATE_1029
        self.assertEqual(self.capture()[0]['status'], 'NOT_BOUND')

    def test_missing_external_identity_or_wrong_candidate_never_contacts_http(self):
        for options in ({'expected_created_filetime': True}, {'expected_created_filetime': 0},
                        {'expected_sessions': {}}, {'probe_id': 'wrong'}):
            with self.subTest(options=options):
                result, count = self.capture(**options)
                self.assertEqual((result['status'], count), ('NOT_BOUND', 0))
        self.payload.candidate = binding.CANDIDATE_1028
        self.assertEqual(self.capture()[1], 0)
        self.payload.candidate = binding.CANDIDATE_1029
        self.payload.active = False
        self.assertEqual(self.capture()[1], 0)

    def test_changed_or_unavailable_native_generation_rejected_before_and_after_request(self):
        for bad in (dict(self.native, created_100ns=CREATED+1), dict(self.native, status='UNAVAILABLE'),
                    dict(self.native, pid=101), dict(self.native, created_100ns=True)):
            for after in (False, True):
                with self.subTest(bad=bad, after=after):
                    rows = [self.native, bad] if after else [bad]
                    result, count = self.capture(native=rows)
                    self.assertEqual(result['status'], 'NOT_BOUND')
                    self.assertEqual(count, int(after))

    def test_listener_process_change_retains_wire_evidence(self):
        result, count = self.capture(graph=[{'owner': 100}, {'owner': 101}])
        self.assertEqual((result['status'], count), ('NOT_BOUND', 1))
        result, count = self.capture(graph=[OSError('synthetic access failure')])
        self.assertEqual((result['status'], count), ('NOT_BOUND', 0))
        self.assertNotIn('synthetic access failure', json.dumps(result))

    def test_wire_tampering_or_wrong_probe_cannot_be_bound(self):
        for change in ({'health_probe_id': 'b'*32}, {'body_sha256': 'f'*64},
                       {'request_success': False}, {'timeout': True}):
            with self.subTest(change=change):
                result, count = self.capture(record_change=change)
                self.assertEqual((result['status'], count), ('NOT_BOUND', 1))

    def test_runtime_build_and_service_generation_must_match_even_with_valid_timing(self):
        for key, value in (('app_version', '1.0.28'), ('runtime_kind', 'dev'),
                           ('mode', 'MOCK'), ('executable_path', self.main.exe)):
            with self.subTest(key=key):
                result, _ = self.capture(health=dict(self.health, **{key: value}))
                self.assertEqual(result['status'], 'NOT_BOUND')
        for key, value in (('build_git_commit', binding.BUILD),
                           ('spot_service_instance_id', '33333333-3333-4333-8333-333333333333')):
            health = deepcopy(self.health)
            health['spot_temperature'][key] = value
            result, _ = self.capture(health=health)
            self.assertEqual(result['status'], 'NOT_BOUND')
        expected = dict(self.sessions, logger_service_instance_id='33333333-3333-4333-8333-333333333333')
        self.assertEqual(self.capture(expected_sessions=expected)[0]['status'], 'NOT_BOUND')


if __name__ == '__main__':
    unittest.main(verbosity=2)
