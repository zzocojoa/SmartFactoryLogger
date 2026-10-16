"""Synthetic contracts and actual locked-file/CLI tests, not server QA."""
from copy import deepcopy
from datetime import datetime
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import review_health_runtime_close as reviewer


LOGGER = 'c7bad677-3827-4da6-b4a0-920f9e5629e6'
CSV = 'Factory_Integrated_Log_v2_20261015_212251.csv'
META = CSV.replace('.csv', '.metadata.json')
ROOT = Path(os.environ['SFL_RUNTIME_CLOSE_REVIEW_TEST_ROOT'])


def raw(value):
    return json.dumps(value, allow_nan=False).encode()


def identity(pid, second, exe):
    stamp = f'2026-10-15T12:00:0{second}+00:00'
    epoch = int(datetime.fromisoformat(stamp).timestamp())
    return dict(pid=pid, created_at_utc=stamp, created_filetime=epoch * 10**7 + reviewer.FILETIME_EPOCH,
                created=float(epoch), exe=exe, native_handle_retained=True)


def fixture():
    request = dict(schema='sfl-health-runtime-close-request-v1', candidate_commit=reviewer.BUILD,
                   logger_service_instance_id=LOGGER, csv_name=CSV, config_sha256=reviewer.sha(b'[fixture]\nx=1\n'))
    processes = [identity(100, 0, reviewer.MAIN), identity(101, 1, reviewer.BACKEND)]
    cim = [dict(ProcessId=p['pid'], ParentProcessId=99 if p['pid'] == 100 else 100,
                Name='smart-factory.exe' if p['pid'] == 100 else 'SmartFactoryBackend.exe',
                ExecutablePath=p['exe'], CreationDate=p['created_at_utc']) for p in processes]
    before = dict(observed_at_utc='2026-10-15T12:00:03+00:00', main_pid=100, backend_pid=101,
                  processes=processes, observation=dict(processes=cim,
                    listeners=[dict(LocalAddress='127.0.0.1', LocalPort=8000, OwningProcess=101)]))
    health = dict(running=True, mode='REAL', app_version='1.0.29', executable_path=reviewer.BACKEND,
                  spot_temperature=dict(build_git_commit=reviewer.BUILD, v2_4_operational=dict(
                      logger_service_instance_id=LOGGER, logger_service_started_at='2026-10-15T12:00:02+00:00',
                      current_v2_csv_file_name=CSV, rows_total=1)))
    metadata = dict(schema_metadata=dict(git_commit=reviewer.BUILD, logger_service_instance_id=LOGGER),
                    csv_closeout=dict(finalized=True, closeout_reason='shutdown', csv_file_name=CSV,
                                      logger_service_instance_id=LOGGER, final_persisted_sample_seq=3))
    files = {'request.json': raw(request), 'health-before.json': raw(health), 'runtime-before.json': raw(before),
             'runtime-after.json': raw(dict(processes=[], listeners=[])), 'config.ini': b'[fixture]\nx=1\n',
             META: raw(metadata), 'process-exits.json': raw([dict(identity=p, actual_exit_code=0,
                 exit_at_utc='2026-10-15T12:00:04+00:00', forced_termination=False) for p in processes]),
             CSV: ('sample_seq,logger_service_instance_id,temperature_output_status,temperature_unavailable_reason\n'
                   f'1,{LOGGER},startup_pending,startup_pending\n2,{LOGGER},stale,stale_observation\n3,{LOGGER},valid,\n').encode()}
    return seal(files)


def seal(files):
    files = deepcopy(files)
    files.pop('result.json', None)
    files['result.json'] = raw(dict(schema='sfl-health-runtime-close-result-v1', status='CLOSED_RUNTIME_CAPTURED_REQUIRES_REVIEW',
        request_sha256=reviewer.sha(files['request.json']), files={k: dict(bytes=len(v), sha256=reviewer.sha(v)) for k, v in files.items()},
        configuration_changed=False, application_started=False, forced_termination=False, full_backup_created=False,
        promotion_allowed=False, release_gate='HOLD', file_content_qa='NOT_EVALUATED'))
    return files


def rollover_fixture():
    files = fixture()
    request = json.loads(files['request.json'])
    request.update(schema='sfl-health-runtime-close-request-v2', csv_first_sample_seq=18573)
    files['request.json'] = raw(request)
    health = json.loads(files['health-before.json'])
    health['spot_temperature']['v2_4_operational'].update(rows_total=18574, last_sample_seq=18574)
    files['health-before.json'] = raw(health)
    metadata = json.loads(files[META])
    metadata['csv_closeout']['final_persisted_sample_seq'] = 18575
    files[META] = raw(metadata)
    files[CSV] = files[CSV].replace(b'\n1,', b'\n18573,').replace(b'\n2,', b'\n18574,').replace(b'\n3,', b'\n18575,')
    return seal(files)


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.files = fixture()

    def invoke(self, files=None, exit_code=0):
        files = self.files if files is None else files
        return reviewer.review_bytes(files, reviewer.sha(files['request.json']), exit_code)

    def mutate_json(self, name, action):
        value = json.loads(self.files[name])
        action(value)
        self.files[name] = raw(value)
        self.files = seal(self.files)

    def test_positive_preserves_all_unverified_gates_and_counts(self):
        result = self.invoke()
        self.assertEqual(result['status'], 'LIMITED_RUNTIME_CLOSE_RECEIPTS_VERIFIED')
        self.assertEqual(result['csv_status_counts'], dict(startup_pending=1, stale=1, valid=1))
        self.assertEqual(result['native_processes'], 2)
        self.assertEqual(result['image_fact_and_byte_qa'], 'NOT_EVALUATED')
        self.assertEqual(result['configuration_attestation'], 'NOT_EVALUATED')
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertFalse(result['promotion_allowed'])

    def test_rollover_pinned_start_and_session_counters(self):
        result = self.invoke(rollover_fixture())
        self.assertEqual((result['csv_rows'], result['csv_first_sample_seq'], result['csv_last_sample_seq']), (3, 18573, 18575))
        self.assertEqual(result['prior_csv_content'], 'NOT_EVALUATED')

    def test_rollover_missing_invalid_and_legacy_override_start_rejected(self):
        for value in (None, True, 0, -1, 1.5, '18573'):
            self.files = rollover_fixture()
            self.mutate_json('request.json', lambda v: v.update(csv_first_sample_seq=value))
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'request-first-sequence'):
                self.invoke()
        self.files = rollover_fixture()
        self.mutate_json('request.json', lambda v: v.pop('csv_first_sample_seq'))
        with self.assertRaisesRegex(ValueError, 'request-first-sequence'):
            self.invoke()
        self.files = fixture()
        self.mutate_json('request.json', lambda v: v.update(csv_first_sample_seq=1))
        with self.assertRaisesRegex(ValueError, 'legacy-first-sequence-not-configurable'):
            self.invoke()

    def test_rollover_truncated_head_gap_duplicate_and_logger_rejected(self):
        original = rollover_fixture()
        lines = original[CSV].splitlines(keepends=True)
        for changed in (b''.join(lines[:1]+lines[2:]), b''.join(lines[:2]+lines[3:]),
                        b''.join(lines[:2]+lines[1:]), original[CSV].replace(LOGGER.encode(), b'x'*36, 1)):
            files = dict(original, **{CSV: changed})
            with self.subTest(changed=changed[-50:]), self.assertRaisesRegex(ValueError, 'csv-sequence-generation'):
                self.invoke(seal(files))

    def test_rollover_final_and_before_sequence_limits(self):
        self.files = rollover_fixture()
        self.mutate_json(META, lambda v: v['csv_closeout'].update(final_persisted_sample_seq=3))
        with self.assertRaisesRegex(ValueError, 'csv-final-count'):
            self.invoke()
        for value in (True, 18572, 18576):
            self.files = rollover_fixture()
            self.mutate_json('health-before.json', lambda v: v['spot_temperature']['v2_4_operational'].update(last_sample_seq=value))
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'csv-before-sequence'):
                self.invoke()

    def test_stream_reads_are_bounded_and_byte_limits_enforced(self):
        class BoundedStream(io.BytesIO):
            def read(self, size=-1):
                self_assert.assertTrue(0 < size <= reviewer.CHUNK_BYTES)
                return super().read(size)
        self_assert = self
        with BoundedStream(b'a'*(reviewer.CHUNK_BYTES+10)) as stream:
            fact = reviewer.csv_fact(stream, reviewer.STREAM_CSV_LIMIT)
            self.assertEqual(fact['bytes'], reviewer.CHUNK_BYTES+10)
            self.assertEqual(stream.tell(), 0)
            with self.assertRaisesRegex(ValueError, 'file-byte-budget'):
                reviewer.csv_fact(stream, 10)

    def test_malformed_csv_utf8_and_long_line_rejected(self):
        for tail, error in ((b'\xff', UnicodeError), (b'"unterminated', csv.Error),
                            (b'x'*(reviewer.CHUNK_BYTES+1), ValueError)):
            files = fixture()
            files[CSV] += tail
            with self.subTest(error=error), self.assertRaises(error):
                self.invoke(seal(files))

    def test_actual_large_locked_csv_cli_and_legacy_budget(self):
        directory = ROOT/'large'
        directory.mkdir()
        files = rollover_fixture()
        rows, first = 2200, 18573
        metadata = json.loads(files[META])
        metadata['csv_closeout']['final_persisted_sample_seq'] = first + rows - 1
        files[META] = raw(metadata)
        files = seal(files)
        for name, data in files.items():
            if name != CSV:
                (directory/name).write_bytes(data)
        digest, total = hashlib.sha256(), 0
        with (directory/CSV).open('xb') as output:
            header = b'sample_seq,logger_service_instance_id,temperature_output_status,temperature_unavailable_reason,padding\n'
            output.write(header);digest.update(header);total += len(header)
            for seq in range(first, first+rows):
                row = f'{seq},{LOGGER},valid,,'.encode()+b'x'*65536+b'\n'
                output.write(row);digest.update(row);total += len(row)
        self.assertGreater(total, reviewer.LEGACY_CSV_LIMIT)
        manifest = json.loads(files['result.json'])
        manifest['files'][CSV] = dict(bytes=total, sha256=digest.hexdigest())
        result_bytes = raw(manifest)
        (directory/'result.json').write_bytes(result_bytes)
        request_sha = reviewer.sha(files['request.json'])
        result_sha = reviewer.sha(result_bytes)
        original = reviewer.csv_fact
        def check_lock(stream, limit):
            with self.assertRaises(OSError):
                with (directory/CSV).open('r+b'):
                    pass
            return original(stream, limit)
        with patch.object(reviewer, 'csv_fact', side_effect=check_lock):
            result = reviewer.review(directory, result_sha, request_sha, 0)
        self.assertEqual(result['csv_rows'], rows)
        command = [sys.executable, '-W', 'error', str(Path(reviewer.__file__)), '--source', str(directory),
                   '--result-sha256', result_sha, '--request-sha256', request_sha, '--launch-exit', '0',
                   '--output', str(ROOT/'large-cli-review.json')]
        run = subprocess.run(command, capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
        self.assertEqual(json.loads(run.stdout)['csv_last_sample_seq'], first+rows-1)
        with (directory/CSV).open('rb') as stream, self.assertRaisesRegex(ValueError, 'file-byte-budget'):
            reviewer.csv_fact(stream, reviewer.LEGACY_CSV_LIMIT)

    def test_nonzero_or_boolean_launcher_rejected(self):
        for value in (1, True, False):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'launcher-nonzero'):
                self.invoke(exit_code=value)

    def test_unpinned_tamper_rejected(self):
        self.files[CSV] += b'extra'
        with self.assertRaisesRegex(ValueError, 'file-pin:'):
            self.invoke()

    def test_self_consistent_wrong_exit_and_generation_rejected(self):
        for key, value, reason in [('actual_exit_code', 23, 'process-exit-not-normal-zero'),
                                   ('forced_termination', True, 'process-exit-not-normal-zero'),
                                   ('exit_at_utc', '2026-10-15T12:10:00+00:00', 'exit-outside-observation-window')]:
            self.files = fixture()
            self.mutate_json('process-exits.json', lambda v: v[0].update({key: value}))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, reason):
                self.invoke()
        self.files = fixture()
        self.mutate_json('process-exits.json', lambda v: v[0]['identity'].update(exe=reviewer.BACKEND))
        with self.assertRaisesRegex(ValueError, 'exit-generation'):
            self.invoke()

    def test_native_times_and_listener_rejected(self):
        self.mutate_json('runtime-before.json', lambda v: v['processes'][0].update(created_filetime=True))
        with self.assertRaisesRegex(ValueError, 'native-handle-time'):
            self.invoke()
        self.files = fixture()
        self.mutate_json('runtime-before.json', lambda v: v['observation']['listeners'][0].update(OwningProcess=100))
        with self.assertRaisesRegex(ValueError, 'listener-owner'):
            self.invoke()

    def test_dotnet_cim_dates_supported_without_replacing_native_precision(self):
        self.mutate_json('runtime-before.json', lambda v: [p.update(CreationDate=f"/Date({int(v['processes'][i]['created']*1000)}+0900)/")
                                                         for i, p in enumerate(v['observation']['processes'])])
        self.assertEqual(self.invoke()['native_processes'], 2)

    def test_csv_gap_duplicate_header_and_final_count_rejected(self):
        for original, changed, reason in [(b'2,', b'4,', 'csv-sequence-generation'),
            (b'temperature_output_status,', b'sample_seq,', 'csv-header')]:
            self.files = fixture()
            self.files[CSV] = self.files[CSV].replace(original, changed, 1)
            self.files = seal(self.files)
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self.invoke()
        self.files = fixture()
        self.mutate_json(META, lambda v: v['csv_closeout'].update(final_persisted_sample_seq=4))
        with self.assertRaisesRegex(ValueError, 'csv-final-count'):
            self.invoke()

    def test_open_metadata_and_active_runtime_rejected(self):
        self.mutate_json(META, lambda v: v['csv_closeout'].update(finalized=False))
        with self.assertRaisesRegex(ValueError, 'csv-not-finalized'):
            self.invoke()
        self.files = fixture()
        self.mutate_json('runtime-after.json', lambda v: v.update(listeners=[8000]))
        with self.assertRaisesRegex(ValueError, 'runtime-not-cold'):
            self.invoke()

    def test_config_drift_and_duplicate_json_rejected(self):
        self.files['config.ini'] += b'changed=1\n'
        self.files = seal(self.files)
        with self.assertRaisesRegex(ValueError, 'config-pin'):
            self.invoke()
        self.files = fixture()
        self.files['request.json'] = b'{"schema":"a","schema":"b"}'
        self.files = seal(self.files)
        with self.assertRaises(ValueError):
            self.invoke()

    def test_actual_locked_files_cli_console_pin_and_extra_file(self):
        directory = ROOT/'actual'
        directory.mkdir()
        for name, data in self.files.items():
            (directory/name).write_bytes(data)
        result_sha = reviewer.sha(self.files['result.json'])
        request_sha = reviewer.sha(self.files['request.json'])
        result = reviewer.review(directory, result_sha, request_sha, 0)
        self.assertEqual(result['files_verified'], 9)
        with self.assertRaisesRegex(ValueError, 'console-result-pin'):
            reviewer.review(directory, '0'*64, request_sha, 0)
        command = [sys.executable, '-W', 'error', str(Path(reviewer.__file__)), '--source', str(directory),
                   '--result-sha256', result_sha, '--request-sha256', request_sha, '--launch-exit', '0',
                   '--output', str(ROOT/'cli-review.json')]
        run = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
        self.assertEqual(json.loads(run.stdout)['status'], 'LIMITED_RUNTIME_CLOSE_RECEIPTS_VERIFIED')
        (directory/'extra.txt').write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'result-directory-membership'):
            reviewer.review(directory, result_sha, request_sha, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
