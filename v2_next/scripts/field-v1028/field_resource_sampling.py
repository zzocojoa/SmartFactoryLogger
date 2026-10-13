"""Field resource recorder; no installation, process control, or release approval.

Disk performance IOCTLs enable/query Windows counters, as does psutil's Windows
disk reader. Never issue PERFORMANCE_OFF or change diskperf configuration here.
Synchronous native reads need an outer watchdog in the eventual field launcher.
"""
import ctypes
from ctypes import wintypes
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import threading
import time

import psutil

from field_http_sampling import _prepare_output, observation_origin


class DiskPerformance(ctypes.Structure):
    _fields_ = [(key, ctypes.c_int64) for key in
                ('BytesRead', 'BytesWritten', 'ReadTime', 'WriteTime', 'IdleTime')]
    _fields_ += [(key, ctypes.c_uint32) for key in
                 ('ReadCount', 'WriteCount', 'QueueDepth', 'SplitCount')]
    _fields_ += [('QueryTime', ctypes.c_int64), ('StorageDeviceNumber', ctypes.c_uint32),
                ('StorageManagerName', ctypes.c_uint16 * 8)]


DISK_FIELDS = {'BytesRead': 'read_bytes', 'BytesWritten': 'write_bytes',
               'ReadTime': 'read_time_100ns', 'WriteTime': 'write_time_100ns',
               'IdleTime': 'idle_time_100ns', 'ReadCount': 'read_count',
               'WriteCount': 'write_count', 'QueueDepth': 'queue_depth',
               'SplitCount': 'split_count', 'QueryTime': 'query_time_100ns_since_1601',
               'StorageDeviceNumber': 'storage_device_number'}
DISK_CUMULATIVE = ('read_bytes', 'write_bytes', 'read_count', 'write_count',
                   'read_time_100ns', 'write_time_100ns', 'idle_time_100ns', 'split_count')
PROCESS_CUMULATIVE = ('cpu_user_seconds', 'cpu_system_seconds', 'io_read_bytes', 'io_write_bytes')
PROCESS_GAUGES = ('rss_bytes', 'vms_bytes', 'threads', 'handles')


def error_record(error):
    return {'type': type(error).__name__, 'reason': str(error)[:2048],
            'winerror': getattr(error, 'winerror', None)}


class WindowsDiskReader:
    """Enumerate visible PhysicalDrive devices and preserve native counter units."""
    def __init__(self):
        if os.name != 'nt':
            raise OSError('Windows required')
        if ctypes.sizeof(DiskPerformance) != 88:
            raise RuntimeError('DISK_PERFORMANCE ABI mismatch')
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        declarations = {
            'QueryDosDeviceW': ([wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD], wintypes.DWORD),
            'CreateFileW': ([wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE], wintypes.HANDLE),
            'DeviceIoControl': ([wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                 ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                 ctypes.c_void_p], wintypes.BOOL),
            'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (args, result) in declarations.items():
            getattr(self.api, name).argtypes = args
            getattr(self.api, name).restype = result

    def names(self):
        for size in (4096, 16384, 65536, 262144):
            buffer = ctypes.create_unicode_buffer(size)
            count = self.api.QueryDosDeviceW(None, buffer, size)
            if count:
                return sorted({name for name in buffer[:count].split('\0')
                               if re.fullmatch(r'PhysicalDrive\d+', name)},
                              key=lambda name: int(name[13:]))
            if ctypes.get_last_error() != 122:
                raise ctypes.WinError(ctypes.get_last_error())
        raise OSError('DOS device enumeration exceeded bounded buffer')

    def read(self, name):
        if not re.fullmatch(r'PhysicalDrive\d+', name):
            raise ValueError('PhysicalDrive name required')
        started = time.perf_counter_ns()
        handle = self.api.CreateFileW('\\\\.\\' + name, 0, 3, None, 3, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            raw, returned = DiskPerformance(), wintypes.DWORD()
            if not self.api.DeviceIoControl(handle, 0x70020, None, 0, ctypes.byref(raw),
                                            ctypes.sizeof(raw), ctypes.byref(returned), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if returned.value != ctypes.sizeof(raw):
                raise ValueError('Incomplete DISK_PERFORMANCE response')
            result = {target: getattr(raw, source) for source, target in DISK_FIELDS.items()}
            result.update(name=name, started_ns=started, finished_ns=time.perf_counter_ns(),
                          storage_manager=''.join(chr(c) for c in raw.StorageManagerName).rstrip('\0 '),
                          raw_hex=bytes(raw).hex(), returned_bytes=returned.value)
            return result
        finally:
            if not self.api.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())

    def snapshot(self):
        started = time.perf_counter_ns()
        records, errors, names = [], [], []
        try:
            names = self.names()
            if not names:
                raise RuntimeError('No visible physical disks')
            for name in names:
                try:
                    records.append(self.read(name))
                except Exception as error:
                    errors.append({'device': name, **error_record(error)})
            if self.names() != names:
                errors.append({'type': 'TopologyChanged', 'reason': 'Disk names changed during sample'})
        except Exception as error:
            errors.append(error_record(error))
        return {'started_ns': started, 'finished_ns': time.perf_counter_ns(),
                'names': names, 'records': records, 'errors': errors,
                'scope': 'HOST_VISIBLE_PHYSICAL_DRIVES_NOT_PROCESS_ATTRIBUTED',
                'counter_enable_side_effect': True}


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    created: float
    exe: str

    @classmethod
    def read(cls, pid):
        process = psutil.Process(pid)
        return cls(pid, process.create_time(), os.path.normcase(process.exe()))

    def validate(self):
        if (type(self.pid) is not int or self.pid <= 0 or not number(self.created)
                or not isinstance(self.exe, str) or not os.path.isabs(self.exe)):
            raise ValueError('Explicit PID/create-time/executable identity required')


def process_snapshot(identity):
    identity.validate()
    started = time.perf_counter_ns()
    records, errors = [], []
    try:
        if ProcessIdentity.read(identity.pid) != identity:
            raise ValueError('Root process identity changed')
        root = psutil.Process(identity.pid)
        children = root.children(recursive=True)
        members = {(p.pid, p.create_time()) for p in [root, *children]}
        for pid, created in sorted(members):
            try:
                process = psutil.Process(pid)
                if process.create_time() != created:
                    raise ValueError('PID reused before read')
                begin = time.perf_counter_ns()
                with process.oneshot():
                    memory, cpu, io = process.memory_info(), process.cpu_times(), process.io_counters()
                    row = {'pid': pid, 'created': created, 'ppid': process.ppid(), 'exe': process.exe(),
                           'started_ns': begin, 'rss_bytes': memory.rss, 'vms_bytes': memory.vms,
                           'threads': process.num_threads(), 'handles': process.num_handles(),
                           'cpu_user_seconds': cpu.user, 'cpu_system_seconds': cpu.system,
                           'io_read_bytes': io.read_bytes, 'io_write_bytes': io.write_bytes,
                           'memory_raw': memory._asdict(), 'io_raw': io._asdict()}
                # Use a fresh object; psutil caches create_time on an existing object.
                if psutil.Process(pid).create_time() != created:
                    raise ValueError('PID reused during read')
                row['finished_ns'] = time.perf_counter_ns()
                records.append(row)
            except Exception as error:
                errors.append({'pid': pid, **error_record(error)})
        after = {(p.pid, p.create_time()) for p in [root, *root.children(recursive=True)]}
        if after != members or ProcessIdentity.read(identity.pid) != identity:
            errors.append({'type': 'MembershipChanged', 'reason': 'Process tree changed during sample'})
    except Exception as error:
        errors.append(error_record(error))
    return {'started_ns': started, 'finished_ns': time.perf_counter_ns(),
            'root': asdict(identity), 'records': records, 'errors': errors,
            'scope': 'OBSERVED_ROOT_AND_DESCENDANTS_NO_BETWEEN_SAMPLE_LIFETIME_COVERAGE'}


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def describe(values):
    if not values:
        return None
    edge = max(1, math.ceil(len(values) * .2))
    return {'count': len(values), 'min': min(values), 'max': max(values),
            'first': values[0], 'last': values[-1],
            'first_20pct_mean': statistics.mean(values[:edge]),
            'last_20pct_mean': statistics.mean(values[-edge:]),
            'mean_change': statistics.mean(values[-edge:]) - statistics.mean(values[:edge])}


def sample_issues(row):
    issues = []
    for group, keys, identity_keys in (
        ('process', PROCESS_CUMULATIVE + PROCESS_GAUGES, ('pid', 'created')),
        ('disk', DISK_CUMULATIVE + ('queue_depth', 'query_time_100ns_since_1601'),
         ('name', 'storage_device_number', 'storage_manager')),
    ):
        item = row.get(group, {})
        records = item.get('records', [])
        if item.get('errors') or not records:
            issues.append(group + '-incomplete')
        seen = set()
        for record in records:
            if not all(key in record for key in identity_keys):
                issues.append(group + '-identity-missing')
                continue
            identity = tuple(record[k] for k in identity_keys)
            if identity in seen:
                issues.append(group + '-duplicate-identity')
            seen.add(identity)
            if not all(number(record.get(k)) for k in keys):
                issues.append(group + '-invalid-counter')
            integer_keys = PROCESS_GAUGES + ('pid', 'io_read_bytes', 'io_write_bytes') if group == 'process' else keys + ('storage_device_number',)
            if not all(type(record.get(k)) is int and record[k] >= 0 for k in integer_keys):
                issues.append(group + '-invalid-integer-counter')
            if group == 'process' and (not number(record.get('created')) or record['created'] <= 0
                                       or record.get('pid', 0) <= 0 or not isinstance(record.get('exe'), str)):
                issues.append('process-invalid-identity')
            if group == 'disk' and (not isinstance(record.get('name'), str)
                                   or not re.fullmatch(r'PhysicalDrive\d+', record['name'])
                                   or not isinstance(record.get('storage_manager'), str)
                                   or not record['storage_manager']):
                issues.append('disk-invalid-identity')
            if not (type(record.get('started_ns')) is int and type(record.get('finished_ns')) is int
                    and 0 < record['started_ns'] <= record['finished_ns']):
                issues.append(group + '-invalid-time')
        if group == 'disk' and set(item.get('names', [])) != {r.get('name') for r in records}:
            issues.append('disk-enumeration-incomplete')
        if group == 'process':
            root = item.get('root', {})
            if (root.get('pid'), root.get('created')) not in seen:
                issues.append('process-root-missing')
            elif not any(r.get('pid') == root['pid'] and r.get('created') == root['created']
                         and os.path.normcase(r.get('exe', '')) == root.get('exe') for r in records):
                issues.append('process-root-executable-mismatch')
    return issues


def interval_metrics(earlier, later, logical_cpus):
    """Never bridge incomplete samples, membership changes, or counter resets."""
    invalid = sample_issues(earlier) + sample_issues(later)
    if earlier.get('process', {}).get('root') != later.get('process', {}).get('root'):
        invalid.append('root-identity-changed')
    if invalid or type(logical_cpus) is not int or logical_cpus < 1:
        return {'status': 'NOT_MEASURED', 'reasons': invalid or ['logical-cpu-count']}
    result = {'status': 'MEASURED', 'process': {}, 'disk': {}, 'reasons': []}
    for group, identity_fields, counters in (
        ('process', ('pid', 'created'), PROCESS_CUMULATIVE),
        ('disk', ('name', 'storage_device_number', 'storage_manager'), DISK_CUMULATIVE),
    ):
        a, b = [{tuple(r[k] for k in identity_fields): r for r in row[group]['records']}
                for row in (earlier, later)]
        if a.keys() != b.keys():
            result['reasons'].append(group + '-membership-changed')
            continue
        for identity, current in b.items():
            previous = a[identity]
            seconds = (current['started_ns'] - previous['started_ns']) / 1e9
            delta = {key: current[key] - previous[key] for key in counters}
            if seconds <= 0 or any(value < 0 for value in delta.values()):
                result['reasons'].append(group + '-counter-reset-or-time-invalid')
                continue
            values = {'elapsed_seconds': seconds, 'delta': delta}
            if group == 'process':
                values.update(cpu_percent_machine_capacity=100 * (
                    delta['cpu_user_seconds'] + delta['cpu_system_seconds']) / seconds / logical_cpus,
                    read_bytes_per_second=delta['io_read_bytes'] / seconds,
                    write_bytes_per_second=delta['io_write_bytes'] / seconds)
                label = str(current['pid']) + ':' + str(current['created'])
            else:
                values.update(read_bytes_per_second=delta['read_bytes'] / seconds,
                              write_bytes_per_second=delta['write_bytes'] / seconds,
                              read_operations_per_second=delta['read_count'] / seconds,
                              write_operations_per_second=delta['write_count'] / seconds,
                              read_time_delta_ms=delta['read_time_100ns'] / 10000,
                              write_time_delta_ms=delta['write_time_100ns'] / 10000)
                label = current['name']
            result[group][label] = values
    if result['reasons']:
        result['status'] = 'NOT_MEASURED'
    return result


def summarize_resources(rows, *, origin_ns, duration_seconds, cadence_seconds=5, logical_cpus):
    duration, step = round(duration_seconds * 1e9), round(cadence_seconds * 1e9)
    expected = duration // step + 1  # Include the final boundary if on cadence.
    issues, valid = [], []
    for sequence, row in enumerate(rows):
        target = origin_ns + sequence * step
        if (type(row.get('sequence')) is not int or row.get('sequence') != sequence or row.get('scheduled_ns') != target
                or row.get('kind') != 'sample'):
            issues.append({'sequence': sequence, 'reasons': ['slot-missing-cancelled-or-invalid']})
            continue
        reasons = sample_issues(row)
        if not (type(row.get('started_ns')) is int and target <= row['started_ns'] < target + step
                and type(row.get('finished_ns')) is int and row['started_ns'] <= row['finished_ns'] < target + step):
            reasons.append('sample-time-invalid')
        if reasons:
            issues.append({'sequence': sequence, 'reasons': reasons})
        else:
            valid.append(row)
    if len(rows) != expected:
        issues.append({'reasons': ['slot-count-mismatch']})
    roots = {json.dumps(row['process']['root'], sort_keys=True) for row in valid}
    if len(roots) != 1:
        issues.append({'reasons': ['root-identity-not-continuous']})
    intervals = []
    for a, b in zip(valid, valid[1:]):
        if b['sequence'] != a['sequence'] + 1:
            intervals.append({'status': 'NOT_MEASURED', 'reasons': ['sample-gap']})
        else:
            intervals.append(interval_metrics(a, b, logical_cpus))
    windows = []
    # Full 300-second windows after 120-second warmup, plus the final rolling window.
    ends = list(range(420, int(duration_seconds) + 1, 300))
    if duration_seconds >= 420 and (not ends or ends[-1] != duration_seconds):
        ends.append(duration_seconds)
    for end in ends:
        selected = [r for r in valid if origin_ns + (end - 300) * 1e9 <= r['scheduled_ns']
                    <= origin_ns + end * 1e9]
        span = (selected[-1]['started_ns'] - selected[0]['started_ns']) / 1e9 if selected else 0
        windows.append({'start_seconds': end - 300, 'end_seconds': end, 'count': len(selected),
                        'span_seconds': span, 'coverage_sufficient': len(selected) >= 48 and span >= 240,
                        'process_gauges_sum': {key: describe([sum(p[key] for p in r['process']['records'])
                                                          for r in selected]) for key in PROCESS_GAUGES}})
    return {'recording_status': 'COMPLETE' if not issues else 'INCOMPLETE', 'issues': issues,
            'expected_slots': expected, 'recorded_slots': len(rows), 'valid_samples': len(valid),
            'windows': windows, 'intervals': intervals,
            'unmeasured_intervals': sum(r['status'] != 'MEASURED' for r in intervals),
            'resource_coverage_status': 'SUFFICIENT' if windows and all(w['coverage_sufficient'] for w in windows)
                                        and not issues else 'NOT_MEASURED',
            'resource_performance_gate': 'NOT_EVALUATED',
            'limitations': ['RSS sum includes shared pages; not unique physical memory',
                            'Process I/O includes non-disk/cached activity',
                            'PhysicalDrive counters are host-wide, not application-attributed',
                            'Device number/manager are not immutable hardware serial identity',
                            'No per-operation disk latency, busy percent, or exhaustive open-file count'],
            'field_gate': 'NOT_EVALUATED', 'release_gate': 'HOLD', 'promotion_allowed': False}


def collect_resource_window(identity, output, *, duration_seconds, origin_ns=None,
                            cadence_seconds=5, stop_event=None):
    identity.validate()
    if (not number(duration_seconds) or not 0 < duration_seconds <= 7200
            or not number(cadence_seconds) or not .01 <= cadence_seconds <= 5):
        raise ValueError('Invalid resource duration or cadence')
    duration, step = round(duration_seconds * 1e9), round(cadence_seconds * 1e9)
    count = duration // step + 1
    if count > 5000:
        raise ValueError('Resource sample budget')
    if len(str(Path(output) / 'resource-00000.json')) > 240:
        raise ValueError('Resource output path exceeds final filename budget')
    origin = observation_origin(origin_ns)
    reader = WindowsDiskReader()
    output = _prepare_output(output)
    stop = stop_event if stop_event is not None else threading.Event()
    rows, files, errors = [], {}, []

    def write(name, value):
        raw = (json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
        with (output / name).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        files[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    logical_cpus = psutil.cpu_count(logical=True)
    write('origin.json', {'origin_ns': origin, 'duration_seconds': duration_seconds,
                         'cadence_seconds': cadence_seconds, 'root': asdict(identity),
                         'logical_cpus': logical_cpus, 'psutil_version': psutil.__version__,
                         'recorded_utc': datetime.now(timezone.utc).isoformat(),
                         'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                         'scope': 'RESOURCE_COMPONENT_ONLY'})
    finished = None
    try:
        for sequence in range(count):
            target = origin + sequence * step
            row = {'sequence': sequence, 'scheduled_ns': target}
            if stop.wait(max(0, (target - time.perf_counter_ns()) / 1e9)):
                row.update(kind='cancelled_remaining', remaining_slots=count - sequence)
            elif (finished is not None and finished >= target) or time.perf_counter_ns() >= target + step:
                row.update(kind='missed_slot')
            else:
                row.update(kind='sample', started_ns=time.perf_counter_ns())
                row['process'] = process_snapshot(identity)
                row['disk'] = reader.snapshot()
                row['finished_ns'] = time.perf_counter_ns()
            write(f'resource-{sequence:05d}.json', row)
            rows.append(row)
            if row['kind'] == 'sample':
                finished = time.perf_counter_ns()
            if row['kind'] == 'cancelled_remaining':
                break
    except Exception as error:
        errors.append(error_record(error))
        stop.set()
    stop.wait(max(0, (origin + duration - time.perf_counter_ns()) / 1e9))
    summary = summarize_resources(rows, origin_ns=origin, duration_seconds=duration_seconds,
                                  cadence_seconds=cadence_seconds, logical_cpus=logical_cpus)
    summary.update(origin_ns=origin, finished_ns=time.perf_counter_ns(), errors=errors,
                   stop_requested=stop.is_set())
    if errors or stop.is_set():
        summary['recording_status'] = 'INCOMPLETE'
        summary['resource_coverage_status'] = 'NOT_MEASURED'
    write('summary.json', summary)
    write('manifest.json', {'schema_version': 'sfl-field-resource-component-v1', 'files': dict(files)})
    return summary
