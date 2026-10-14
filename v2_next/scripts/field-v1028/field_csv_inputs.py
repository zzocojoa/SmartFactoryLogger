"""Bind the pinned CSV consumer to explicit locked inputs and a path-only projection.

The caller supplies facts from the authenticated closed-copy inventory and keeps
this context open until the validator and its descendants exit. This does not
prove shutdown, inventory authorization, image bytes, or field QA. Like the
payload binder, locks are not a defense against an adversarial parent owner.
"""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re

import field_installation_binding as binding
import field_configuration_binding as configuration
import field_shutdown_binding as shutdown


CSV_EXE_SHA = 'e728730ad841dd4a754a6c0880e0e1216de5e3d0cd5646c22de9245fc85b0b2f'
DEFAULT_INPUT_MAX_BYTES = 2 * 1024**3
# The cumulative field image ledger has exceeded 2 GiB. Other inputs retain
# their existing limit; hashing still reads at most 1 MiB into memory per chunk.
IMAGE_FACT_MAX_BYTES = 4 * 1024**3
REQUIRED = {'v2', 'metadata', 'observation', 'image', 'image_final'}
OPTIONAL = {
    'changeover': ('changeover_candidate_resolution_fact_manifest', 'fact_path'),
    'phase': ('process_phase_event_fact_manifest', 'fact_path'),
    'linkage': ('spot_image_linkage_fact_manifest', 'fact_path'),
    'linkage_report': ('spot_image_linkage_fact_manifest', 'report_path'),
}


def file_fact(stream, *, maximum_bytes=DEFAULT_INPUT_MAX_BYTES):
    binding.require(type(maximum_bytes) is int and 0 < maximum_bytes <= IMAGE_FACT_MAX_BYTES,
                    'csv-input-byte-budget')
    stream.seek(0)
    digest, count = hashlib.sha256(), 0
    while chunk := stream.read(1024 * 1024):
        count += len(chunk)
        binding.require(count <= maximum_bytes, 'csv-input-byte-budget')
        digest.update(chunk)
    return dict(bytes=count, sha256=digest.hexdigest())


def manifest_basename(value):
    binding.require(isinstance(value, str) and value and value == value.strip(), 'manifest-path-text')
    path = PureWindowsPath(value)
    binding.require(not path.drive.startswith('\\') and (not path.drive or re.fullmatch('[A-Za-z]:', path.drive))
                    and (not path.root or bool(path.drive)) and (not path.drive or path.root),
                    'manifest-path-root')
    parts = path.parts[1:] if path.anchor else path.parts
    binding.require(bool(parts), 'manifest-path-basename')
    for part in parts:
        binding.entry_name(part)
    return path.name


class CsvInputs:
    """One-use lock context; PASS becomes available only after clean closeout."""
    def __init__(self, data_root, work_directory, roles, expected_files, executable,
                 *, executable_sha256=CSV_EXE_SHA):
        self.root, self.work = Path(data_root), Path(work_directory)
        self.roles, self.expected = dict(roles), deepcopy(expected_files)
        self.executable, self.executable_sha256 = Path(executable), executable_sha256
        self.stack, self.held = ExitStack(), {}
        self.active = self.used = False
        self.receipt = dict(input_binding_status='FAIL', scope='CSV_CONSUMER_DEFAULT_STREAM_INPUTS',
                            field_gate='NOT_EVALUATED', image_bytes_gate='NOT_EVALUATED',
                            release_gate='HOLD', promotion_allowed=False)

    def _maximum_bytes(self, path):
        return IMAGE_FACT_MAX_BYTES if path == self.root / self.roles['image'] else DEFAULT_INPUT_MAX_BYTES

    def _hold(self, path, expected=None):
        path = binding.plain_path(path)
        binding.require(path not in self.held, 'duplicate-held-input')
        stream = self.stack.enter_context(binding.locked_read(path))
        stat = os.fstat(stream.fileno())
        maximum_bytes = self._maximum_bytes(path)
        binding.require(stat.st_size <= maximum_bytes, 'csv-input-byte-budget')
        value = file_fact(stream, maximum_bytes=maximum_bytes)
        binding.require(expected is None or value == expected, 'csv-input-fact-mismatch:' + path.name)
        self.held[path] = (stream, (stat.st_dev, stat.st_ino, stat.st_size), value)
        return stream

    def __enter__(self):
        binding.require(not self.used, 'csv-context-already-used')
        self.used = True
        try:
            binding.plain_path(self.root)
            binding.require(self.root.is_dir(), 'csv-root-directory')
            binding.require(REQUIRED <= self.roles.keys() <= REQUIRED | OPTIONAL.keys() | {'v1'}, 'csv-role-set')
            binding.require(len(set(self.roles.values())) == len(self.roles), 'csv-role-alias')
            binding.require(set(self.roles.values()) == self.expected.keys(), 'exact-csv-input-facts')
            for name, value in self.expected.items():
                binding.entry_name(name)
                binding.require('/' not in name, 'csv-input-direct-child')
                binding.require(isinstance(value, dict) and set(value) == {'bytes', 'sha256'}
                                and type(value['bytes']) is int and 0 <= value['bytes'] <= self._maximum_bytes(self.root / name)
                                and isinstance(value['sha256'], str)
                                and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'csv-input-fact-contract')
                self._hold(self.root / name, value)
            self.paths = {role: self.root / name for role, name in self.roles.items()}
            v2 = self.roles['v2']
            binding.require(re.fullmatch(r'Factory_Integrated_Log_v2_[A-Za-z0-9_.-]+\.csv', v2)
                            and ('v1' not in self.roles or self.roles['v1'] == v2.replace('_v2_', '_', 1))
                            and self.roles['metadata'] == str(Path(v2).with_suffix('.metadata.json')),
                            'csv-pair-identity')
            binding.require(isinstance(self.executable_sha256, str)
                            and re.fullmatch('[0-9a-f]{64}', self.executable_sha256), 'csv-executable-hash')
            exe_stream = self._hold(self.executable)
            binding.require(file_fact(exe_stream)['sha256'] == self.executable_sha256, 'csv-executable-mismatch')
            metadata_stream = self.held[self.paths['metadata']][0]
            binding.require(os.fstat(metadata_stream.fileno()).st_size <= 4 * 1024**2, 'metadata-byte-budget')
            metadata_stream.seek(0)
            original = binding.strict_json(metadata_stream.read())
            self.absent_v1 = None
            if 'v1' not in self.roles:
                schema = original.get('schema_metadata')
                binding.require(isinstance(schema, dict) and schema.get('v1_csv_enabled') is False,
                                'v1-omission-requires-explicit-disabled-metadata')
                self.absent_v1 = self.root / v2.replace('_v2_', '_', 1)
                binding.require(not self.absent_v1.exists(), 'unbound-local-v1-input')
            projected = deepcopy(original)
            binding.require(self.work.is_absolute() and not self.work.exists()
                            and self.work != self.root and self.root not in self.work.parents,
                            'new-work-directory-outside-input')
            binding.plain_path(self.work.parent)
            self.work.mkdir()
            binding.plain_path(self.work)
            blocker = self.work / 'ABSENT_INPUT'
            with blocker.open('xb') as stream:
                stream.write(b'Locked regular file: optional consumer children cannot exist.\n')
            self._hold(blocker)
            changes, absent = [], []
            for role, (section, field) in OPTIONAL.items():
                manifest = original.get(section)
                if not isinstance(manifest, dict):
                    binding.require(role not in self.roles, 'optional-input-without-manifest')
                    continue  # Preserve malformed/missing blocks for the validator's own failure rules.
                name = manifest_basename(manifest.get(field))
                if role in self.roles:
                    binding.require(name == self.roles[role], 'optional-input-name-mismatch')
                    if role == 'linkage_report':
                        binding.require(manifest.get('report_sha256') == self.expected[name]['sha256'],
                                        'linkage-report-manifest-hash')
                    target = self.paths[role]
                else:
                    binding.require(role in ('changeover', 'phase') and type(manifest.get('row_count')) is int
                                    and manifest['row_count'] == 0 and manifest.get('sha256') is None,
                                    'nonempty-or-required-optional-input-missing')
                    binding.require(not (self.root / name).exists(), 'unbound-local-optional-input')
                    target = blocker / name
                    binding.require(not target.exists(), 'optional-consumer-path-exists')
                    absent.append(dict(role=role, source_copy_path=str(self.root / name),
                                       consumer_path=str(target), absence_mechanism='LOCKED_REGULAR_FILE_PARENT'))
                binding.require(len(str(target)) <= 240, 'projected-path-budget')
                projected[section][field] = str(target)
                changes.append(dict(section=section, field=field, original=manifest[field], projected=str(target)))
            binding.require(('linkage' in self.roles) == ('linkage_report' in self.roles), 'linkage-pair-required')
            restored = deepcopy(projected)
            for change in changes:
                restored[change['section']][change['field']] = change['original']
            binding.require(restored == original, 'metadata-projection-content-change')
            self.projected_path = self.work / self.roles['metadata']
            with self.projected_path.open('xb') as stream:
                stream.write((json.dumps(projected, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
            self._hold(self.projected_path)
            self.absent = absent
            self.receipt.update(input_binding_status='ACTIVE', input_files=self.expected,
                                input_byte_limits={name: self._maximum_bytes(self.root / name) for name in self.expected},
                                executable_sha256=self.executable_sha256, path_changes=changes,
                                projected_metadata=file_fact(self.held[self.projected_path][0]),
                                original_metadata=self.expected[self.roles['metadata']], absent_inputs=absent,
                                v1_comparison_requested='v1' in self.roles,
                                v1_omission_reason=None if self.absent_v1 is None else 'AUTHENTICATED_METADATA_DISABLED',
                                non_path_metadata_fields_unchanged=True)
            self.active = True
            self.recheck()
            return self
        except BaseException:
            self.receipt['input_binding_status'] = 'FAIL'
            self.active = False
            self.stack.close()
            raise

    def command(self):
        binding.require(self.active, 'csv-context-not-active')
        v1_args = ['--v1', str(self.paths['v1'])] if 'v1' in self.paths else []
        return [str(self.executable), *v1_args, '--v2', str(self.paths['v2']),
                '--metadata', str(self.projected_path), '--spot-observation-fact', str(self.paths['observation']),
                '--spot-image-fact', str(self.paths['image']), '--spot-image-fact-final-manifest',
                str(self.paths['image_final'])]

    def recheck(self):
        binding.require(self.active, 'csv-context-not-active')
        if self.absent_v1 is not None:
            binding.require(not self.absent_v1.exists(), 'unbound-local-v1-input')
        for path, (stream, identity, expected) in self.held.items():
            current = binding.plain_path(path).stat()
            binding.require((current.st_dev, current.st_ino, current.st_size) == identity,
                            'csv-input-identity-changed')
            binding.require(file_fact(stream, maximum_bytes=self._maximum_bytes(path)) == expected,
                            'csv-input-bytes-changed')
        for item in self.absent:
            binding.require(not Path(item['consumer_path']).exists(), 'optional-consumer-path-exists')
            binding.require(not Path(item['source_copy_path']).exists(), 'optional-source-copy-changed')

    def __exit__(self, error_type, error, traceback):
        self.receipt['input_binding_status'] = 'FAIL'
        try:
            self.recheck()
        finally:
            self.active = False
            self.stack.close()
        if error_type is None:
            self.receipt['input_binding_status'] = 'PASS'


@contextmanager
def shutdown_csv_inputs(bound, expected_shutdown, configuration_path, configuration_sha256):
    """Check the observed shutdown and pinned attestation against the SAME held metadata.

The caller must authenticate expected_shutdown's observation provenance and
record the consumer's real exit. No process exit or physical QA is inferred.
    """
    with bound, configuration.configuration_reference(configuration_path, configuration_sha256) as reference:
        shutdown.validate_expectation(expected_shutdown)
        binding.require(bound.roles['v2'] == expected_shutdown['csv_file_name'], 'observed-csv-input-name')
        stream = bound.held[bound.paths['metadata']][0]
        stream.seek(0)
        review = shutdown.review_metadata(binding.strict_json(stream.read()), expected_shutdown, reference)
        bound.receipt.update(shutdown_review=review, shutdown_expectation=deepcopy(expected_shutdown),
                             configuration_reference_sha256=configuration_sha256)
        binding.require(review['status'] == 'PASS', 'shutdown-csv-identity-or-configuration-failed')
        yield bound
