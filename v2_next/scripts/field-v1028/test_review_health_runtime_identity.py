"""Synthetic mismatch cases and actual locked-file CLI; never server QA."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import review_health_runtime_identity as reviewer
from test_review_health_runtime_close import fixture as close_fixture, raw


ROOT = Path(os.environ['SFL_RUNTIME_IDENTITY_REVIEW_TEST_ROOT'])


def seal(files):
    files = deepcopy(files)
    files.pop('result.json', None)
    files['result.json'] = raw(dict(schema='sfl-health-runtime-identity-result-v1',
        status='RUNNING_IDENTITY_CAPTURED_REQUIRES_REVIEW', request_sha256=reviewer.sha(files['request.json']),
        files={k: dict(bytes=len(v), sha256=reviewer.sha(v)) for k, v in files.items()},
        configuration_changed=False, application_started=False, application_shutdown_performed=False,
        actual_process_exit_observed=False, full_backup_created=False, promotion_allowed=False,
        field_gate='NOT_EVALUATED', release_gate='HOLD'))
    return files


def fixture():
    files = {k: v for k, v in close_fixture().items() if k in reviewer.MEMBERS}
    request = json.loads(files['request.json'])
    request.update(physical_boundary='NOT_TESTED', release_gate='HOLD', promotion_allowed=False)
    files['request.json'] = raw(request)
    return seal(files)


class IdentityReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.files = fixture()

    def invoke(self, exit_code=0):
        return reviewer.review_bytes(self.files, reviewer.sha(self.files['request.json']), exit_code)

    def mutate(self, name, action):
        value = json.loads(self.files[name])
        action(value)
        self.files[name] = raw(value)
        self.files = seal(self.files)

    def test_capture_identity_not_liveness_or_release(self):
        value = self.invoke()
        self.assertEqual(value['backend']['pid'], 101)
        self.assertEqual(value['main']['pid'], 100)
        self.assertEqual(value['current_liveness'], 'REQUIRES_EXECUTION_TIME_RECHECK')
        self.assertEqual(value['field_gate'], 'NOT_EVALUATED')
        self.assertEqual(value['release_gate'], 'HOLD')
        self.assertFalse(value['actual_process_exit_observed'])
        self.assertFalse(value['promotion_allowed'])

    def test_failed_boolean_launch_and_unpinned_bytes_rejected(self):
        for value in (1, True, False):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'launcher-nonzero'):
                self.invoke(value)
        self.files['config.ini'] += b'changed'
        with self.assertRaisesRegex(ValueError, 'file-pin:config.ini'):
            self.invoke()

    def test_resealed_config_or_stale_csv_rejected(self):
        self.files['config.ini'] += b'changed'
        self.files = seal(self.files)
        with self.assertRaisesRegex(ValueError, 'config-pin'):
            self.invoke()
        self.files = fixture()
        self.mutate('health-before.json', lambda v: v['spot_temperature']['v2_4_operational'].update(
            current_v2_csv_file_name='Factory_Integrated_Log_v2_20261016_000000.csv'))
        with self.assertRaisesRegex(ValueError, 'health-generation'):
            self.invoke()

    def test_native_and_cim_generations_parents_and_listener_rejected(self):
        cases = [
            (lambda v: v['processes'][1].update(created_filetime=True), 'native-handle-time'),
            (lambda v: v['processes'][1].update(created_filetime=v['processes'][1]['created_filetime'] + 10000), 'native-time-representations'),
            (lambda v: v['processes'].append(v['processes'][1]), 'duplicate-native-pid'),
            (lambda v: v['observation']['processes'][1].update(CreationDate='2026-10-15T12:00:00+00:00'), 'cim-native-creation'),
            (lambda v: v['observation']['processes'][1].update(ParentProcessId=99), 'cim-parent'),
            (lambda v: v['observation']['listeners'][0].update(OwningProcess=100), 'listener-owner'),
            (lambda v: v['processes'][1].update(exe=reviewer.MAIN), 'native-path'),
        ]
        for action, reason in cases:
            self.files = fixture()
            self.mutate('runtime-before.json', action)
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self.invoke()

    def test_dotnet_cim_and_submillisecond_native_precision_preserved(self):
        def change(v):
            p = v['processes'][1]
            p.update(created_filetime=p['created_filetime'] + 1234,
                     created=p['created'] + .0001234, created_at_utc='2026-10-15T12:00:01.0001234+00:00')
            for i, item in enumerate(v['observation']['processes']):
                item['CreationDate'] = f"/Date({int(v['processes'][i]['created'] * 1000)}+0900)/"
        self.mutate('runtime-before.json', change)
        self.assertEqual(self.invoke()['backend']['created_filetime'] % 10000, 1234)

    def test_false_promotion_and_exit_claims_rejected(self):
        for key, value in (('promotion_allowed', True), ('actual_process_exit_observed', True),
                           ('application_shutdown_performed', True), ('field_gate', 'PASS')):
            self.files = fixture()
            result = json.loads(self.files['result.json'])
            result[key] = value
            self.files['result.json'] = raw(result)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.invoke()
        self.files = fixture()
        self.mutate('request.json', lambda v: v.update(promotion_allowed=True))
        with self.assertRaisesRegex(ValueError, 'request-scope'):
            self.invoke()

    def test_duplicate_json_rejected(self):
        self.files['runtime-before.json'] = b'{"main_pid":100,"main_pid":101}'
        self.files = seal(self.files)
        with self.assertRaises(ValueError):
            self.invoke()

    def test_actual_cli_external_pins_and_membership(self):
        directory = ROOT / 'captured-fixture'
        directory.mkdir()
        for name, value in self.files.items():
            (directory / name).write_bytes(value)
        result_sha, request_sha = (reviewer.sha(self.files[name]) for name in ('result.json', 'request.json'))
        command = [sys.executable, '-W', 'error', str(Path(reviewer.__file__)), '--source', str(directory),
                   '--result-sha256', result_sha, '--request-sha256', request_sha, '--launch-exit', '0',
                   '--output', str(ROOT / 'cli-reviewed.json')]
        run = subprocess.run(command, capture_output=True, text=True, timeout=30)
        (ROOT / 'cli.stdout.log').write_text(run.stdout, encoding='utf-8')
        (ROOT / 'cli.stderr.log').write_text(run.stderr, encoding='utf-8')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(json.loads(run.stdout)['files_verified'], 5)
        for result_pin, request_pin, reason in ((result_sha, '0'*64, 'external-request-pin'),
                                               ('0'*64, request_sha, 'console-result-pin')):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                reviewer.review(directory, result_pin, request_pin, 0)
        bad_command = list(command)
        bad_command[bad_command.index('--result-sha256') + 1] = '0' * 64
        bad_command[-1] = str(ROOT / 'cli-rejected.json')
        bad = subprocess.run(bad_command, capture_output=True, text=True, timeout=30)
        self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
        self.assertEqual(json.loads(bad.stdout)['status'], 'HOLD')
        (directory / 'extra.txt').write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'result-directory-membership'):
            reviewer.review(directory, result_sha, request_sha, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
