"""Native input locks and real pinned CSV consumer, using new copies only."""
from copy import deepcopy
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

import field_csv_inputs as inputs
from test_field_observation import configuration_snapshot
from backend.FacilityData.spot_image_linkage_fact import (
    build_spot_image_linkage_fact_manifest, write_spot_image_linkage_artifacts,
)


ROOT = Path(os.environ['SFL_CSV_INPUT_TEST_ROOT'])
ARCHIVE = Path(os.environ['SFL_CSV_INPUT_ARCHIVE'])
EXE = Path(os.environ['SFL_CSV_INPUT_EXE'])


def fact(path):
    with path.open('rb') as stream:
        return inputs.file_fact(stream)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


class CsvInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir()
        assert fact(EXE)['sha256'] == inputs.CSV_EXE_SHA

    def setUp(self):
        self.folder = ROOT / self._testMethodName
        self.folder.mkdir()

    def prepare(self, name='case', restart=False):
        folder = self.folder / name
        data = folder / 'data'
        data.mkdir(parents=True)
        stage, stamp = ('I5-candidate-restart', '20261013_142706') if restart else ('I4-candidate-runtime', '20261013_142551')
        source = ARCHIVE / stage / 'closed-data'
        roles = dict(v1=f'Factory_Integrated_Log_{stamp}.csv', v2=f'Factory_Integrated_Log_v2_{stamp}.csv',
                     metadata=f'Factory_Integrated_Log_v2_{stamp}.metadata.json', observation='spot_observation_fact.csv',
                     image='spot_image_fact.csv', image_final='spot_image_fact_manifest.final.json')
        baseline = json.loads((ARCHIVE / stage / 'data-after.json').read_bytes())
        for filename in roles.values():
            self.assertEqual(fact(source / filename), dict(bytes=baseline[filename]['bytes'], sha256=baseline[filename]['sha256'].lower()))
            shutil.copy2(source / filename, data / filename)
        return folder, data, roles

    def bind(self, folder, data, roles, **kwargs):
        return inputs.CsvInputs(data, folder / 'bound', roles, {n: fact(data / n) for n in roles.values()}, EXE, **kwargs)

    def execute(self, folder, label, command):
        env = os.environ.copy()
        for key in list(env):
            if key.lower() in ('pythonpath', 'pythonhome', 'psmodulepath'):
                del env[key]
        for key in ('APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP'):
            p = folder / label / key
            p.mkdir(parents=True)
            env[key] = str(p)
        env['PATH'] = env['SYSTEMROOT'] + '/System32;' + env['SYSTEMROOT']
        result = subprocess.run(command, cwd=folder, env=env, capture_output=True, timeout=120,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (folder / (label + '.stdout.log')).write_bytes(result.stdout)
        (folder / (label + '.stderr.log')).write_bytes(result.stderr)
        save(folder / (label + '-terminal.json'), dict(command=command, exit_code=result.returncode))
        self.assertEqual(result.stderr, b'')
        return result.returncode, result.stdout.decode('utf-8')

    def test_archived_install_and_restart_pass_without_external_lookup(self):
        for restart in (False, True):
            folder, data, roles = self.prepare('restart' if restart else 'install', restart)
            original = (data / roles['metadata']).read_bytes()
            ctx = self.bind(folder, data, roles)
            with ctx:
                code, stdout = self.execute(folder, 'csv', ctx.command())
                self.assertEqual(code, 0, stdout)
                self.assertEqual(len(ctx.receipt['path_changes']), 2)
                self.assertEqual(ctx.receipt['input_binding_status'], 'ACTIVE')
                self.assertIn('current_server_promotion_profile_required=False', stdout)
                self.assertFalse(any(x in ctx.command() for x in ('--changeover-candidate-resolution-fact', '--process-phase-event-fact')))
            self.assertEqual(ctx.receipt['input_binding_status'], 'PASS')
            self.assertEqual(ctx.receipt['field_gate'], 'NOT_EVALUATED')
            self.assertEqual((data / roles['metadata']).read_bytes(), original)
            save(folder / 'binding-receipt.json', ctx.receipt)

    def test_external_poison_affects_unbound_consumer_but_not_projection(self):
        folder, data, roles = self.prepare()
        metadata = json.loads((data / roles['metadata']).read_bytes())
        foreign = folder / 'foreign'
        foreign.mkdir()
        target = foreign / 'changeover_candidate_resolution_fact.csv'
        target.write_text('foreign,invalid\nvalue,value\n', encoding='utf-8')
        before = fact(target)
        metadata['changeover_candidate_resolution_fact_manifest']['fact_path'] = str(target)
        save(data / roles['metadata'], metadata)
        ctx = self.bind(folder, data, roles)
        with ctx:
            direct = ctx.command()
            direct[direct.index('--metadata') + 1] = str(data / roles['metadata'])
            self.assertEqual(self.execute(folder, 'unbound', direct)[0], 1)
            code, stdout = self.execute(folder, 'bound', ctx.command())
            self.assertEqual(code, 0, stdout)
        self.assertEqual(before, fact(target))
        save(folder / 'binding-receipt.json', ctx.receipt)

    def test_optional_fact_hash_and_row_mismatch_are_not_relaxed(self):
        for fault in ('none', 'hash', 'rows'):
            folder, data, roles = self.prepare(fault)
            metadata = json.loads((data / roles['metadata']).read_bytes())
            block = metadata['changeover_candidate_resolution_fact_manifest']
            roles['changeover'] = 'changeover_candidate_resolution_fact.csv'
            target = data / roles['changeover']
            with target.open('w', encoding='utf-8-sig', newline='') as stream:
                csv.writer(stream).writerow(block['required_columns'])
            block['sha256'] = '0' * 64 if fault == 'hash' else fact(target)['sha256']
            block['row_count'] = 1 if fault == 'rows' else 0
            save(data / roles['metadata'], metadata)
            ctx = self.bind(folder, data, roles)
            with ctx:
                code, stdout = self.execute(folder, 'strict', ctx.command())
                self.assertEqual(code, 0 if fault == 'none' else 1, stdout)
                if fault != 'none':
                    override = ctx.command() + ['--changeover-candidate-resolution-fact', str(target)]
                    relaxed_code, relaxed_stdout = self.execute(folder, 'override-control', override)
                    self.assertEqual(relaxed_code, 0, relaxed_stdout)
                    self.assertIn('does not match fact file' if fault == 'hash' else 'row_count=1', stdout)
            save(folder / 'binding-receipt.json', ctx.receipt)

    def add_linkage(self, data, roles):
        roles.update(linkage='spot_image_linkage_fact.csv', linkage_report='spot_image_linkage_report.json')
        write_spot_image_linkage_artifacts(source_csv_path=data / roles['v2'], spot_image_fact_path=data / roles['image'],
            fact_output_path=data / roles['linkage'], report_output_path=data / roles['linkage_report'])
        metadata = json.loads((data / roles['metadata']).read_bytes())
        metadata['spot_image_linkage_fact_manifest'] = build_spot_image_linkage_fact_manifest(
            fact_path=data / roles['linkage'], report_path=data / roles['linkage_report'],
            source_csv_path=data / roles['v2'], spot_image_fact_path=data / roles['image'])
        save(data / roles['metadata'], metadata)
        return metadata

    def test_linkage_pair_paths_are_bound_and_contents_still_validated(self):
        folder, data, roles = self.prepare()
        self.add_linkage(data, roles)
        ctx = self.bind(folder, data, roles)
        with ctx:
            code, stdout = self.execute(folder, 'valid-linkage', ctx.command())
            self.assertEqual(code, 0, stdout)
            self.assertEqual(len(ctx.receipt['path_changes']), 4)
        save(folder / 'binding-receipt.json', ctx.receipt)

    def test_declared_linkage_report_hash_is_enforced_before_consumer(self):
        folder, data, roles = self.prepare()
        metadata = self.add_linkage(data, roles)
        metadata['spot_image_linkage_fact_manifest']['report_sha256'] = '0' * 64
        for role in ('changeover', 'phase'):
            section, field = inputs.OPTIONAL[role]
            metadata[section][field] = str(data / inputs.manifest_basename(metadata[section][field]))
        save(data / roles['metadata'], metadata)
        command = [str(EXE)]
        for flag, role in (('--v1', 'v1'), ('--v2', 'v2'), ('--metadata', 'metadata'),
                           ('--spot-observation-fact', 'observation'), ('--spot-image-fact', 'image'),
                           ('--spot-image-fact-final-manifest', 'image_final')):
            command += [flag, str(data / roles[role])]
        code, stdout = self.execute(folder, 'unwrapped-bad-report', command)
        self.assertEqual(code, 0, stdout)  # Existing EXE does not enforce metadata report_sha256.
        with self.assertRaisesRegex(ValueError, 'linkage-report-manifest-hash'):
            with self.bind(folder, data, roles): self.fail('declared report SHA must bind the selected report')

    def test_final_image_manifest_error_is_still_a_csv_failure(self):
        folder, data, roles = self.prepare()
        manifest = json.loads((data / roles['image_final']).read_bytes())
        manifest['sha256'] = '0' * 64
        save(data / roles['image_final'], manifest)
        ctx = self.bind(folder, data, roles)
        with ctx:
            code, stdout = self.execute(folder, 'bad-final', ctx.command())
            self.assertEqual(code, 1, stdout)
            self.assertIn('spot_image_fact_final_manifest.sha256 does not match fact file', stdout)
        self.assertEqual(ctx.receipt['input_binding_status'], 'PASS')  # Bytes bound; content deliberately FAIL.
        save(folder / 'binding-receipt.json', ctx.receipt)

    def test_native_locks_protect_input_projection_and_absence_parent(self):
        folder, data, roles = self.prepare()
        ctx = self.bind(folder, data, roles)
        with ctx:
            for path in (data / roles['metadata'], ctx.projected_path, ctx.work / 'ABSENT_INPUT'):
                with self.assertRaises(PermissionError):
                    path.write_bytes(b'forbidden mutation')
                with self.assertRaises(PermissionError):
                    path.rename(path.with_suffix('.replaced'))
            for item in ctx.receipt['absent_inputs']:
                child = Path(item['consumer_path'])
                self.assertFalse(child.exists())
                with self.assertRaises(OSError):
                    child.write_bytes(b'forbidden optional input')
            with self.assertRaises(PermissionError):
                ctx.work.rename(folder / 'renamed-work')
            with self.assertRaises(PermissionError):
                data.rename(folder / 'renamed-inputs')
        self.assertEqual(ctx.receipt['input_binding_status'], 'PASS')

    def test_missing_nonempty_and_unbound_local_optional_are_rejected(self):
        for mode in ('count', 'sha', 'unbound', 'linkage'):
            folder, data, roles = self.prepare(mode)
            metadata = json.loads((data / roles['metadata']).read_bytes())
            block = metadata['changeover_candidate_resolution_fact_manifest']
            if mode == 'count': block['row_count'] = 1
            if mode == 'sha': block['sha256'] = 'a' * 64
            if mode == 'unbound': (data / 'changeover_candidate_resolution_fact.csv').write_bytes(b'undeclared')
            if mode == 'linkage':
                metadata['spot_image_linkage_fact_manifest'] = dict(fact_path='spot_image_linkage_fact.csv', report_path='report.json')
            save(data / roles['metadata'], metadata)
            ctx = self.bind(folder, data, roles)
            with self.assertRaises(ValueError):
                with ctx: self.fail('must not expose a command')
            self.assertEqual(ctx.receipt['input_binding_status'], 'FAIL')

    def test_expected_hash_and_executable_pin_mismatch_reject_before_use(self):
        folder, data, roles = self.prepare()
        expected = {n: fact(data / n) for n in roles.values()}
        expected[roles['v2']]['sha256'] = '0' * 64
        ctx = inputs.CsvInputs(data, folder / 'bad-data', roles, expected, EXE)
        with self.assertRaisesRegex(ValueError, 'fact-mismatch'):
            with ctx: self.fail()
        with self.assertRaisesRegex(ValueError, 'executable-mismatch'):
            with self.bind(folder, data, roles, executable_sha256='0' * 64): self.fail()

    def test_image_ledger_over_2gib_keeps_native_lock_and_hash_checks(self):
        folder, data, roles = self.prepare()
        large = data / roles['image']
        # Only this newly generated synthetic file is removed after the test.
        self.assertTrue(large.resolve().is_relative_to(ROOT.resolve()))
        self.addCleanup(large.unlink)
        size = 2 * 1024**3 + 1
        with large.open('wb') as stream:
            stream.truncate(size)
        expected = {name: fact(data / name) for name in roles.values() if name != roles['image']}
        with large.open('rb') as stream:
            expected[roles['image']] = dict(bytes=size, sha256=hashlib.file_digest(stream, 'sha256').hexdigest())
        save(folder / 'synthetic-large-file.json', expected[roles['image']])
        ctx = inputs.CsvInputs(data, folder / 'bound', roles, expected, EXE)
        with ctx:
            self.assertEqual(ctx.held[large][2], expected[roles['image']])
            with self.assertRaises(PermissionError): large.write_bytes(b'forbidden')
        self.assertEqual(ctx.receipt['input_binding_status'], 'PASS')
        self.assertEqual(ctx.receipt['field_gate'], 'NOT_EVALUATED')
        save(folder / 'binding-receipt.json', ctx.receipt)

    def omit_v1(self, folder, data, roles, flag=False):
        name = roles.pop('v1')
        (data / name).rename(folder / 'omitted-v1.csv')
        metadata = json.loads((data / roles['metadata']).read_bytes())
        metadata['schema_metadata']['v1_csv_enabled'] = flag
        save(data / roles['metadata'], metadata)
        return name

    def test_explicit_disabled_v1_runs_pinned_consumer_without_pair_claim(self):
        folder, data, roles = self.prepare()
        self.omit_v1(folder, data, roles)
        original = (data / roles['metadata']).read_bytes()
        ctx = self.bind(folder, data, roles)
        with ctx:
            self.assertNotIn('--v1', ctx.command())
            code, stdout = self.execute(folder, 'v2-only', ctx.command())
            self.assertEqual(code, 0, stdout)
            self.assertIn('v1_rows=not checked', stdout)
            self.assertFalse(ctx.receipt['v1_comparison_requested'])
        self.assertEqual(ctx.receipt['input_binding_status'], 'PASS')
        self.assertEqual(ctx.receipt['v1_omission_reason'], 'AUTHENTICATED_METADATA_DISABLED')
        self.assertEqual((data / roles['metadata']).read_bytes(), original)
        save(folder / 'binding-receipt.json', ctx.receipt)

    def test_v1_omission_rejects_missing_or_nonboolean_disabled_flag(self):
        for index, flag in enumerate((True, None, 0, 'false', 'missing')):
            folder, data, roles = self.prepare(str(index))
            self.omit_v1(folder, data, roles, flag)
            if flag == 'missing':
                metadata = json.loads((data / roles['metadata']).read_bytes())
                del metadata['schema_metadata']['v1_csv_enabled']
                save(data / roles['metadata'], metadata)
            with self.assertRaisesRegex(ValueError, 'v1-omission-requires-explicit-disabled-metadata'):
                with self.bind(folder, data, roles): self.fail('unproven omission accepted')

    def test_unbound_v1_present_or_created_during_context_rejects(self):
        for timing in ('before', 'during'):
            folder, data, roles = self.prepare(timing)
            name = self.omit_v1(folder, data, roles)
            if timing == 'before':
                shutil.copy2(folder / 'omitted-v1.csv', data / name)
            ctx = self.bind(folder, data, roles)
            with self.assertRaisesRegex(ValueError, 'unbound-local-v1-input'):
                with ctx:
                    shutil.copy2(folder / 'omitted-v1.csv', data / name)
            self.assertEqual(ctx.receipt['input_binding_status'], 'FAIL')

    def test_image_ledger_limit_does_not_expand_other_input_limits(self):
        for role, size in (('v2', 2 * 1024**3 + 1), ('image', 4 * 1024**3 + 1)):
            folder, data, roles = self.prepare(role)
            expected = {name: fact(data / name) for name in roles.values()}
            expected[roles[role]]['bytes'] = size
            ctx = inputs.CsvInputs(data, folder / 'bound', roles, expected, EXE)
            with self.assertRaisesRegex(ValueError, 'csv-input-fact-contract'):
                with ctx: self.fail('out-of-budget input accepted')
            self.assertEqual(ctx.receipt['input_binding_status'], 'FAIL')

    def test_streaming_hash_enforces_supplied_budget(self):
        with self.assertRaisesRegex(ValueError, 'csv-input-byte-budget'):
            inputs.file_fact(io.BytesIO(b'x' * 33), maximum_bytes=32)
        self.assertEqual(inputs.file_fact(io.BytesIO(b'x' * 32), maximum_bytes=32),
                         dict(bytes=32, sha256=hashlib.sha256(b'x' * 32).hexdigest()))

    def test_malformed_duplicate_json_and_unsafe_manifest_paths_reject(self):
        for index, bad_path in enumerate(('../escape.csv', 'C:relative.csv', '//host/share/f.csv', 'C:/safe/f.csv:ads', 'NUL.csv', None)):
            folder, data, roles = self.prepare(str(index))
            metadata = json.loads((data / roles['metadata']).read_bytes())
            metadata['changeover_candidate_resolution_fact_manifest']['fact_path'] = bad_path
            save(data / roles['metadata'], metadata)
            with self.assertRaises(ValueError):
                with self.bind(folder, data, roles): self.fail()
        folder, data, roles = self.prepare('duplicate-json')
        (data / roles['metadata']).write_bytes(b'{"duplicate":1,"duplicate":2}')
        with self.assertRaises(ValueError):
            with self.bind(folder, data, roles): self.fail()

    def test_closeout_failure_and_body_exception_never_leave_pass(self):
        folder, data, roles = self.prepare('closeout')
        ctx = self.bind(folder, data, roles)
        ctx.__enter__()
        with patch.object(inputs, 'file_fact', side_effect=OSError('closeout read failed')):
            with self.assertRaises(OSError): ctx.__exit__(None, None, None)
        self.assertEqual(ctx.receipt['input_binding_status'], 'FAIL')
        (data / roles['v1']).write_bytes(b'copy handles closed')
        folder, data, roles = self.prepare('body')
        ctx = self.bind(folder, data, roles)
        with self.assertRaises(RuntimeError):
            with ctx: raise RuntimeError('consumer failure')
        self.assertEqual(ctx.receipt['input_binding_status'], 'FAIL')

    def test_context_close_exception_keeps_fail_and_releases_input_handles(self):
        folder, data, roles = self.prepare()
        ctx = self.bind(folder, data, roles)
        def fail_close():
            raise OSError('simulated context close failure')
        with self.assertRaisesRegex(OSError, 'context close failure'):
            with ctx:
                ctx.stack.callback(fail_close)
        self.assertEqual(ctx.receipt['input_binding_status'], 'FAIL')
        (data / roles['v1']).write_bytes(b'copy handles were released')

    def test_new_optional_file_after_binding_invalidates_closeout(self):
        folder, data, roles = self.prepare()
        ctx = self.bind(folder, data, roles)
        with self.assertRaisesRegex(ValueError, 'optional-source-copy-changed'):
            with ctx:
                (data / 'changeover_candidate_resolution_fact.csv').write_bytes(b'new file')
                self.assertFalse(Path(ctx.receipt['absent_inputs'][0]['consumer_path']).exists())
        self.assertEqual(ctx.receipt['input_binding_status'], 'FAIL')

    def test_command_lifetime_reuse_and_wrong_pair_are_rejected(self):
        folder, data, roles = self.prepare()
        ctx = self.bind(folder, data, roles)
        with self.assertRaises(ValueError): ctx.command()
        with ctx: pass
        with self.assertRaises(ValueError): ctx.command()
        with self.assertRaises(ValueError): ctx.__enter__()
        folder, data, roles = self.prepare('bad-pair')
        bad = deepcopy(roles)
        bad['v1'] = 'wrong.csv'; (data / bad['v1']).write_bytes(b'x')
        with self.assertRaisesRegex(ValueError, 'pair-identity'):
            with self.bind(folder, data, bad): self.fail()

    def shutdown_reference(self, folder, metadata, roles):
        expected = dict(schema=inputs.shutdown.SCHEMA, build_git_commit=inputs.binding.BUILD,
            logger_service_instance_id=metadata['schema_metadata']['logger_service_instance_id'],
            spot_service_instance_id='11111111-1111-4111-8111-111111111111', schema_version='2.5.2',
            csv_file_name=roles['v2'], minimum_sample_seq=metadata['csv_closeout']['final_persisted_sample_seq'],
            health_body_sha256='a' * 64, observed_at=datetime.now(timezone.utc).isoformat())
        snapshot = configuration_snapshot()
        reference = folder / 'synthetic-reference.json'
        save(reference, dict(schema='sfl-field-configuration-reference-v1',
            profile_approval_sha256=inputs.configuration.PROFILE_APPROVAL_SHA, snapshot=snapshot,
            classification='SYNTHETIC_TEST_NOT_FIELD_APPROVAL'))
        return expected, snapshot, reference, fact(reference)['sha256']

    def test_shutdown_integration_preserves_archived_attestation_failure(self):
        folder, data, roles = self.prepare()
        metadata = json.loads((data / roles['metadata']).read_bytes())
        expected, _, reference, sha = self.shutdown_reference(folder, metadata, roles)
        ctx = self.bind(folder, data, roles)
        with self.assertRaisesRegex(ValueError, 'shutdown-csv-identity-or-configuration-failed'):
            with inputs.shutdown_csv_inputs(ctx, expected, reference, sha): self.fail()
        self.assertEqual(ctx.receipt['shutdown_review']['identity_status'], 'PASS')
        self.assertEqual(ctx.receipt['shutdown_review']['configuration_review']['status'], 'FAIL')
        self.assertEqual(ctx.receipt['input_binding_status'], 'FAIL')
        save(folder / 'binding-receipt.json', ctx.receipt)

    def test_synthetic_shutdown_reference_is_checked_with_same_locked_metadata(self):
        folder, data, roles = self.prepare()
        metadata = json.loads((data / roles['metadata']).read_bytes())
        expected, snapshot, reference, sha = self.shutdown_reference(folder, metadata, roles)
        metadata['spot_configuration_snapshot'] = snapshot
        save(data / roles['metadata'], metadata)  # Explicit synthetic copy; archived source remains untouched.
        ctx = self.bind(folder, data, roles)
        with inputs.shutdown_csv_inputs(ctx, expected, reference, sha):
            self.assertEqual(ctx.receipt['shutdown_review']['status'], 'PASS')
            with self.assertRaises(PermissionError): reference.write_bytes(b'cannot change reference')
            self.assertIn('--metadata', ctx.command())
        self.assertEqual(ctx.receipt['input_binding_status'], 'PASS')
        self.assertFalse(ctx.receipt['promotion_allowed'])
        save(folder / 'binding-receipt.json', ctx.receipt)


if __name__ == '__main__':
    unittest.main()
