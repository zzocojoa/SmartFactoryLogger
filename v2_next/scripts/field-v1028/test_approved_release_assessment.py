import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

import approved_release_assessment as assessment
from field_http_sampling import ENDPOINTS


POLICY_PATH = Path(__file__).resolve().parents[2] / 'docs/V2/05_운영_배포/approved_release_policy_20261023.json'


class ApprovedReleaseAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.policy = assessment.load_policy(POLICY_PATH, hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest())

    def test_policy_hash_and_explicit_approval_required(self):
        with self.assertRaises(ValueError):
            assessment.load_policy(POLICY_PATH, '0' * 64)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'policy.json'
            for value in [False, 'true', 1, None]:
                policy = copy.deepcopy(self.policy)
                policy['approval']['approved'] = value
                path.write_text(json.dumps(policy), encoding='utf-8')
                with self.subTest(value=value), self.assertRaises(ValueError):
                    assessment.load_policy(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_bad_policy_values_and_duplicate_keys_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'policy.json'
            for value in [True, -1, float('nan'), float('inf'), '200']:
                policy = copy.deepcopy(self.policy)
                policy['operational_criteria']['health_latency_p99_ms_inclusive'] = value
                path.write_text(json.dumps(policy), encoding='utf-8')
                with self.subTest(value=value), self.assertRaises(ValueError):
                    assessment.load_policy(path, hashlib.sha256(path.read_bytes()).hexdigest())
            path.write_text('{"schema":1,"schema":2}', encoding='utf-8')
            with self.assertRaises(ValueError):
                assessment.load_policy(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_percentile_does_not_reintroduce_single_outlier_failure(self):
        self.assertEqual(assessment.percentile([200] * 99 + [321], .99), 200)
        self.assertEqual(assessment.percentile([200] * 98 + [201, 321], .99), 201)
        for values in [[], [True], [float('nan')]]:
            with self.assertRaises(ValueError):
                assessment.percentile(values, .99)

    def receipts(self, gaps, status='success'):
        current = datetime(2026, 10, 23, tzinfo=timezone.utc)
        rows = []
        for i, gap in enumerate([0, *gaps], 1):
            current += timedelta(milliseconds=gap)
            rows.append({'spot_service_instance_id': 'fixture', 'spot_poll_seq': str(i),
                         'spot_poll_status': status, 'spot_raw_validity': 'invalid_sentinel',
                         'spot_last_poll_completed_at': current.isoformat()})
        return rows

    def test_temperature_boundaries_and_real_sentinel_receipts(self):
        rows = self.receipts([1500] * 100)
        self.assertEqual(assessment.assess_temperature(rows, 'fixture', self.policy)['status'], 'PASS')
        rows = self.receipts([1500] * 99 + [3000])
        result = assessment.assess_temperature(rows, 'fixture', self.policy)
        self.assertEqual(result['p99_ms'], 1500)
        self.assertEqual(result['failures'], ['receipt-gap-exceeded'])
        self.assertEqual(assessment.assess_temperature(self.receipts([1501]), 'fixture', self.policy)['status'], 'FAIL')

    def test_temperature_rejects_missing_clock_identity_sequence_and_poll_error(self):
        for key, value in [('spot_poll_seq', '5'), ('spot_service_instance_id', 'different'),
                           ('spot_last_poll_completed_at', ''),
                           ('spot_last_poll_completed_at', '2026-10-23T00:00:01')]:
            rows = self.receipts([1000, 1000]); rows[1][key] = value
            with self.subTest(key=key, value=value):
                self.assertEqual(assessment.assess_temperature(rows, 'fixture', self.policy)['status'], 'INCOMPLETE')
        self.assertEqual(assessment.assess_temperature(self.receipts([1000], 'error'), 'fixture', self.policy)['status'], 'FAIL')

    def display(self, timestamps, **kwargs):
        samples = [{'presented_at_ms': t, 'response_id': str(i), 'presentation_confirmed': True,
                    'fresh_frame_identity_confirmed': True, 'visible': True, 'occluded': False}
                   for i, t in enumerate(timestamps)]
        return assessment.assess_display(samples, window_start_ms=0, window_end_ms=kwargs.get('end', timestamps[-1]),
                                         complete=True, white_screen_events=kwargs.get('white', 0), policy=self.policy)

    def test_display_threshold_and_tail_stall(self):
        self.assertEqual(self.display([500, 1000, 1500])['status'], 'PASS')
        self.assertEqual(self.display([500, 1000, 1500], end=3500)['failures'], ['display-gap-exceeded'])
        self.assertIn('white-screen', self.display([500, 1000], white=1)['failures'])

    def test_dom_load_raf_or_unconfirmed_identity_cannot_pass_display(self):
        for missing in ['presentation_confirmed', 'fresh_frame_identity_confirmed', 'visible', 'occluded', 'response_id']:
            records = [{'presented_at_ms': t, 'response_id': str(t), 'presentation_confirmed': True,
                        'fresh_frame_identity_confirmed': True, 'visible': True, 'occluded': False}
                       for t in [100, 500]]
            records[1].pop(missing)
            with self.subTest(missing=missing):
                self.assertEqual(assessment.assess_display(records, window_start_ms=0, window_end_ms=700,
                    complete=True, white_screen_events=0, policy=self.policy)['status'], 'INCOMPLETE')

    def test_rollback_exception_is_limited_to_clean_normal_exit(self):
        record = {k: self.policy['rollback'][k] for k in
                  ['build_commit', 'installer_sha256', 'request_path', 'http_status', 'reason']}
        record.update(normal_ui_close_requested=True, forced_exit=False, data_validation_passed=True,
                      native_exit_codes=[0, 0], pending_writes=0, storage_failures=0,
                      close_requested_at=100, error_at=101, exit_at=102)
        self.assertEqual(assessment.assess_rollback(record, self.policy)['disposition'], 'ACCEPTED_KNOWN_LIMITATION')
        for key, value in [('error_at', 99), ('error_at', 103), ('forced_exit', True), ('pending_writes', 1),
                           ('storage_failures', 1), ('native_exit_codes', [1]), ('native_exit_codes', [False]),
                           ('data_validation_passed', False), ('reason', 'timeout'), ('http_status', 200),
                           ('build_commit', self.policy['candidate']['build_commit'])]:
            with self.subTest(key=key):
                self.assertEqual(assessment.assess_rollback({**record, key: value}, self.policy)['disposition'], 'NOT_ACCEPTED')

    def test_http_does_not_treat_missing_measurements_as_success(self):
        result = assessment.assess_http(ENDPOINTS[0], [], 10, self.policy)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertFalse(result['promotion_allowed'])

    def test_http_boundary_requests_need_no_fabricated_schedule_fields(self):
        def request(start, latency=20):
            end = start + latency * 1000000
            return {'kind': 'request', 'endpoint': 'health', 'path': '/health', 'status': 200,
                    'started_ns': start, 'response_finished_ns': end, 'finished_ns': end + 1000,
                    'client_request_and_body_ms': latency, 'request_success': True,
                    'timeout': False, 'body_complete': True, 'decode_complete': True}
        records = [dict(request(1000000000), sequence=0, start_lateness_ms=0)]
        boundaries = [request(1), request(2000000000)]
        result = assessment.assess_http(ENDPOINTS[0], records, 1, self.policy, boundary_records=boundaries)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['boundary_count'], 2)
        self.assertNotIn('sequence', boundaries[0])
        boundaries[-1] = request(2000000000, 201)
        self.assertEqual(assessment.assess_http(ENDPOINTS[0], records, 1, self.policy,
            boundary_records=boundaries)['status'], 'FAIL')
        boundaries[-1]['request_success'] = False
        boundaries[-1]['timeout'] = True
        self.assertIn('boundary-request-error-or-timeout', assessment.assess_http(
            ENDPOINTS[0], records, 1, self.policy, boundary_records=boundaries)['failures'])
        for bad in [[], [boundaries[0]], [None, request(2000000000)], [request(1100000000), request(2000000000)]]:
            with self.subTest(boundaries=bad):
                self.assertEqual(assessment.assess_http(ENDPOINTS[0], records, 1, self.policy,
                    boundary_records=bad)['status'], 'INCOMPLETE')

    def test_display_non_records_are_incomplete(self):
        for records in [None, [None, {}], [1, 2]]:
            with self.subTest(records=records):
                self.assertEqual(assessment.assess_display(records, window_start_ms=0,
                    window_end_ms=1000, complete=True, white_screen_events=0,
                    policy=self.policy)['status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
