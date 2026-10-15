"""Shutdown identity negatives and preserved native candidate closeouts."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import field_configuration_binding as configuration
import field_installation_binding as binding
import field_observation as observation
import field_shutdown_binding as shutdown
from test_field_observation import configuration_snapshot, fixture_app


ROOT = Path(os.environ['SFL_SHUTDOWN_TEST_ROOT'])


def expectation():
    return dict(schema=shutdown.SCHEMA, build_git_commit=binding.BUILD,
                logger_service_instance_id='22222222-2222-4222-8222-222222222222',
                spot_service_instance_id='11111111-1111-4111-8111-111111111111',
                schema_version='2.5.2', csv_file_name='Factory_Integrated_Log_v2_fixture.csv',
                minimum_sample_seq=20, health_body_sha256='a' * 64,
                observed_at=datetime.now(timezone.utc).isoformat())


def metadata(expected, snapshot):
    return dict(schema_metadata=dict(git_commit=binding.BUILD,
                    logger_service_instance_id=expected['logger_service_instance_id'],
                    schema_version=expected['schema_version'], active_schema_version=expected['schema_version'],
                    csv_v2_temperature_hardening_enabled=True),
                spot_configuration_snapshot=deepcopy(snapshot),
                csv_closeout=dict(finalized=True, closeout_reason='shutdown',
                    csv_file_name=expected['csv_file_name'],
                    logger_service_instance_id=expected['logger_service_instance_id'],
                    final_persisted_sample_seq=expected['minimum_sample_seq'],
                    persisted_at='2026-01-01T00:00:00Z'))


class ShutdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.folder = ROOT / self._testMethodName
        self.folder.mkdir()
        self.expected = expectation()
        self.snapshot = configuration_snapshot()
        self.metadata = metadata(self.expected, self.snapshot)

    def test_exact_identity_and_prior_persistence_time_are_supported(self):
        result = shutdown.review_metadata(self.metadata, self.expected, self.snapshot)
        self.assertEqual(result['status'], 'PASS', result)
        self.assertEqual(result['csv_content_gate'], 'NOT_EVALUATED')
        self.assertEqual(result['normal_shutdown_gate'], 'NOT_EVALUATED')
        self.assertFalse(result['promotion_allowed'])
        observation.write_json(self.folder / 'review.json', result)

    def test_identity_and_closeout_negative_matrix(self):
        cases = [
            ('schema_metadata', 'git_commit', '0' * 40),
            ('schema_metadata', 'logger_service_instance_id', '33333333-3333-4333-8333-333333333333'),
            ('schema_metadata', 'schema_version', '2.4.0'),
            ('schema_metadata', 'active_schema_version', '2.5.1'),
            ('schema_metadata', 'csv_v2_temperature_hardening_enabled', 1),
            ('spot_configuration_snapshot', 'build_git_commit', '0' * 40),
            ('csv_closeout', 'logger_service_instance_id', '33333333-3333-4333-8333-333333333333'),
            ('csv_closeout', 'csv_file_name', 'Factory_Integrated_Log_v2_other.csv'),
            ('csv_closeout', 'csv_file_name', '../Factory_Integrated_Log_v2_fixture.csv'),
            ('csv_closeout', 'closeout_reason', 'rotation'),
            ('csv_closeout', 'finalized', False), ('csv_closeout', 'finalized', 1),
            ('csv_closeout', 'final_persisted_sample_seq', 19),
            ('csv_closeout', 'final_persisted_sample_seq', '20'),
            ('csv_closeout', 'final_persisted_sample_seq', True),
            ('csv_closeout', 'final_persisted_sample_seq', 2**63),
            ('csv_closeout', 'persisted_at', '2026-01-01T00:00:00'),
            ('csv_closeout', 'persisted_at', '9999-01-01T00:00:00Z'),
        ]
        reviews = []
        for section, key, value in cases:
            changed = deepcopy(self.metadata)
            changed[section][key] = value
            result = shutdown.review_metadata(changed, self.expected, self.snapshot)
            self.assertEqual(result['status'], 'FAIL', (section, key, result))
            self.assertEqual(result['identity_status'], 'FAIL')
            reviews.append(dict(section=section, key=key, value=value, review=result))
        for section in self.metadata:
            for value in (None, [], 'missing'):
                changed = dict(self.metadata, **{section: value})
                self.assertEqual(shutdown.review_metadata(changed, self.expected, self.snapshot)['status'], 'FAIL')
        observation.write_json(self.folder / 'cases.json', reviews)

    def test_pinned_attestation_cannot_be_replaced_by_self_consistent_configuration(self):
        changed = deepcopy(self.metadata)
        snap = changed['spot_configuration_snapshot']
        snap['settings_file_sha256'] = 'b' * 64
        fingerprint = configuration.canonical_fingerprint(snap)
        snap.update(spot_config_fingerprint_sha256=fingerprint, spot_config_verified_fingerprint_sha256=fingerprint)
        result = shutdown.review_metadata(changed, self.expected, self.snapshot)
        self.assertEqual(result['identity_status'], 'PASS')
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('pinned-reference:settings_file_sha256', result['configuration_review']['issues'])
        observation.write_json(self.folder / 'review.json', result)

    def test_bad_expectation_cannot_select_alternate_or_unsafe_file(self):
        for key, value in [('csv_file_name', '../other.csv'), ('csv_file_name', 'C:\\other.csv'),
                           ('csv_file_name', 'Factory_Integrated_Log_v2_test.csv:stream'),
                           ('minimum_sample_seq', 0), ('minimum_sample_seq', True),
                           ('minimum_sample_seq', 20.0), ('schema_version', '2.4.0'),
                           ('logger_service_instance_id', 'not-a-uuid'), ('build_git_commit', '0' * 40),
                           ('health_body_sha256', 'invalid'), ('observed_at', '2026-01-01')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                shutdown.validate_expectation(dict(self.expected, **{key: value}))

    def prepare_files(self):
        reference = self.folder / 'reference.json'
        fact = observation.write_json(reference, dict(schema='sfl-field-configuration-reference-v1',
            profile_approval_sha256=configuration.PROFILE_APPROVAL_SHA, snapshot=self.snapshot,
            classification='SYNTHETIC_TEST_NOT_FIELD_APPROVAL'))
        data = self.folder / 'data'
        data.mkdir()
        csv_path = data / self.expected['csv_file_name']
        csv_path.write_bytes(b'SYNTHETIC FILE: full CSV validation is deliberately not claimed\n')
        observation.write_json(csv_path.with_suffix('.metadata.json'), self.metadata)
        return data, reference, fact['sha256']

    def test_native_locks_and_exact_file_facts(self):
        data, reference, sha = self.prepare_files()
        original = shutdown.review_metadata

        def under_locks(*args, **kwargs):
            for path in data.iterdir():
                with self.assertRaises(PermissionError):
                    path.write_bytes(b'changed')
                with self.assertRaises(PermissionError):
                    path.unlink()
            return original(*args, **kwargs)

        with patch.object(shutdown, 'review_metadata', side_effect=under_locks):
            result = shutdown.review_shutdown_files(data, self.expected, reference, sha)
        self.assertEqual(result['shutdown_binding_status'], 'PASS', result)
        for name, fact in result['files'].items():
            raw = (data / name).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (fact['bytes'], fact['sha256']))
        self.assertEqual(result['csv_content_gate'], 'NOT_EVALUATED')
        observation.write_json(self.folder / 'result.json', result)

    def test_missing_exact_file_does_not_fall_back_to_another_sidecar(self):
        data, reference, sha = self.prepare_files()
        path = data / self.expected['csv_file_name']
        path.with_suffix('.metadata.json').rename(data / 'Factory_Integrated_Log_v2_other.metadata.json')
        result = shutdown.review_shutdown_files(data, self.expected, reference, sha)
        self.assertEqual(result['shutdown_binding_status'], 'FAIL')
        self.assertTrue(result['errors'])
        observation.write_json(self.folder / 'result.json', result)

    def test_reference_context_closeout_failure_cannot_leave_pass(self):
        data, reference, sha = self.prepare_files()
        original = configuration.configuration_reference

        @contextmanager
        def fail_closeout(*args, **kwargs):
            with original(*args, **kwargs) as snapshot:
                yield snapshot
                raise OSError('injected-shutdown-reference-closeout')

        with patch.object(configuration, 'configuration_reference', fail_closeout):
            result = shutdown.review_shutdown_files(data, self.expected, reference, sha)
        self.assertEqual(result['review']['status'], 'PASS')
        self.assertEqual(result['shutdown_binding_status'], 'FAIL')
        self.assertEqual(result['errors'][0]['reason'], 'injected-shutdown-reference-closeout')
        observation.write_json(self.folder / 'result.json', result)

    def test_duplicate_metadata_and_wrong_reference_hash_are_rejected(self):
        data, reference, sha = self.prepare_files()
        result = shutdown.review_shutdown_files(data, self.expected, reference, '0' * 64)
        self.assertEqual(result['shutdown_binding_status'], 'FAIL')
        (data / self.expected['csv_file_name']).with_suffix('.metadata.json').write_bytes(b'{"csv_closeout":{},"csv_closeout":{}}')
        result = shutdown.review_shutdown_files(data, self.expected, reference, sha)
        self.assertEqual(result['shutdown_binding_status'], 'FAIL')
        self.assertTrue(result['errors'])

    def test_real_loopback_boundary_uses_exact_health_bytes(self):
        with fixture_app(self.folder) as spec, binding.InstalledPayload(spec.root, spec.reference,
                expected_reference_sha256=spec.reference_sha256) as payload:
            boundary = binding.capture_runtime_binding(payload, spec.main, spec.backend, spec.port)
            expected = shutdown.expectation_from_boundary(boundary, spec.backend)
            self.assertEqual(expected['minimum_sample_seq'], 1)
            self.assertEqual(expected['health_body_sha256'], boundary['health_record']['body_sha256'])
            changed = deepcopy(boundary)
            changed['health_record']['body_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'health-body-binding'):
                shutdown.expectation_from_boundary(changed, spec.backend)
            observation.write_json(self.folder / 'boundary.json', boundary)
            observation.write_json(self.folder / 'expectation.json', expected)

    def test_archived_native_sessions_match_identity_but_fail_attestation(self):
        archive = Path(os.environ['SFL_SHUTDOWN_ARCHIVE'])
        cases = [('I4-candidate-runtime', '20261013_142551', 'ad99e165eb6368fc238766097566ca96075efc838aaea8728349ee60d132fbb8'),
                 ('I5-candidate-restart', '20261013_142706', '1eb95419353f2060f36f16b61b4b5e9eaee7bd67c1d43e946f7359fcfef09d55')]
        reviews = []
        for stage, stamp, sha in cases:
            path = archive / stage / 'closed-data' / f'Factory_Integrated_Log_v2_{stamp}.metadata.json'
            raw = path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), sha)
            sample_path = archive / stage / 'sample-14.json'
            sample_raw = sample_path.read_bytes()
            sample = json.loads(sample_raw)
            spot = sample['health']['spot_temperature']
            operational = spot['v2_4_operational']
            expected = dict(self.expected, build_git_commit=spot['build_git_commit'],
                logger_service_instance_id=operational['logger_service_instance_id'],
                spot_service_instance_id=spot['spot_service_instance_id'],
                schema_version=operational['schema_version'], minimum_sample_seq=operational['last_sample_seq'],
                csv_file_name=operational['current_v2_csv_file_name'],
                observed_at=datetime.fromtimestamp(sample['epoch'], timezone.utc).isoformat(),
                health_body_sha256=hashlib.sha256(json.dumps(sample['health']).encode()).hexdigest())
            # Archived health is parsed JSON, not the new collector's wire-bound observation.
            result = shutdown.review_metadata(json.loads(raw), expected, self.snapshot)
            self.assertEqual(result['identity_status'], 'PASS', result)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(result['configuration_review']['status'], 'FAIL')
            (self.folder / (stage + '.metadata.json')).write_bytes(raw)
            (self.folder / (stage + '.sample.json')).write_bytes(sample_raw)
            reviews.append(dict(stage=stage, metadata_source=str(path), metadata_sha256=sha,
                sample_source=str(sample_path), sample_sha256=hashlib.sha256(sample_raw).hexdigest(),
                classification='ARCHIVED_PARSED_HEALTH_REENCODED_NOT_WIRE_OR_FIELD_APPROVAL',
                expectation=expected, review=result))
        observation.write_json(self.folder / 'reviews.json', reviews)


if __name__ == '__main__':
    unittest.main(verbosity=2)
