"""Native file locks, process/listener binding, and explicit simulated API faults."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

import psutil

import field_installation_binding as binding
from field_resource_sampling import ProcessIdentity


ROOT = Path(os.environ['SFL_BINDING_TEST_ROOT'])


def fact(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.server.paths.append(self.path)
        body = self.server.raw
        self.send_response(self.server.status)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


@contextmanager
def server(raw, status=200):
    instance = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    instance.raw, instance.status, instance.paths = raw, status, []
    worker = threading.Thread(target=instance.serve_forever, kwargs={'poll_interval': .01})
    worker.start()
    try:
        yield instance
    finally:
        instance.shutdown()
        instance.server_close()
        worker.join(2)
        assert not worker.is_alive()


class InstallationBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.folder = ROOT / self._testMethodName
        self.folder.mkdir()
        self.root = self.folder / 'app'
        self.root.mkdir()
        self.files = {name: name.encode() for name in binding.REQUIRED_FILES}
        self.files[binding.PROVENANCE] = json.dumps(dict(schema_version='1.0.0', source='clean_git_head',
                                                       git_commit=binding.BUILD)).encode()
        for name, raw in self.files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.document = dict(candidate_commit=binding.BUILD, version=binding.VERSION,
                             installer_sha256=binding.INSTALLER_SHA, installer_bytes=164618981,
                             payload_file_count=len(self.files),
                             payload_content_bytes=sum(map(len, self.files.values())),
                             payload_files={name: fact(raw) for name, raw in self.files.items()})
        self.main = ProcessIdentity(100, 12.0, os.path.normcase(str(self.root / 'smart-factory.exe')))
        self.backend = ProcessIdentity(101, 13.0, os.path.normcase(str(self.root / binding.BACKEND)))

    def payload(self, *, document=None, extras=None, expected=None, candidate=binding.CANDIDATE_1028):
        reference = self.folder / ('reference-' + str(len(list(self.folder.glob('reference-*')))) + '.json')
        raw = json.dumps(self.document if document is None else document).encode()
        reference.write_bytes(raw)
        return binding.InstalledPayload(self.root, reference,
                                        expected_reference_sha256=expected or fact(raw)['sha256'], extras=extras,
                                        candidate=candidate)

    def test_explicit_1029_identity_rejects_mixed_payload_provenance_and_runtime(self):
        candidate = binding.CANDIDATE_1029
        self.document.update(candidate_commit=candidate.commit, version=candidate.version,
                             installer_sha256=candidate.installer_sha256,
                             installer_bytes=candidate.installer_bytes)
        raw = json.dumps(dict(schema_version='1.0.0', source='clean_git_head',
                              git_commit=candidate.commit)).encode()
        old = self.document['payload_files'][binding.PROVENANCE]['bytes']
        self.document['payload_content_bytes'] += len(raw) - old
        self.document['payload_files'][binding.PROVENANCE] = fact(raw)
        (self.root / binding.PROVENANCE).write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'candidate-identity'):
            with self.payload():
                self.fail('new reference selected old candidate implicitly')
        health = self.health()
        health['app_version'] = candidate.version
        health['spot_temperature']['build_git_commit'] = candidate.commit
        with self.payload(candidate=candidate) as payload:
            self.assertEqual(payload.receipt['build_commit'], candidate.commit)
            self.assertEqual(self.capture(payload, health)['binding_status'], 'PASS')
            self.assertEqual(self.capture(payload, self.health())['binding_status'], 'FAIL')
        wrong = dict(self.document, installer_sha256=binding.INSTALLER_SHA)
        with self.assertRaisesRegex(ValueError, 'candidate-identity'):
            with self.payload(candidate=candidate, document=wrong):
                self.fail('mixed installer identity accepted')
        old_provenance = json.dumps(dict(schema_version='1.0.0', source='clean_git_head',
                                         git_commit=binding.BUILD)).encode()
        (self.root / binding.PROVENANCE).write_bytes(old_provenance)
        self.document['payload_files'][binding.PROVENANCE] = fact(old_provenance)
        self.document['payload_content_bytes'] += len(old_provenance) - len(raw)
        with self.assertRaisesRegex(ValueError, 'installed-provenance'):
            with self.payload(candidate=candidate):
                self.fail('mixed build provenance accepted')

    def test_unrecognized_candidate_does_not_read_payload(self):
        with self.assertRaisesRegex(ValueError, 'unsupported-candidate'):
            self.payload(candidate=replace(binding.CANDIDATE_1029, commit='0' * 40))
        with self.assertRaisesRegex(ValueError, 'candidate-identity-type'):
            self.payload(candidate={'version': '1.0.29'})

    def health(self):
        return dict(app_version=binding.VERSION, runtime_kind='frozen', mode='REAL',
                    executable_path=self.backend.exe, frontend_source='resources', frontend_static_ready=True,
                    spot_temperature=dict(build_git_commit=binding.BUILD, diagnostics_available=True,
                                          spot_service_instance_id='11111111-1111-4111-8111-111111111111',
                                          v2_4_operational=dict(enabled=True,
                                                               logger_service_instance_id='22222222-2222-4222-8222-222222222222')))

    def capture(self, payload, health=None, *, status=200, expected=None, graph=None):
        raw = json.dumps(self.health() if health is None else health).encode()
        with server(raw, status) as fixture, patch.object(binding, 'read_process_binding') as read:
            if graph is None:
                read.return_value = {'fixture_graph': True}
            else:
                read.side_effect = graph
            result = binding.capture_runtime_binding(payload, self.main, self.backend,
                                                     fixture.server_port, expected_sessions=expected)
            self.assertEqual(fixture.paths, ['/health'])
        self.assertEqual(bytes.fromhex(result['health_body_hex']), raw)
        self.assertEqual(result['health_record']['body_sha256'], fact(raw)['sha256'])
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertEqual(result['field_gate'], 'NOT_EVALUATED')
        save(self.folder / ('capture-' + str(len(list(self.folder.glob('capture-*')))) + '.json'), result)
        return result

    def test_native_read_locks_recheck_and_release(self):
        payload = self.payload()
        target = self.root / 'smart-factory.exe'
        with payload:
            self.assertEqual(payload.recheck()['files_rechecked'], 4)
            self.assertEqual(target.read_bytes(), self.files['smart-factory.exe'])
            with self.assertRaises(PermissionError):
                target.open('wb')
            with self.assertRaises(PermissionError):
                target.rename(self.root / 'changed.exe')
            with self.assertRaises(PermissionError):
                target.unlink()
            save(self.folder / 'payload-receipt.json', payload.receipt)
        self.assertFalse(payload.active)
        with target.open('ab') as stream:
            stream.write(b'released')
        with self.assertRaisesRegex(ValueError, 'not-active'):
            payload.recheck()
        with self.assertRaisesRegex(ValueError, 'already-used'):
            payload.__enter__()

    def test_wrong_external_reference_hash(self):
        with self.assertRaisesRegex(ValueError, 'external-reference-hash'):
            with self.payload(expected='0' * 64):
                self.fail('untrusted reference accepted')

    def test_modified_payload_releases_previous_locks(self):
        path = self.root / binding.BACKEND
        path.write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'installed-file-mismatch'):
            with self.payload():
                self.fail('modified bytes accepted')
        # Every successfully opened earlier file was released on entry failure.
        for name in self.files:
            with (self.root / name).open('ab'):
                pass

    def test_existing_write_handle_conflicts(self):
        with (self.root / 'smart-factory.exe').open('r+b'):
            with self.assertRaises(PermissionError):
                with self.payload():
                    self.fail('concurrent writer accepted')

    def test_hardlinked_file_rejected(self):
        os.link(self.root / 'smart-factory.exe', self.folder / 'hardlink.exe')
        with self.assertRaisesRegex(ValueError, 'single-link'):
            with self.payload():
                self.fail('hardlink accepted')

    def test_unlisted_file_rejected(self):
        (self.root / 'extra.dll').write_bytes(b'not in installer')
        with self.assertRaisesRegex(ValueError, 'exact-installed-file-set'):
            with self.payload():
                self.fail('extra accepted')

    def test_missing_file_rejected(self):
        (self.root / 'resources/app.asar').rename(self.folder / 'moved-app.asar')
        with self.assertRaisesRegex(ValueError, 'exact-installed-file-set'):
            with self.payload():
                self.fail('missing accepted')

    def test_installer_extra_requires_exact_external_fact(self):
        name = 'Uninstall smart-factory.exe'
        raw = b'fixture NSIS-generated uninstaller'
        (self.root / name).write_bytes(raw)
        with self.payload(extras={name: fact(raw)}) as payload:
            self.assertEqual(payload.receipt['verified_extras'], {name: fact(raw)})
        with self.assertRaisesRegex(ValueError, 'installed-file-mismatch'):
            with self.payload(extras={name: fact(b'wrong')}):
                self.fail('wrong uninstaller accepted')

    def test_added_file_during_observation_rejected_at_closeout(self):
        with self.payload() as payload:
            (self.root / 'late.dll').write_bytes(b'late')
            with self.assertRaisesRegex(ValueError, 'file-set-changed'):
                payload.recheck()

    def test_contract_tampering_even_with_matching_reference_hash(self):
        mutations = [('candidate_commit', '0' * 40), ('version', '1.0.26'),
                     ('installer_sha256', '0' * 64), ('installer_bytes', True),
                     ('payload_file_count', True), ('payload_content_bytes', -1)]
        for key, value in mutations:
            with self.subTest(key=key):
                document = deepcopy(self.document)
                document[key] = value
                with self.assertRaises(ValueError):
                    with self.payload(document=document):
                        self.fail('tampering accepted')

    def test_unsafe_manifest_paths_and_types(self):
        for name in ('../x', '/x', 'C:/x', 'a:b', 'a\\b', 'con.txt', 'trailing.', 'blank /x'):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    binding.entry_name(name)
        for value in (True, '1', -1, 512 * 1024**2 + 1):
            document = deepcopy(self.document)
            document['payload_files']['smart-factory.exe']['bytes'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                with self.payload(document=document):
                    self.fail('invalid size accepted')

    def test_native_junction_parent_is_not_followed(self):
        junction = self.folder / 'junction'
        command = "New-Item -ItemType Junction -Path '" + str(junction) + "' -Target '" + str(self.root) + "' | Out-Null"
        completed = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                   capture_output=True, timeout=20)
        save(self.folder / 'junction-create.json', dict(exit_code=completed.returncode,
                                                      stdout_hex=completed.stdout.hex(), stderr_hex=completed.stderr.hex()))
        self.assertEqual(completed.returncode, 0)
        with self.assertRaisesRegex(ValueError, 'reparse-path'):
            binding.locked_read(junction / 'smart-factory.exe')
        with self.assertRaisesRegex(ValueError, 'reparse-path'):
            binding.inventory_names(junction)

    def test_bounded_local_path_and_duplicate_json(self):
        for value in ('relative.exe', '//server/share/file', str(self.folder / ('x' * 241))):
            with self.subTest(value=value), self.assertRaises(ValueError):
                binding.plain_path(value)
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                binding.strict_json(raw)

    def test_undeclared_extras_and_case_collisions_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unapproved-installer-extra'):
            with self.payload(extras={'extension.dll': fact(b'')}):
                self.fail('unknown extra accepted')
        document = deepcopy(self.document)
        document['payload_files']['SMART-FACTORY.EXE'] = fact(b'')
        document['payload_file_count'] += 1
        with self.assertRaisesRegex(ValueError, 'duplicate-payload-name'):
            with self.payload(document=document):
                self.fail('case collision accepted')

    def test_missing_or_invalid_health_structure(self):
        cases = [None, [], {}, {'build_git_commit': binding.BUILD}]
        with self.payload() as payload:
            for spot in cases:
                health = self.health()
                health['spot_temperature'] = spot
                with self.subTest(spot=spot):
                    self.assertEqual(self.capture(payload, health)['binding_status'], 'FAIL')

    def test_process_os_access_error_stops_before_http(self):
        with self.payload() as payload, patch.object(binding, 'read_process_binding',
                                                     side_effect=psutil.AccessDenied(101)), \
                patch.object(binding, 'fetch_sample') as fetch:
            result = binding.capture_runtime_binding(payload, self.main, self.backend, 8000)
            self.assertEqual(result['binding_status'], 'FAIL')
            self.assertEqual(result['errors'][0]['type'], 'AccessDenied')
            fetch.assert_not_called()

    def test_provenance_wrong_commit_with_matching_file_hash(self):
        raw = json.dumps(dict(schema_version='1.0.0', source='clean_git_head', git_commit='0' * 40)).encode()
        old_size = self.document['payload_files'][binding.PROVENANCE]['bytes']
        (self.root / binding.PROVENANCE).write_bytes(raw)
        self.document['payload_files'][binding.PROVENANCE] = fact(raw)
        self.document['payload_content_bytes'] += len(raw) - old_size
        with self.assertRaisesRegex(ValueError, 'installed-provenance'):
            with self.payload():
                self.fail('wrong provenance accepted')

    def test_runtime_binding_preserves_health_and_sessions(self):
        with self.payload() as payload:
            first = self.capture(payload)
            second = self.capture(payload, expected=first['sessions'])
            self.assertEqual(first['binding_status'], 'PASS')
            self.assertEqual(second['binding_status'], 'PASS')

    def test_runtime_wrong_version_commit_exe_and_modes(self):
        cases = [('app_version', '1.0.26'), ('runtime_kind', 'dev'), ('mode', 'MOCK'),
                 ('executable_path', self.main.exe), ('frontend_source', 'dev'),
                 ('frontend_static_ready', 1)]
        with self.payload() as payload:
            for key, value in cases:
                health = self.health()
                health[key] = value
                with self.subTest(key=key):
                    self.assertEqual(self.capture(payload, health)['binding_status'], 'FAIL')
            health = self.health()
            health['spot_temperature']['build_git_commit'] = '0' * 40
            self.assertEqual(self.capture(payload, health)['binding_status'], 'FAIL')

    def test_runtime_missing_invalid_or_changed_services(self):
        with self.payload() as payload:
            first = self.capture(payload)
            for value in (None, '', 'not-a-uuid', '33333333-3333-4333-8333-333333333333'):
                for group in ('spot', 'logger'):
                    health = self.health()
                    if group == 'spot':
                        health['spot_temperature']['spot_service_instance_id'] = value
                    else:
                        health['spot_temperature']['v2_4_operational']['logger_service_instance_id'] = value
                    with self.subTest(value=value, group=group):
                        result = self.capture(payload, health, expected=first['sessions'])
                        self.assertEqual(result['binding_status'], 'FAIL')

    def test_http_failure_and_process_change_never_pass(self):
        with self.payload() as payload:
            self.assertEqual(self.capture(payload, status=503)['binding_status'], 'FAIL')
            self.assertEqual(self.capture(payload, graph=[{'before': 1}, {'after': 2}])['binding_status'], 'FAIL')
            self.assertEqual(self.capture(payload, graph=[{}, psutil.NoSuchProcess(101)])['binding_status'], 'FAIL')

    def test_inactive_or_foreign_install_does_not_contact_http(self):
        payload = self.payload()
        with patch.object(binding, 'fetch_sample') as fetch:
            result = binding.capture_runtime_binding(payload, self.main, self.backend, 8000)
            self.assertEqual(result['binding_status'], 'FAIL')
            with payload:
                result = binding.capture_runtime_binding(payload, replace(self.main, exe=sys.executable),
                                                         self.backend, 8000)
                self.assertEqual(result['binding_status'], 'FAIL')
            fetch.assert_not_called()

    def test_native_descendant_listener_pid_and_restart_guards(self):
        child_source = self.folder / 'listener.py'
        child_source.write_text("import socket,sys,os\ns=socket.socket();s.bind(('127.0.0.1',0));s.listen()\n"
                                "print(str(os.getpid())+' '+str(s.getsockname()[1]),flush=True)\n"
                                "sys.stdin.readline();s.close()\n")
        process = subprocess.Popen([sys.executable, str(child_source)], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            # A Windows venv launcher may spawn a different actual Python PID.
            child_pid, port = map(int, process.stdout.readline().split())
            main, backend = ProcessIdentity.read(os.getpid()), ProcessIdentity.read(child_pid)
            actual = binding.read_process_binding(main, backend, port)
            save(self.folder / 'native-binding.json', actual)
            self.assertEqual({row[3] for row in actual['listeners']}, {child_pid})
            with self.assertRaisesRegex(ValueError, 'process-identity-changed'):
                binding.read_process_binding(main, replace(backend, created=backend.created + 1), port)
            with socket.socket() as foreign:
                foreign.bind(('127.0.0.1', 0))
                foreign.listen()
                with self.assertRaisesRegex(ValueError, 'listener-owner-mismatch'):
                    binding.read_process_binding(main, backend, foreign.getsockname()[1])
            stdout, stderr = process.communicate('\n', timeout=10)
            save(self.folder / 'child-exit.json', dict(exit_code=process.returncode, stdout=stdout, stderr=stderr))
            self.assertEqual(process.returncode, 0)
            with self.assertRaises(psutil.NoSuchProcess):
                binding.read_process_binding(main, backend, port)
        finally:
            if process.poll() is None:
                process.communicate('\n', timeout=10)


if __name__ == '__main__':
    unittest.main(verbosity=2)
