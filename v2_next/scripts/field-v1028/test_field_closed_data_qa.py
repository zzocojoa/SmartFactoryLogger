"""Native fixed-EXE data pipeline and owned-process fault checks, on new copies."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import psutil

import field_closed_data_qa as qa
import field_csv_inputs as inputs
from test_field_observation import configuration_snapshot


ROOT = Path(os.environ['SFL_DATA_QA_TEST_ROOT'])
ARCHIVE = Path(os.environ['SFL_CSV_INPUT_ARCHIVE'])
CSV_EXE = Path(os.environ['SFL_CSV_INPUT_EXE'])
IMAGE_EXE = Path(os.environ['SFL_IMAGE_INPUT_EXE'])


def fact(path):
    with path.open('rb') as stream: return inputs.file_fact(stream)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


FAULT_SCRIPT = '''import json, os, subprocess, sys, time
from pathlib import Path
mode, marker = sys.argv[1], Path(sys.argv[2])
if mode == 'orphan':
    subprocess.Popen([sys.executable, '-S', __file__, 'hang', str(marker)], creationflags=subprocess.CREATE_NO_WINDOW)
    end=time.monotonic()+5
    while not marker.exists() and time.monotonic()<end: time.sleep(.02)
    raise SystemExit(0)
marker.write_text(json.dumps({'pid':os.getpid()}))
if mode == 'exit': raise SystemExit(7)
if mode in ('output', 'fast-output'):
    print('x'*4096, flush=True)
if mode == 'fast-output': raise SystemExit(0)
time.sleep(90)
'''


class ClosedDataTests(unittest.TestCase):
    counter = 0

    @classmethod
    def setUpClass(cls):
        ROOT.mkdir()
        assert fact(CSV_EXE)['sha256'] == inputs.CSV_EXE_SHA
        assert fact(IMAGE_EXE)['sha256'] == qa.IMAGE_EXE_SHA

    def setUp(self):
        type(self).counter += 1
        self.folder = ROOT / f't{self.counter:02d}'
        self.folder.mkdir()
        (self.folder / 'test-name.txt').write_text(self._testMethodName, encoding='utf-8')

    def prepare(self, label='a', restart=False):
        folder = self.folder / label
        data = folder / 'data'; data.mkdir(parents=True)
        stage, stamp = ('I5-candidate-restart', '20261013_142706') if restart else ('I4-candidate-runtime', '20261013_142551')
        baseline = json.loads((ARCHIVE / stage / 'data-after.json').read_bytes())
        source = ARCHIVE / stage / 'closed-data'
        roles = dict(v1=f'Factory_Integrated_Log_{stamp}.csv', v2=f'Factory_Integrated_Log_v2_{stamp}.csv',
                     metadata=f'Factory_Integrated_Log_v2_{stamp}.metadata.json', observation='spot_observation_fact.csv',
                     image='spot_image_fact.csv', image_final='spot_image_fact_manifest.final.json')
        images = {}
        for name, expected in baseline.items():
            if name not in roles.values() and not name.startswith('spot_images/'): continue
            expected = dict(bytes=expected['bytes'], sha256=expected['sha256'].lower())
            self.assertEqual(fact(source / name), expected)
            target = data / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, target)
            self.assertEqual(fact(target), expected)
            if name.startswith('spot_images/'): images[name] = expected
        return folder, data, roles, images

    def bind(self, folder, data, roles):
        return inputs.CsvInputs(data, folder / 'bound', roles, {n: fact(data / n) for n in roles.values()}, CSV_EXE)

    def reference(self, folder, data, roles, synthetic, *, disabled_low_signal=False):
        metadata = json.loads((data / roles['metadata']).read_bytes())
        expected = dict(schema=inputs.shutdown.SCHEMA, build_git_commit=inputs.binding.BUILD,
            logger_service_instance_id=metadata['schema_metadata']['logger_service_instance_id'],
            spot_service_instance_id='11111111-1111-4111-8111-111111111111', schema_version='2.5.2',
            csv_file_name=roles['v2'], minimum_sample_seq=metadata['csv_closeout']['final_persisted_sample_seq'],
            health_body_sha256='a' * 64, observed_at=datetime.now(timezone.utc).isoformat())
        snapshot = configuration_snapshot()
        schema = 'sfl-field-configuration-reference-v1'
        approval = {}
        if disabled_low_signal:
            snapshot.update(low_signal_comparator_configured_verified=False, low_signal_comparator_verified=False)
            fingerprint = inputs.configuration.canonical_fingerprint(snapshot)
            snapshot.update(spot_config_fingerprint_sha256=fingerprint, spot_config_verified_fingerprint_sha256=fingerprint)
            schema = inputs.configuration.DISABLED_SCHEMA
            approval['field_sequence_approval_sha256'] = inputs.configuration.FIELD_SEQUENCE_APPROVAL_SHA
        reference = folder / 'synthetic-reference.json'
        save(reference, dict(schema=schema, **approval,
            profile_approval_sha256=inputs.configuration.PROFILE_APPROVAL_SHA, snapshot=snapshot,
            classification='SYNTHETIC_TEST_NOT_FIELD_APPROVAL'))
        if synthetic:
            metadata['spot_configuration_snapshot'] = snapshot
            save(data / roles['metadata'], metadata)
        return expected, reference, fact(reference)['sha256']

    def test_actual_i4_i5_both_validators_and_all_images(self):
        for restart in (False, True):
            folder, data, roles, images = self.prepare('i5' if restart else 'i4', restart)
            self.assertEqual(len(images), 199 if restart else 133)
            bound = self.bind(folder, data, roles)
            with bound:
                result = qa.check_bound_data(bound, images, IMAGE_EXE, folder / 'qa')
                self.assertEqual(result['data_checks_status'], 'PASS', result)
                for name in ('csv', 'image'):
                    self.assertEqual(result[name]['exit_code'], 0)
                    self.assertEqual(result[name]['job_after_cleanup']['active_processes'], 0)
                    self.assertFalse(result[name]['termination_requested'])
                    self.assertEqual(result[name]['outputs']['stderr.log']['bytes'], 0)
            self.assertEqual(bound.receipt['input_binding_status'], 'PASS')
            self.assertFalse(result['promotion_allowed'])
            save(folder / 'csv-binding.json', bound.receipt)

    def test_full_pipeline_synthetic_reference_pass_is_not_field_approval(self):
        folder, data, roles, images = self.prepare()
        expected, reference, sha = self.reference(folder, data, roles, True)
        result = qa.validate_closed_data(self.bind(folder, data, roles), images, IMAGE_EXE,
                                         folder / 'qa', expected, reference, sha)
        self.assertEqual(result['closed_data_status'], 'PASS', result)
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertFalse(result['promotion_allowed'])

    def test_disabled_trial_both_validators_keep_physical_and_release_pending(self):
        folder, data, roles, images = self.prepare()
        expected, reference, sha = self.reference(folder, data, roles, True, disabled_low_signal=True)
        result = qa.validate_closed_data(self.bind(folder, data, roles), images, IMAGE_EXE,
                                         folder / 'qa', expected, reference, sha)
        self.assertEqual(result['closed_data_status'], 'PASS', result)
        self.assertEqual(result['validation_scope'], inputs.configuration.DISABLED_SCOPE)
        self.assertEqual(result['physical_device_gate'], 'NOT_TESTED')
        self.assertEqual(result['formal_qa_gate'], 'HOLD')
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertFalse(result['promotion_allowed'])

    def test_actual_attestation_failure_prevents_command_start(self):
        folder, data, roles, images = self.prepare()
        expected, reference, sha = self.reference(folder, data, roles, False)
        result = qa.validate_closed_data(self.bind(folder, data, roles), images, IMAGE_EXE,
                                         folder / 'qa', expected, reference, sha)
        self.assertEqual(result['closed_data_status'], 'FAIL')
        self.assertEqual(result['csv_inputs']['shutdown_review']['identity_status'], 'PASS')
        self.assertEqual(result['csv_inputs']['shutdown_review']['configuration_review']['status'], 'FAIL')
        self.assertFalse((folder / 'qa/checks').exists())

    def test_image_content_failure_is_not_overridden_by_csv_pass(self):
        folder, data, roles, images = self.prepare()
        name = next(iter(images))
        (data / name).write_bytes(b'not a decodable image')
        images[name] = fact(data / name)  # Copy integrity correct; recorded image content is wrong.
        bound = self.bind(folder, data, roles)
        with bound:
            result = qa.check_bound_data(bound, images, IMAGE_EXE, folder / 'qa')
        self.assertEqual(result['csv']['exit_code'], 0)
        self.assertEqual(result['image']['exit_code'], 1)
        self.assertEqual(result['data_checks_status'], 'FAIL')

    def test_csv_failure_is_not_overridden_by_image_pass(self):
        folder, data, roles, images = self.prepare()
        path = data / roles['image_final']
        value = json.loads(path.read_bytes()); value['sha256'] = '0' * 64; save(path, value)
        bound = self.bind(folder, data, roles)
        with bound: result = qa.check_bound_data(bound, images, IMAGE_EXE, folder / 'qa')
        self.assertEqual(result['csv']['exit_code'], 1)
        self.assertEqual(result['image']['exit_code'], 0)
        self.assertEqual(result['data_checks_status'], 'FAIL')

    def test_inventory_missing_extra_bad_hash_and_exe_rejected(self):
        for mode in ('missing', 'extra', 'hash', 'exe'):
            folder, data, roles, images = self.prepare(mode)
            if mode == 'missing': (data / next(iter(images))).rename(folder / 'removed-image.jpg')
            if mode == 'extra': (data / 'spot_images/undeclared.jpg').write_bytes(b'x')
            if mode == 'hash': images[next(iter(images))]['sha256'] = '0' * 64
            exe = IMAGE_EXE
            if mode == 'exe': exe = folder / 'wrong.exe'; exe.write_bytes(b'wrong')
            bound = self.bind(folder, data, roles)
            with bound: result = qa.check_bound_data(bound, images, exe, folder / 'qa')
            self.assertEqual(result['data_checks_status'], 'FAIL', mode)
            self.assertNotIn('csv', result)

    def test_locks_and_new_image_during_context_fail_closeout(self):
        folder, data, roles, images = self.prepare()
        bound = self.bind(folder, data, roles)
        with bound:
            context = qa.ImageInputs(bound, images, IMAGE_EXE)
            with self.assertRaisesRegex(ValueError, 'image-inventory-set'):
                with context:
                    target = data / next(iter(images))
                    with self.assertRaises(PermissionError): target.write_bytes(b'changed')
                    with self.assertRaises(PermissionError): target.rename(folder / 'moved.jpg')
                    (data / 'spot_images/new-image.jpg').write_bytes(b'new')
            self.assertEqual(context.receipt['input_binding_status'], 'FAIL')

    def test_output_pass_claim_with_wrong_consumed_inventory_is_rejected(self):
        folder, data, roles, images = self.prepare()
        bound = self.bind(folder, data, roles)
        with bound: result = qa.check_bound_data(bound, images, IMAGE_EXE, folder / 'qa')
        self.assertEqual(result['data_checks_status'], 'PASS')
        output = folder / 'qa/images'
        tamper = folder / 'tampered'; shutil.copytree(output, tamper)
        p = tamper / 'inventory-after.jsonl'
        rows = p.read_text(encoding='utf-8').splitlines()
        row = json.loads(rows[0]); row['sha256'] = 'f' * 64; rows[0] = json.dumps(row)
        p.write_text('\n'.join(rows)+'\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'inventory-fact'):
            qa.verify_image_outputs(tamper, images, fact(data / roles['image'])['sha256'])

    def test_context_close_error_cannot_leave_closed_data_pass(self):
        folder, data, roles, images = self.prepare()
        expected, reference, sha = self.reference(folder, data, roles, True)
        bound = self.bind(folder, data, roles)
        def fail_close(): raise OSError('close fault')
        bound.stack.callback(fail_close)
        result = qa.validate_closed_data(bound, images, IMAGE_EXE, folder / 'qa', expected, reference, sha)
        self.assertEqual(result['checks']['data_checks_status'], 'PASS')
        self.assertEqual(result['closed_data_status'], 'FAIL')
        self.assertEqual(result['csv_inputs']['input_binding_status'], 'FAIL')

    def fault_command(self, mode):
        script = self.folder / 'fixture.py'; script.write_text(FAULT_SCRIPT, encoding='utf-8')
        marker = self.folder / 'pid.json'
        return [sys._base_executable, '-S', str(script), mode, str(marker)], marker

    def assert_marker_process_gone(self, marker):
        pid = json.loads(marker.read_bytes())['pid']
        self.assertFalse(psutil.pid_exists(pid), pid)

    def test_command_timeout_terminates_owned_tree(self):
        command, marker = self.fault_command('hang')
        result = qa.run_command(command, self.folder / 'run', timeout=3)
        self.assertEqual(result['process_status'], 'FAIL')
        self.assertTrue(result['termination_requested'])
        self.assertEqual(result['job_after_cleanup']['active_processes'], 0)
        self.assertNotEqual(result['worker_exit_code'], 0)
        self.assertIsNotNone(result['worker_exit_code'])
        self.assert_marker_process_gone(marker)

    def test_orphan_is_failure_and_unrelated_owned_fixture_survives(self):
        unrelated = subprocess.Popen([sys._base_executable, '-S', '-c', 'import time; time.sleep(90)'],
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            command, marker = self.fault_command('orphan')
            result = qa.run_command(command, self.folder / 'run')
            self.assertEqual(result['process_status'], 'FAIL')
            self.assertTrue(result['termination_requested'])
            self.assert_marker_process_gone(marker)
            self.assertIsNone(unrelated.poll())
        finally:
            unrelated.terminate(); unrelated.wait(timeout=10)

    def test_nonzero_consumer_is_preserved_as_actual_exit(self):
        command, marker = self.fault_command('exit')
        result = qa.run_command(command, self.folder / 'run')
        self.assertEqual(result['process_status'], 'PASS', result)
        self.assertEqual(result['exit_code'], 7)
        self.assertFalse(result['termination_requested'])
        self.assert_marker_process_gone(marker)

    def test_output_budget_terminates_only_test_tree(self):
        command, marker = self.fault_command('output')
        with patch.object(qa, 'COMMAND_OUTPUT_LIMIT', 1024):
            result = qa.run_command(command, self.folder / 'run')
        self.assertEqual(result['process_status'], 'FAIL')
        self.assertIn('command-output-budget', str(result['errors']))
        self.assert_marker_process_gone(marker)

    def test_completed_command_cannot_exceed_final_output_budget(self):
        command, marker = self.fault_command('fast-output')
        original_alive = qa.multiprocessing.process.BaseProcess.is_alive
        def delayed_parent_check(process):
            process.join(10)  # Model a descheduled parent; let the real child finish first.
            return original_alive(process)
        with patch.object(qa, 'COMMAND_OUTPUT_LIMIT', 1024), patch.object(
                qa.multiprocessing.process.BaseProcess, 'is_alive', delayed_parent_check):
            result = qa.run_command(command, self.folder / 'run')
        self.assertEqual(result['process_status'], 'FAIL')
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['worker_exit_code'], 0)
        self.assertFalse(result['termination_requested'])
        self.assertIn('command-final-output-budget', str(result['errors']))
        self.assert_marker_process_gone(marker)

    def test_supervisor_death_kills_its_job_descendants(self):
        command, marker = self.fault_command('hang')
        script = self.folder / 'supervisor.py'
        script.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0, '+repr(str(Path(qa.__file__).parent))+')\n'
            'import field_closed_data_qa as qa\nif __name__ == "__main__":\n'
            '    qa.run_command(sys.argv[1:-1], Path(sys.argv[-1]), timeout=60)\n', encoding='utf-8')
        with (self.folder / 'supervisor.log').open('xb') as log:
            process = subprocess.Popen([sys.executable, str(script), *command, str(self.folder / 'run')],
                stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline = time.monotonic() + 15
                while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(marker.exists(), 'fault child did not start')
                pid = json.loads(marker.read_bytes())['pid']
                self.assertTrue(psutil.pid_exists(pid))
                descendants = [child.pid for child in psutil.Process(process.pid).children(recursive=True)]
                self.assertIn(pid, descendants)
                self.assertGreaterEqual(len(descendants), 2)
                save(self.folder / 'supervisor-death.json', dict(supervisor_pid=process.pid,
                                                               child_pid=pid, descendants=descendants))
                process.terminate(); process.wait(timeout=10)
                deadline = time.monotonic() + 10
                while any(psutil.pid_exists(p) for p in descendants) and time.monotonic() < deadline: time.sleep(.05)
                self.assertFalse(any(psutil.pid_exists(p) for p in descendants))
                self.assert_marker_process_gone(marker)
                self.assertFalse((self.folder / 'run/process-receipt.json').exists())
            finally:
                if process.poll() is None:
                    process.terminate(); process.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
