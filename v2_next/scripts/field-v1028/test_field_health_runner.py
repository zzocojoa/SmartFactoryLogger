"""Protected-input runner contracts; collection is replaced by an explicit fixture."""
from copy import deepcopy
import hashlib
import json
import os
import shutil
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
                reference_sha256=runner.binding.REFERENCE_SHA_1029,
                configuration_reference=str(self.root/'original-configuration-not-present.json'),
                configuration_reference_sha256=config_sha, extras={}, port=8000,
                main=dict(pid=100, created=1.0, exe=str(self.installed/'smart-factory.exe')),
                backend=dict(pid=101, created=2.0, exe=str(self.installed/'backend.exe')),
                backend_created_filetime=134365056356121274))

    def invoke(self, *, phase=None, mutate=None):
        expected_candidate = runner.binding.candidate_from_commit(self.request['candidate_commit'])
        self.request['spec']['reference_sha256'] = self.payload_sha
        request_sha = save(self.archive/'request.json', self.request)
        if mutate:
            mutate()
        seen = []

        def fixture(spec, output):
            seen.append(spec)
            self.assertEqual(spec.candidate, expected_candidate)
            self.assertEqual(spec.reference, str(self.archive/'candidate-payload.json'))
            self.assertEqual(spec.configuration_reference, str(self.archive/'configuration.json'))
            contract = json.loads(Path(spec.trace_contract_path).read_bytes())
            self.assertEqual(contract['package_sha256'], self.trace_sha)
            self.assertEqual(contract['backend_created_filetime'], self.request['spec']['backend_created_filetime'])
            outlier = self.request['schema'] not in (runner.SCHEMA, runner.PYTHON_SCHEMA, runner.PYTHON_BASELINE_SCHEMA)
            self.assertEqual(contract['duration_seconds'], 900 if outlier else 6)
            self.assertEqual(contract['guard_seconds'], 960 if outlier else 30)
            self.assertEqual(spec.outlier_capture, outlier)
            self.assertEqual(spec.cpu_samples, self.request['schema'] in (runner.CPU_OUTLIER_SCHEMA, runner.CPU_CONCURRENT_SCHEMA))
            self.assertEqual(spec.concurrent_api, self.request['schema'] in (runner.CPU_CONCURRENT_SCHEMA, runner.READY_CONCURRENT_SCHEMA))
            self.assertEqual(spec.ready_stacks, self.request['schema'] == runner.READY_CONCURRENT_SCHEMA)
            self.assertEqual(spec.python_frames, self.request['schema'] == runner.PYTHON_SCHEMA)
            self.assertEqual(spec.python_baseline, self.request['schema'] == runner.PYTHON_BASELINE_SCHEMA)
            if spec.python_frames or spec.python_baseline:
                self.assertEqual(spec.tool, str(self.archive/'sfl_qpc_reader.exe'))
                with self.assertRaises(OSError): Path(spec.tool).write_bytes(b'replacement')
            self.assertEqual(hashlib.sha256(Path(spec.trace_contract_path).read_bytes()).hexdigest(), spec.trace_contract_sha256)
            with self.assertRaises(OSError):
                (self.archive/'configuration.json').write_text('attempted replacement')
            output.mkdir()
            return phase or dict(supervisor_status='PASS', release_gate='HOLD', promotion_allowed=False)

        def payload_pin(candidate):
            self.assertEqual(candidate, expected_candidate)
            return self.payload_sha

        with patch.object(runner.binding, 'candidate_reference_sha256', payload_pin), \
                patch.object(runner.trace, 'supervise', fixture):
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

    def test_cpu_request_is_explicit_and_preserves_fixed_outlier_budget(self):
        self.request.update(schema=runner.CPU_OUTLIER_SCHEMA, duration_seconds=900)
        runner.validate_request(self.request)
        for value in (6, 30, 899, 901, 900.0, True):
            with self.assertRaises(ValueError):
                runner.validate_request(dict(self.request, duration_seconds=value))
        result, saved, seen = self.invoke()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(saved['scope'], 'CPU_OUTLIER_CAPTURE_NOT_FIELD_PERFORMANCE')
        self.assertEqual(saved['mode'], 'health-cpu-outlier-trace')
        contract = json.loads(Path(seen[0].trace_contract_path).read_bytes())
        self.assertEqual(contract['schema'], 'sfl-health-cpu-outlier-contract-v1')
        self.assertEqual(contract['scope'], runner.trace.CPU_OUTLIER_SCOPE)
        self.assertFalse(saved['promotion_allowed'])

    def test_explicit_candidate_and_legacy_request_both_bind_1029(self):
        for explicit in (False, True):
            with self.subTest(explicit=explicit):
                if explicit:
                    self.setUp()
                    self.request['spec']['candidate_commit'] = runner.binding.CANDIDATE_1029.commit
                result, _, seen = self.invoke()
                self.assertEqual(result['status'], 'PASS')
                self.assertEqual(seen[0].candidate, runner.binding.CANDIDATE_1029)

    def test_concurrent_request_uses_distinct_contract_and_cannot_hide_in_spec(self):
        self.request.update(schema=runner.CPU_CONCURRENT_SCHEMA, duration_seconds=900)
        runner.validate_request(self.request)
        for duration in (6, 899, 901, True, 900.0):
            with self.assertRaises(ValueError):
                runner.validate_request(dict(self.request, duration_seconds=duration))
        changed = deepcopy(self.request)
        changed['schema'] = runner.CPU_OUTLIER_SCHEMA
        changed['spec']['concurrent_api'] = True
        with self.assertRaisesRegex(ValueError, 'health-request-spec-members'):
            runner.validate_request(changed)
        result, saved, seen = self.invoke()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(saved['mode'], 'health-cpu-concurrent-trace')
        self.assertEqual(saved['scope'], 'CPU_CONCURRENT_CAPTURE_NOT_FIELD_PERFORMANCE')
        contract = json.loads(Path(seen[0].trace_contract_path).read_bytes())
        self.assertEqual(contract['schema'], 'sfl-health-cpu-concurrent-contract-v1')
        self.assertEqual(contract['scope'], runner.trace.CPU_CONCURRENT_SCOPE)

    def test_1030_requires_explicit_matching_spec_and_payload_pin(self):
        self.request['candidate_commit'] = runner.binding.CANDIDATE_1030.commit
        self.request['spec']['reference_sha256'] = runner.binding.REFERENCE_SHA_1030
        with self.assertRaisesRegex(ValueError, 'health-request-spec-candidate'):
            runner.validate_request(self.request)
        self.request['spec']['candidate_commit'] = runner.binding.CANDIDATE_1030.commit
        runner.validate_request(self.request)
        for key, value in [('candidate_commit', runner.binding.CANDIDATE_1029.commit),
                           ('reference_sha256', runner.binding.REFERENCE_SHA_1029)]:
            changed = deepcopy(self.request)
            changed['spec'][key] = value
            with self.assertRaises(ValueError):
                runner.validate_request(changed)
        changed = deepcopy(self.request)
        changed['candidate_commit'] = runner.binding.CANDIDATE_1029.commit
        with self.assertRaisesRegex(ValueError, 'health-request-spec-candidate'):
            runner.validate_request(changed)

    def test_all_1030_trace_modes_keep_candidate_and_fixed_contract(self):
        for schema in (runner.SCHEMA, runner.OUTLIER_SCHEMA, runner.CPU_OUTLIER_SCHEMA, runner.CPU_CONCURRENT_SCHEMA,
                       runner.READY_CONCURRENT_SCHEMA):
            with self.subTest(schema=schema):
                self.setUp()
                self.request.update(schema=schema, duration_seconds=6 if schema == runner.SCHEMA else 900,
                                    candidate_commit=runner.binding.CANDIDATE_1030.commit)
                self.request['spec']['candidate_commit'] = runner.binding.CANDIDATE_1030.commit
                result, saved, seen = self.invoke()
                self.assertEqual(result['status'], 'PASS', saved)
                self.assertEqual(seen[0].candidate, runner.binding.CANDIDATE_1030)
                self.assertEqual(saved['field_gate'], 'NOT_EVALUATED')
                self.assertFalse(saved['promotion_allowed'])

    def test_ready_request_is_distinct_and_keeps_fixed_limits(self):
        self.request.update(schema=runner.READY_CONCURRENT_SCHEMA, duration_seconds=900)
        for duration in (6, 899, 901, True, 900.0):
            with self.assertRaises(ValueError):
                runner.validate_request(dict(self.request, duration_seconds=duration))
        changed = deepcopy(self.request)
        changed['schema'] = runner.CPU_CONCURRENT_SCHEMA
        changed['spec']['ready_stacks'] = True
        with self.assertRaisesRegex(ValueError, 'health-request-spec-members'):
            runner.validate_request(changed)
        result, saved, seen = self.invoke()
        self.assertEqual(result['status'], 'PASS', saved)
        self.assertEqual(saved['mode'], 'health-ready-concurrent-trace')
        self.assertEqual(saved['scope'], 'READY_CONCURRENT_CAPTURE_NOT_FIELD_PERFORMANCE')
        self.assertTrue(seen[0].ready_stacks)
        self.assertFalse(seen[0].cpu_samples)
        contract = json.loads(Path(seen[0].trace_contract_path).read_bytes())
        self.assertEqual(contract['scope'], runner.trace.READY_CONCURRENT_SCOPE)
        self.assertEqual(contract['schema'], 'sfl-health-ready-concurrent-contract-v1')

    def test_1030_tampered_archived_payload_prevents_collection(self):
        self.request['candidate_commit'] = runner.binding.CANDIDATE_1030.commit
        self.request['spec']['candidate_commit'] = runner.binding.CANDIDATE_1030.commit
        result, saved, seen = self.invoke(mutate=lambda: (self.archive/'candidate-payload.json').write_text('{}'))
        self.assertEqual((result['status'], seen), ('FAIL', []))
        self.assertIn('health-archived-input-pin:candidate-payload.json', str(saved['errors']))

    def prepare_python(self):
        self.request.update(schema=runner.PYTHON_SCHEMA, duration_seconds=6,
                            candidate_commit=runner.binding.CANDIDATE_1030.commit)
        self.request['spec']['candidate_commit'] = runner.binding.CANDIDATE_1030.commit
        self.request['spec']['reference_sha256'] = runner.binding.REFERENCE_SHA_1030
        shutil.copyfile(os.environ['SFL_PYTHON_STREAM_TOOL'], self.archive/'sfl_qpc_reader.exe')

    def test_python_request_locks_package_reader_and_keeps_distinct_contract(self):
        self.prepare_python()
        runner.validate_request(self.request)
        result, saved, seen = self.invoke()
        self.assertEqual(result['status'], 'PASS', saved)
        self.assertEqual(saved['mode'], 'python-health-trace')
        self.assertEqual(saved['archived_inputs']['sfl_qpc_reader.exe'], runner.trace.python_stream.TOOL_FACT)
        contract = json.loads(Path(seen[0].trace_contract_path).read_bytes())
        self.assertEqual(contract['schema'], 'sfl-python-health-trace-contract-v1')
        self.assertEqual(contract['scope'], runner.trace.PYTHON_SCOPE)

    def test_python_reader_pin_failure_prevents_trace_or_collection(self):
        self.prepare_python()
        result, saved, seen = self.invoke(mutate=lambda: (self.archive/'sfl_qpc_reader.exe').write_bytes(b'wrong'))
        self.assertEqual((result['status'], seen), ('FAIL', []))
        self.assertIn('health-python-tool-pin', str(saved['errors']))
        self.assertFalse((self.output/'session/trace-channel').exists())

    def test_baseline_keeps_same_locked_reader_package_without_enabling_observer(self):
        self.prepare_python()
        self.request['schema'] = runner.PYTHON_BASELINE_SCHEMA
        runner.validate_request(self.request)
        result, saved, seen = self.invoke()
        self.assertEqual(result['status'], 'PASS', saved)
        self.assertEqual(saved['mode'], 'python-health-baseline-trace')
        self.assertEqual(saved['scope'], 'PYTHON_HTTP_BASELINE_NOT_FIELD_PERFORMANCE')
        self.assertEqual(saved['archived_inputs']['sfl_qpc_reader.exe'], runner.trace.python_stream.TOOL_FACT)
        self.assertFalse(seen[0].python_frames)
        self.assertTrue(seen[0].python_baseline)
        contract = json.loads(Path(seen[0].trace_contract_path).read_bytes())
        self.assertEqual(contract['schema'], 'sfl-python-health-baseline-contract-v1')
        self.assertEqual(contract['scope'], runner.trace.PYTHON_BASELINE_SCOPE)
        self.assertFalse(saved['promotion_allowed'])

    def test_baseline_reader_pin_failure_still_prevents_collection(self):
        self.prepare_python()
        self.request['schema'] = runner.PYTHON_BASELINE_SCHEMA
        result, saved, seen = self.invoke(mutate=lambda: (self.archive/'sfl_qpc_reader.exe').write_bytes(b'wrong'))
        self.assertEqual((result['status'], seen), ('FAIL', []))
        self.assertIn('health-python-tool-pin', str(saved['errors']))
        self.assertFalse((self.output/'session/trace-channel').exists())

    def test_baseline_rejects_old_candidate_duration_and_hidden_options(self):
        self.prepare_python()
        self.request['schema'] = runner.PYTHON_BASELINE_SCHEMA
        for name in ('python_baseline', 'python_frames', 'outlier_capture'):
            changed = deepcopy(self.request)
            changed['spec'][name] = True
            with self.assertRaisesRegex(ValueError, 'health-request-spec-members'):
                runner.validate_request(changed)
        for duration in (0, 30, 900, True, 6.0):
            with self.assertRaises(ValueError):
                runner.validate_request(dict(self.request, duration_seconds=duration))
        with self.assertRaisesRegex(ValueError, 'health-python-candidate'):
            runner.validate_request(dict(self.request, candidate_commit=runner.binding.CANDIDATE_1029.commit))

    def test_python_request_forbids_extra_options_duration_and_old_candidate(self):
        self.prepare_python()
        for name, value in [('tool', 'C:/other.exe'), ('python_frames', True), ('outlier_capture', True)]:
            changed = deepcopy(self.request)
            changed['spec'][name] = value
            with self.assertRaisesRegex(ValueError, 'health-request-spec-members'): runner.validate_request(changed)
        for duration in (900, 30, True, 6.0):
            with self.assertRaises(ValueError): runner.validate_request(dict(self.request, duration_seconds=duration))
        with self.assertRaisesRegex(ValueError, 'health-python-candidate'):
            runner.validate_request(dict(self.request, candidate_commit=runner.binding.CANDIDATE_1029.commit))

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
