"""Read-only candidate payload and sampled runtime binding for the field collector.

No production launcher, installation, process control, attestation or QA approval.
The caller must durably save returned raw evidence and supply an outer watchdog.
Locks cover ordinary file writes/deletes, not an adversarial writable parent tree.
"""
from contextlib import ExitStack
import ctypes
from ctypes import wintypes
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from uuid import UUID

import psutil

from field_http_sampling import ENDPOINTS, _strict_object, _invalid_constant, fetch_sample
from field_resource_sampling import ProcessIdentity, error_record


BUILD = '4cc7393e1bafbf90a329726aed9470fe0daacb21'
VERSION = '1.0.28'
INSTALLER_SHA = '8821746bbed47850ead68c66894e5580afac63483b1569865915dadc30cfc848'
REFERENCE_SHA = 'a5de26c2db81c8d69418fd3e574d4180b2dd895ab94b9cbf064959369644af5c'
BACKEND = 'resources/backend/SmartFactoryBackend.exe'
PROVENANCE = 'resources/backend/_internal/backend/build_provenance.json'
REQUIRED_FILES = {'smart-factory.exe', BACKEND, PROVENANCE, 'resources/app.asar'}


@dataclass(frozen=True)
class CandidateIdentity:
    commit: str
    version: str
    installer_sha256: str
    installer_bytes: int

    def validate(self):
        require(type(self) is CandidateIdentity and self in (CANDIDATE_1028, CANDIDATE_1029, CANDIDATE_1030),
                'unsupported-candidate-identity')


CANDIDATE_1028 = CandidateIdentity(BUILD, VERSION, INSTALLER_SHA, 164618981)
CANDIDATE_1029 = CandidateIdentity(
    'acaf77d95101a050f4d3ecd76125d3502036f5a7', '1.0.29',
    '3394a23de82f0d40749f020af320592a33cd9630113ba02b1e40f63f41549de7', 164824610)
REFERENCE_SHA_1029 = '658b096408ddb82022c53f9802c1300e6da7ca7cfbd077a60db4efc07935fe69'
CANDIDATE_1030 = CandidateIdentity(
    '0732c8e810be3c46096b397812f53a9767354229', '1.0.30',
    'e72c042dd4554d5c31e27b8a2edfa6ecdcbdd08c58ed43769e7a84d782b370c1', 164941077)
REFERENCE_SHA_1030 = '4e3e95be87d8ea51a509ba62c8eb29236eefe402f5f353bb78c9a342d7825a97'


def candidate_from_commit(commit):
    for candidate in (CANDIDATE_1028, CANDIDATE_1029, CANDIDATE_1030):
        if type(commit) is str and commit == candidate.commit:
            return candidate
    raise ValueError('unsupported-candidate-commit')


def candidate_reference_sha256(candidate):
    require(type(candidate) is CandidateIdentity, 'candidate-identity-type')
    candidate.validate()
    return {CANDIDATE_1028: REFERENCE_SHA,
            CANDIDATE_1029: REFERENCE_SHA_1029,
            CANDIDATE_1030: REFERENCE_SHA_1030}[candidate]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def plain_path(value):
    path = Path(value)
    require(path.is_absolute() and path.drive and not str(path).startswith('\\\\')
            and '..' not in path.parts and len(str(path)) <= 240, 'absolute-local-path-budget')
    for node in (path, *path.parents):
        info = node.lstat()
        require(not info.st_file_attributes & 0x400, 'reparse-path')
    return path


def entry_name(name):
    require(isinstance(name, str) and 0 < len(name) <= 200
            and not re.search(r'[\\:<>"|?*\x00-\x1f]', name), 'unsafe-entry-name')
    for part in name.split('/'):
        require(part not in ('', '.', '..') and not part.endswith(('.', ' '))
                and not re.match(r'^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)', part, re.I),
                'unsafe-entry-component')
    return name


def strict_json(raw):
    result = json.loads(raw, object_pairs_hook=_strict_object, parse_constant=_invalid_constant)
    require(isinstance(result, dict), 'json-object-required')
    return result


def locked_read(path):
    """Open the same regular file bytes with read sharing only (Windows)."""
    if os.name != 'nt':
        raise OSError('Windows required')
    import msvcrt
    path = plain_path(path)
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    api.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR,
                                            wintypes.DWORD, wintypes.DWORD]
    api.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    handle = api.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    fd = None
    try:
        buffer = ctypes.create_unicode_buffer(1024)
        length = api.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not length:
            raise ctypes.WinError(ctypes.get_last_error())
        require(length < len(buffer), 'handle-path-budget')
        final = buffer.value.removeprefix('\\\\?\\')
        require(os.path.normcase(final) == os.path.normcase(str(path)), 'handle-path-mismatch')
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        handle = None  # fd now owns the native handle.
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and not info.st_file_attributes & 0x400, 'regular-single-link-file-required')
        stream = os.fdopen(fd, 'rb')
        fd = None
        return stream
    finally:
        if fd is not None:
            os.close(fd)
        if handle is not None:
            api.CloseHandle(handle)


def stream_fact(stream):
    stream.seek(0)
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        require(size <= 512 * 1024**2, 'file-byte-budget')
        digest.update(chunk)
    return {'bytes': size, 'sha256': digest.hexdigest()}


def inventory_names(root):
    pending, names, seen = [plain_path(root)], set(), 0
    folded = set()
    while pending:
        directory = pending.pop()
        plain_path(directory)
        for node in directory.iterdir():
            seen += 1
            require(seen <= 6000, 'tree-entry-budget')
            plain_path(node)
            name = entry_name(node.relative_to(root).as_posix())
            require(name.casefold() not in folded, 'case-collision')
            folded.add(name.casefold())
            if node.is_dir():
                pending.append(node)
            else:
                require(node.is_file(), 'non-file-entry')
                names.add(name)
    return names


class InstalledPayload:
    """Keep verified payload handles until observation ends; recheck at closeout.

    Expected reference hash must come from the locked launcher, never from the
    reference itself. Default pins the delivered candidate. Explicit alternate
    hashes support isolated fixtures; this class alone grants no field approval.
    NSIS extras are allowed only with externally supplied exact names/bytes/SHA.
    """
    def __init__(self, root, reference, *, expected_reference_sha256=REFERENCE_SHA, extras=None,
                 candidate=CANDIDATE_1028):
        require(type(candidate) is CandidateIdentity, 'candidate-identity-type')
        candidate.validate()
        self.candidate = candidate
        self.root = Path(root)
        self.reference = Path(reference)
        self.expected_reference_sha256 = expected_reference_sha256
        self.extras = {} if extras is None else dict(extras)
        self.stack = ExitStack()
        self.streams = {}
        self.active = False
        self.used = False

    def __enter__(self):
        require(not self.used, 'payload-context-already-used')
        self.used = True
        try:
            plain_path(self.root)
            require(self.root.is_dir() and self.root != Path(self.root.anchor), 'invalid-install-root')
            reference = self.stack.enter_context(locked_read(self.reference))
            require(os.fstat(reference.fileno()).st_size <= 2 * 1024**2, 'reference-byte-budget')
            raw = reference.read()
            require(hashlib.sha256(raw).hexdigest() == self.expected_reference_sha256,
                    'external-reference-hash')
            document = strict_json(raw)
            candidate = self.candidate
            require(document.get('candidate_commit') == candidate.commit and document.get('version') == candidate.version
                    and document.get('installer_sha256') == candidate.installer_sha256
                    and type(document.get('installer_bytes')) is int
                    and document['installer_bytes'] == candidate.installer_bytes, 'candidate-identity')
            files = document.get('payload_files')
            require(isinstance(files, dict) and 4 <= len(files) <= 5000, 'payload-file-count')
            require(type(document.get('payload_file_count')) is int
                    and document['payload_file_count'] == len(files), 'declared-file-count')
            self.specs = dict(files)
            require(REQUIRED_FILES <= self.specs.keys(), 'required-payload-files')
            require(not self.specs.keys() & self.extras.keys(), 'extra-overlap')
            for name in self.extras:
                require(name in ('Uninstall smart-factory.exe', 'uninstallerIcon.ico'),
                        'unapproved-installer-extra')
            self.specs.update(self.extras)
            folded = set()
            for name, fact in self.specs.items():
                entry_name(name)
                require(name.casefold() not in folded, 'duplicate-payload-name')
                folded.add(name.casefold())
                require(isinstance(fact, dict) and type(fact.get('bytes')) is int
                        and 0 <= fact['bytes'] <= 512 * 1024**2
                        and isinstance(fact.get('sha256'), str)
                        and re.fullmatch('[0-9a-f]{64}', fact['sha256']), 'invalid-file-fact')
            require(type(document.get('payload_content_bytes')) is int
                    and document['payload_content_bytes'] == sum(v['bytes'] for v in files.values())
                    and sum(v['bytes'] for v in self.specs.values()) <= 2 * 1024**3, 'payload-byte-budget')
            require(inventory_names(self.root) == self.specs.keys(), 'exact-installed-file-set')
            started = time.perf_counter_ns()
            for name, fact in self.specs.items():
                stream = self.stack.enter_context(locked_read(self.root / name))
                require(stream_fact(stream) == fact, 'installed-file-mismatch:' + name)
                self.streams[name] = stream
            provenance = self.streams[PROVENANCE]
            provenance.seek(0)
            require(os.fstat(provenance.fileno()).st_size <= 65536, 'provenance-byte-budget')
            info = strict_json(provenance.read())
            require(info.get('schema_version') == '1.0.0' and info.get('source') == 'clean_git_head'
                    and info.get('git_commit') == candidate.commit, 'installed-provenance')
            self.receipt = {'root': str(self.root), 'build_commit': candidate.commit, 'version': candidate.version,
                            'installer_sha256': candidate.installer_sha256, 'reference_sha256': hashlib.sha256(raw).hexdigest(),
                            'verified_files': len(files), 'verified_extras': self.extras,
                            'verified_bytes': sum(v['bytes'] for v in self.specs.values()),
                            'started_ns': started, 'finished_ns': time.perf_counter_ns(),
                            'scope': 'DEFAULT_STREAM_PAYLOAD_BYTES_NOT_LOADED_MEMORY_OR_INSTALLER_EXECUTION',
                            'field_gate': 'NOT_EVALUATED', 'release_gate': 'HOLD'}
            self.active = True
            self.recheck()
            return self
        except BaseException:
            self.stack.close()
            self.active = False
            raise

    def recheck(self):
        require(self.active, 'payload-context-not-active')
        require(inventory_names(self.root) == self.specs.keys(), 'installed-file-set-changed')
        for name, stream in self.streams.items():
            path = plain_path(self.root / name)
            opened, current = os.fstat(stream.fileno()), path.stat()
            require((opened.st_dev, opened.st_ino, opened.st_size) ==
                    (current.st_dev, current.st_ino, current.st_size), 'installed-file-identity-changed')
            require(stream_fact(stream) == self.specs[name], 'installed-bytes-changed:' + name)
        return {'files_rechecked': len(self.streams), 'finished_ns': time.perf_counter_ns()}

    def __exit__(self, *args):
        self.active = False
        self.stack.close()


def read_process_binding(main, backend, port):
    """Fresh OS identities before/after tree and IPv4/IPv6 listener enumeration."""
    main.validate()
    backend.validate()
    require(main.pid != backend.pid and type(port) is int and 1 <= port <= 65535, 'process-port-contract')
    require(ProcessIdentity.read(main.pid) == main and ProcessIdentity.read(backend.pid) == backend,
            'process-identity-changed')
    ancestors = psutil.Process(backend.pid).parents()
    require(any(p.pid == main.pid and p.create_time() == main.created for p in ancestors),
            'backend-not-main-descendant')
    listeners = sorted({(c.family.value, c.laddr.ip, c.laddr.port, c.pid)
                        for c in psutil.net_connections(kind='tcp')
                        if c.status == psutil.CONN_LISTEN and c.laddr.port == port})
    require(listeners and all(row[3] == backend.pid for row in listeners), 'listener-owner-mismatch')
    require(any(row[1] in ('127.0.0.1', '0.0.0.0') for row in listeners), 'ipv4-loopback-listener-missing')
    require(ProcessIdentity.read(main.pid) == main and ProcessIdentity.read(backend.pid) == backend,
            'process-identity-changed-during-read')
    return {'main': asdict(main), 'backend': asdict(backend), 'listeners': listeners}


def runtime_sessions(health, backend, *, candidate=CANDIDATE_1028):
    require(type(candidate) is CandidateIdentity, 'candidate-identity-type')
    candidate.validate()
    require(health.get('app_version') == candidate.version and health.get('runtime_kind') == 'frozen'
            and health.get('mode') == 'REAL', 'runtime-build-kind')
    require(isinstance(health.get('executable_path'), str)
            and os.path.normcase(health['executable_path']) == backend.exe, 'runtime-executable')
    require(health.get('frontend_source') == 'resources'
            and health.get('frontend_static_ready') is True, 'runtime-frontend')
    spot = health.get('spot_temperature')
    require(isinstance(spot, dict) and spot.get('build_git_commit') == candidate.commit
            and spot.get('diagnostics_available') is True, 'runtime-build-commit')
    logger = spot.get('v2_4_operational')
    require(isinstance(logger, dict) and logger.get('enabled') is True, 'runtime-logger')
    result = {'spot_service_instance_id': spot.get('spot_service_instance_id'),
              'logger_service_instance_id': logger.get('logger_service_instance_id')}
    for value in result.values():
        require(isinstance(value, str) and str(UUID(value)) == value, 'runtime-service-uuid')
    return result


def capture_runtime_binding(payload, main, backend, port, *, expected_sessions=None):
    """Return evidence even on mismatch. This is a sampled identity check only.

    No extra SPOT request: health reads backend state. Configuration fingerprint,
    authenticated backend generation, shutdown and between-sample identity
    coverage remain the full collector's responsibilities.
    """
    result = {'started_ns': time.perf_counter_ns(), 'observed_at': datetime.now(timezone.utc).isoformat(),
              'binding_status': 'FAIL', 'errors': [], 'field_gate': 'NOT_EVALUATED',
              'release_gate': 'HOLD', 'promotion_authorized': False}
    try:
        require(payload.active, 'payload-context-not-active')
        require(main.exe == os.path.normcase(str(payload.root / 'smart-factory.exe'))
                and backend.exe == os.path.normcase(str(payload.root / BACKEND)), 'installed-process-path')
        result['payload'] = payload.receipt
        result['process_before'] = read_process_binding(main, backend, port)
        record, raw = fetch_sample(port, ENDPOINTS[0])
        result['health_record'] = record
        # JSON wire bytes are retained exactly as hex, including failed/partial responses.
        result['health_body_hex'] = raw.hex()
        require(record['request_success'], 'health-request-failed')
        result['sessions'] = runtime_sessions(strict_json(raw), backend, candidate=payload.candidate)
        result['process_after'] = read_process_binding(main, backend, port)
        require(result['process_before'] == result['process_after'], 'runtime-process-binding-changed')
        if expected_sessions is not None:
            require(result['sessions'] == expected_sessions, 'runtime-service-generation-changed')
        result['binding_status'] = 'PASS'
    except Exception as error:
        result['errors'].append(error_record(error))
    result['finished_ns'] = time.perf_counter_ns()
    return result
