"""Final attestation binding, native file locks and actual product serialization."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import field_configuration_binding as configuration
import field_installation_binding as binding
import field_observation as observation
from test_field_observation import configuration_snapshot, fixture_app


ROOT = Path(os.environ['SFL_CONFIGURATION_TEST_ROOT'])


class ConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.folder = ROOT / self._testMethodName
        self.folder.mkdir()
        self.snapshot = configuration_snapshot()

    def test_actual_product_payload_and_fingerprint_contract(self):
        # Production module reads only this test's config and does not import app/config.
        repository = Path(os.environ['SFL_CONFIGURATION_REPO'])
        sys.path.insert(0, str(repository))
        try:
            from backend.FacilityData.spot_config_provenance import build_spot_configuration_snapshot
            from backend.tests.test_spot_config_provenance import config_namespace, attest
            config = config_namespace(SPOT_LOW_SIGNAL_ALARM_ENABLED=False, SPOT_CONFIG_VERIFIED_BY='USER_SELF')
            path = self.folder / 'settings.ini'
            path.write_text('[SPOT]\nmodelinfo=SPOT+ AL\n', encoding='utf-8')
            config.CONFIG_PATH = path
            before = build_spot_configuration_snapshot(config, runtime_git_commit=binding.BUILD)
            config = attest(config, before['spot_config_fingerprint_sha256'])
            config.SPOT_CONFIG_VERIFIED_BY = 'USER_SELF'
            actual = build_spot_configuration_snapshot(config, runtime_git_commit=binding.BUILD)
            self.assertEqual(set(configuration.PAYLOAD_KEYS), set(before) - set(configuration.ATTESTATION_KEYS)
                             - {'low_signal_config_source', 'config_captured_at'})
            self.assertEqual(configuration.canonical_fingerprint(actual), actual['spot_config_fingerprint_sha256'])
            result = configuration.review_snapshot(actual)
            self.assertEqual(result['status'], 'PASS', result)
            observation.write_json(self.folder / 'actual-product-snapshot.json', actual)
            observation.write_json(self.folder / 'review.json', result)
        finally:
            sys.path.remove(str(repository))

    def test_missing_payload_fields_and_fingerprint_tampering(self):
        for key in configuration.PAYLOAD_KEYS:
            with self.subTest(key=key):
                value = deepcopy(self.snapshot)
                del value[key]
                self.assertEqual(configuration.review_snapshot(value)['status'], 'FAIL')
        value = dict(self.snapshot, settings_file_sha256='b' * 64)
        self.assertIn('fingerprint-recomputed-mismatch', configuration.review_snapshot(value)['issues'])
        # Recomputing both claimed fingerprints still cannot change the pinned baseline.
        fingerprint = configuration.canonical_fingerprint(value)
        value.update(spot_config_fingerprint_sha256=fingerprint, spot_config_verified_fingerprint_sha256=fingerprint)
        result = configuration.review_snapshot(value, self.snapshot)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('pinned-reference:settings_file_sha256', result['issues'])
        observation.write_json(self.folder / 'tamper.json', result)

    def test_unverified_drift_invalid_readback_and_wrong_operator_fail(self):
        cases = {
            'config_operator_verified': False, 'config_operator_verified_requested': 1,
            'low_signal_comparator_verified': False, 'low_signal_comparator_configured_verified': False,
            'config_attestation_status': 'fingerprint_mismatch', 'config_drift_detected': True,
            'config_drift_fields': ['spot_config_fingerprint_sha256'], 'device_config_readback_status': 'partial',
            'spot_config_verified_by': 'Operator1', 'spot_config_verified_at': '2026-01-01T00:00:00',
            'spot_ratio_raw_enabled': 0, 'spot_range_min_c': True, 'spot_range_max_c': float('nan'),
            'low_signal_comparator': 'unknown', 'spot_ip': 'http://192.0.2.1',
            'config_captured_at': '2000-01-01T00:00:00Z',
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                self.assertEqual(configuration.review_snapshot(dict(self.snapshot, **{key: value}))['status'], 'FAIL')
        matched = dict(self.snapshot, device_config_readback_status='matched',
                       device_config_fingerprint_sha256=self.snapshot['spot_config_fingerprint_sha256'])
        self.assertEqual(configuration.review_snapshot(matched)['status'], 'PASS')
        matched['device_config_fingerprint_sha256'] = 'b' * 64
        self.assertIn('device-fingerprint-mismatch', configuration.review_snapshot(matched)['issues'])
        observation.write_json(self.folder / 'cases.json', dict(rejected=len(cases), matched_readback_checked=True))

    def test_external_reference_hash_approval_and_lock(self):
        path = self.folder / 'reference.json'
        value = dict(schema='sfl-field-configuration-reference-v1',
                     profile_approval_sha256=configuration.PROFILE_APPROVAL_SHA, snapshot=self.snapshot)
        fact = observation.write_json(path, value)
        with self.assertRaisesRegex(ValueError, 'reference-hash'):
            with configuration.configuration_reference(path, '0' * 64):
                self.fail('tampered reference accepted')
        with configuration.configuration_reference(path, fact['sha256']) as expected:
            self.assertEqual(expected, self.snapshot)
            with self.assertRaises(PermissionError):
                path.write_bytes(b'changed')
            with self.assertRaises(PermissionError):
                path.unlink()
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), fact['sha256'])
        for name, replacement in [('unverified', dict(value, snapshot=dict(self.snapshot, config_operator_verified=False))),
                                  ('wrong-approval', dict(value, profile_approval_sha256='0' * 64))]:
            target = self.folder / (name + '.json')
            target_fact = observation.write_json(target, replacement)
            with self.assertRaises(ValueError):
                with configuration.configuration_reference(target, target_fact['sha256']):
                    self.fail('invalid reference accepted')

    def test_oversize_duplicate_and_invalid_reference_json(self):
        for name, raw in [('oversize', b' ' * 32769), ('duplicate', b'{"snapshot":{},"snapshot":{}}'),
                          ('invalid-utf8', b'\xff'), ('array', b'[]')]:
            with self.subTest(name=name):
                path = self.folder / (name + '.json')
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    with configuration.configuration_reference(path, hashlib.sha256(raw).hexdigest()):
                        self.fail('invalid reference accepted')

    def test_native_capture_keeps_wire_bytes_and_rejects_wrong_service(self):
        for name, mode in [('normal', 'normal'), ('wrong-service', 'configuration-session')]:
            folder = self.folder / name
            folder.mkdir()
            with fixture_app(folder, mode) as spec, binding.InstalledPayload(spec.root, spec.reference,
                    expected_reference_sha256=spec.reference_sha256) as payload, \
                    configuration.configuration_reference(spec.configuration_reference,
                        spec.configuration_reference_sha256) as expected:
                result = configuration.capture_configuration(payload, spec.main, spec.backend, spec.port,
                    {'spot_service_instance_id': '11111111-1111-4111-8111-111111111111'}, expected)
                self.assertEqual(result['configuration_status'], 'PASS' if name == 'normal' else 'FAIL', result)
                record, raw = result['configuration_record'], bytes.fromhex(result['configuration_body_hex'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), record['body_sha256'])
                self.assertEqual(len(raw), record['body_bytes'])
                self.assertEqual(result['field_gate'], 'NOT_EVALUATED')
                observation.write_json(folder / 'capture.json', result)

    def test_os_identity_change_and_prior_process_snapshot_fail(self):
        with fixture_app(self.folder) as spec, binding.InstalledPayload(spec.root, spec.reference,
                expected_reference_sha256=spec.reference_sha256) as payload:
            expected = json.loads(Path(spec.configuration_reference).read_text(encoding='utf-8'))['snapshot']
            for mode in ('process-change', 'old-snapshot'):
                image = dict(expected, spot_service_instance_id='11111111-1111-4111-8111-111111111111',
                             config_captured_at=datetime.fromtimestamp(spec.backend.created - 10 if mode == 'old-snapshot'
                                 else spec.backend.created + 1, timezone.utc).isoformat())
                raw = json.dumps(dict(image=image)).encode()
                with patch.object(binding, 'read_process_binding', side_effect=[{}, {'changed': True}]), \
                        patch.object(configuration.http, 'fetch_sample', return_value=({'request_success': True}, raw)):
                    result = configuration.capture_configuration(payload, spec.main, spec.backend, spec.port,
                        {'spot_service_instance_id': image['spot_service_instance_id']}, expected)
                    self.assertEqual(result['configuration_status'], 'FAIL')
                    observation.write_json(self.folder / (mode + '.json'), result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
