"""Protected-input runner contracts; collection is replaced by an explicit fixture."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import field_health_runner as runner


ROOT = Path(os.environ['SFL_HEALTH_ENTRY_TEST_ROOT'])


def save(path, value):
    raw = json.dumps(value).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.root = ROOT/str(len(list(ROOT.iterdir())))
        self.root.mkdir()
        self.output = self.root/'output'
        self.archive = self.output/'inputs'
        (self.archive/'trace').mkdir(parents=True)
        self.installed = self.root/'installed'
        self.installed.mkdir()
        self.payload_sha = save(self.archive/'candidate-payload.json', {'synthetic': 'payload'})
        config_sha = save(self.archive/'configuration.json', {'synthetic': 'approved profile'})
        self.trace_sha = save(self.archive/'trace/manifest.json', {'synthetic': 'trace package'})
        self.request = dict(schema=runner.SCHEMA, candidate_commit=runner.binding.CANDIDATE_1029.commit,
            signature_policy='UNSIGNED_INTERNAL', duration_seconds=6, spec=dict(
                root=str(self.installed), reference=str(self.root/'original-reference-not-present.json'),
                reference_sha256=runner.PAYLOAD_SHA256,
                configuration_reference=str(self.root/'original-configuration-not-present.json'),
                configuration_reference_sha256=config_sha, extras={}, port=8000,
                main=dict(pid=100, created=1.0, exe=str(self.installed/'smart-factory.exe')),
                backend=dict(pid=101, created=2.0, exe=str(self.installed/'backend.exe')),
                backend_created_filetime=134365056356121274))

    def invoke(self, *, phase=None, mutate=None):
        self.request['spec']['reference_sha256'] = self.payload_sha
        request_sha = save(self.archive/'request.json', self.request)
        if mutate:
            mutate()
        seen = []

        def fixture(spec, output):
            seen.append(spec)
            self.assertEqual(spec.candidate, runner.binding.CANDIDATE_1029)
            self.assertEqual(spec.reference, str(self.archive/'candidate-payload.json'))
            self.assertEqual(spec.configuration_reference, str(self.archive/'configuration.json'))
            contract = json.loads(Path(spec.trace_contract_path).read_bytes())
            self.assertEqual(contract['package_sha256'], self.trace_sha)
            self.assertEqual(contract['backend_created_filetime'], self.request['spec']['backend_created_filetime'])
            outlier = self.request['schema'] == runner.OUTLIER_SCHEMA
            self.assertEqual(contract['duration_seconds'], 900 if outlier else 6)
            self.assertEqual(contract['guard_seconds'], 960 if outlier else 30)
            self.assertEqual(spec.outlier_capture, outlier)
            self.assertEqual(hashlib.sha256(Path(spec.trace_contract_path).read_bytes()).hexdigest(), spec.trace_contract_sha256)
            with self.assertRaises(OSError):
                (self.archive/'configuration.json').write_text('attempted replacement')
            output.mkdir()
            return phase or dict(supervisor_status='PASS', release_gate='HOLD', promotion_allowed=False)

        with patch.object(runner, 'PAYLOAD_SHA256', self.payload_sha), patch.object(runner.trace, 'supervise', fixture):
            result = runner.run(self.output, request_sha, self.trace_sha)
        return result, json.loads((self.output/'session/result.json').read_bytes()), seen

    def test_exact_request_identity_duration_and_members(self):
        runner.validate_request(self.request)
        for key, value in [('schema', 'old'), ('candidate_commit', runner.binding.BUILD),
                           ('signature_policy', 'SIGNED'), ('duration_seconds', 30), ('duration_seconds', True),
                           ('extra', 1)]:
            with self.subTest(key=key, value=value):
                changed = deepcopy(self.request)
                changed[key] = value
                with self.assertRaises(ValueError):
                    runner.validate_request(changed)

    def test_outlier_request_has_distinct_fixed_budget_and_contract(self):
        self.request.update(schema=runner.OUTLIER_SCHEMA, duration_seconds=900)
        runner.validate_request(self.request)
        for value in (6, 30, 899, 901, 900.0, True):
            with self.assertRaises(ValueError):
                runner.validate_request(dict(self.request, duration_seconds=value))
        result, saved, seen = self.invoke()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(saved['scope'], 'OUTLIER_CAPTURE_NOT_FIELD_PERFORMANCE')
        self.assertEqual(saved['field_gate'], 'NOT_EVALUATED')
        contract = json.loads(Path(seen[0].trace_contract_path).read_bytes())
        self.assertEqual(contract['schema'], 'sfl-health-outlier-contract-v1')
        self.assertEqual(contract['scope'], runner.trace.OUTLIER_SCOPE)

    def test_spec_rejects_changed_pins_extra_fields_and_native_identity(self):
        for key, value in [('reference_sha256', runner.binding.REFERENCE_SHA),
                           ('candidate_commit', runner.binding.BUILD), ('candidate_commit', None),
                           ('configuration_reference_sha256', 'bad'), ('backend_created_filetime', True),
                           ('backend_created_filetime', 0), ('backend_created_filetime', '134365056356121274'),
                           ('extra', 1), ('main', {'pid': 100})]:
            with self.subTest(key=key):
                changed = deepcopy(self.request)
                changed['spec'][key] = value
                with self.assertRaises(ValueError):
                    runner.validate_request(changed)

    def test_explicit_candidate_and_legacy_request_both_bind_1029(self):
        for explicit in (False, True):
            with self.subTest(explicit=explicit):
                if explicit:
                    self.setUp()
                    self.request['spec']['candidate_commit'] = runner.binding.CANDIDATE_1029.commit
                result, _, seen = self.invoke()
                self.assertEqual(result['status'], 'PASS')
                self.assertEqual(seen[0].candidate, runner.binding.CANDIDATE_1029)

    def test_archived_references_used_and_locked_before_collection(self):
        result, saved, seen = self.invoke()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(saved['archived_inputs']), 4)
        self.assertFalse(saved['frozen'])
        self.assertFalse(saved['promotion_allowed'])
        self.assertFalse(saved['installation_performed'])
        self.assertFalse(saved['application_shutdown_performed'])
        self.assertEqual(saved['field_gate'], 'NOT_EVALUATED')
        # The outer coordinator can still write: no premature full-tree manifest.
        self.assertFalse((self.output/'session/manifest.json').exists())

    def test_configuration_mismatch_prevents_collector(self):
        result, saved, seen = self.invoke(mutate=lambda: (self.archive/'configuration.json').write_text('{}'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertFalse(seen)
        self.assertIn('health-archived-input-pin:configuration.json', str(saved['errors']))

    def test_duplicate_request_key_prevents_collector(self):
        path = self.archive/'request.json'
        raw = b'{"schema":"a","schema":"b"}'
        path.write_bytes(raw)
        with patch.object(runner.trace, 'supervise') as collection:
            result = runner.run(self.output, hashlib.sha256(raw).hexdigest(), self.trace_sha)
        self.assertEqual(result['status'], 'FAIL')
        collection.assert_not_called()

    def test_phase_failure_propagates_without_claiming_capture(self):
        result, saved, seen = self.invoke(phase=dict(supervisor_status='FAIL', release_gate='HOLD', promotion_allowed=False))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(len(seen), 1)
        self.assertEqual(saved['phase']['supervisor_status'], 'FAIL')

    def test_phase_promotion_claim_rejected(self):
        result, saved, _ = self.invoke(phase=dict(supervisor_status='PASS', release_gate='PASS', promotion_allowed=True))
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('health-phase-gates', str(saved['errors']))

    def test_existing_output_is_never_overwritten(self):
        result, _, _ = self.invoke()
        before = (self.output/'session/result.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'health-session-already-exists'):
            runner.run(self.output, result['request_sha256'], self.trace_sha)
        self.assertEqual(before, (self.output/'session/result.json').read_bytes())

    def test_installation_inside_output_rejected_before_collection(self):
        self.request['spec']['root'] = str(self.archive)
        result, saved, seen = self.invoke()
        self.assertEqual(result['status'], 'FAIL')
        self.assertFalse(seen)
        self.assertIn('health-output-installation-boundary', str(saved['errors']))


if __name__ == '__main__':
    unittest.main()
