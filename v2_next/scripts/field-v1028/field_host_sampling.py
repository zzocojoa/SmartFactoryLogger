"""Read-only host attribution for diagnostics; never a field performance gate.

Capture CPU counters for the host and all visible process generations so a later
diagnostic can distinguish application, collector, and other host activity.
Command lines, environments, usernames, connections, and file paths are excluded.
"""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import math
import ntpath
import os
import time

import psutil


SCOPE = 'HOST_ATTRIBUTION_DIAGNOSTIC_NOT_RELEASE_QA'


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


class ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)]
    _fields_ += [(name, ctypes.c_size_t) for name in (
        'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
        'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]


class WindowsProcessReader:
    """Read one process object through a limited-query handle; no slow fallback.

    A single handle binds creation/CPU/memory/name to the same kernel object even
    if its numeric PID is reused. CAPTURED does not assert the process is alive.
    https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes
    https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo
    """
    def __init__(self):
        if os.name != 'nt':
            raise OSError('Windows required')
        if ctypes.sizeof(ProcessMemoryCounters) != (72 if ctypes.sizeof(ctypes.c_void_p) == 8 else 40):
            raise RuntimeError('PROCESS_MEMORY_COUNTERS ABI mismatch')
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        declarations = {
            'OpenProcess': ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
            'GetProcessTimes': ([wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4, wintypes.BOOL),
            'K32GetProcessMemoryInfo': ([wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters),
                                      wintypes.DWORD], wintypes.BOOL),
            'QueryFullProcessImageNameW': ([wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                           ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
        }
        for name, (args, result) in declarations.items():
            getattr(self.api, name).argtypes = args
            getattr(self.api, name).restype = result

    def read(self, pid):
        row = {'pid': pid, 'started_ns': time.perf_counter_ns(), 'status': 'UNAVAILABLE'}
        if pid == 0:
            row.update(reason='idle-pseudo-process-excluded', finished_ns=time.perf_counter_ns())
            return row
        handle = None
        try:
            handle = self.api.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION only.
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
            if not self.api.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                           ctypes.byref(kernel), ctypes.byref(user)):
                raise ctypes.WinError(ctypes.get_last_error())
            row['cpu_observed_ns'] = time.perf_counter_ns()
            ticks = lambda value: (value.dwHighDateTime << 32) | value.dwLowDateTime
            memory = ProcessMemoryCounters()
            memory.cb = ctypes.sizeof(memory)
            if not self.api.K32GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
                raise ctypes.WinError(ctypes.get_last_error())
            size = wintypes.DWORD(32768)
            name = ctypes.create_unicode_buffer(size.value)
            if not self.api.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())
            row.update(name=ntpath.basename(name.value), created=(ticks(created) - 116444736000000000) / 1e7,
                       created_100ns=ticks(created), cpu_user_seconds=ticks(user) / 1e7,
                       cpu_system_seconds=ticks(kernel) / 1e7, rss_bytes=memory.WorkingSetSize,
                       vms_bytes=memory.PagefileUsage, status='CAPTURED')
        except OSError as error:
            row.update(reason=type(error).__name__, winerror=getattr(error, 'winerror', None))
        finally:
            if handle and not self.api.CloseHandle(handle):
                row.update(status='UNAVAILABLE', reason='CloseHandleFailed', winerror=ctypes.get_last_error())
        row['finished_ns'] = time.perf_counter_ns()
        return row


def capture_host(*, process_limit=4096):
    if type(process_limit) is not int or not 1 <= process_limit <= 4096:
        raise ValueError('Invalid process count budget')
    started = time.perf_counter_ns()
    own_cpu_started = time.process_time_ns()
    result = {'scope': SCOPE, 'started_ns': started,
              'observed_utc': datetime.now(timezone.utc).isoformat(),
              'logical_cpus': psutil.cpu_count(logical=True), 'processes': [], 'errors': [],
              'truncated': False, 'release_gate': 'HOLD', 'promotion_allowed': False,
              'resource_performance_gate': 'NOT_EVALUATED'}
    try:
        reader = WindowsProcessReader()
        cpu = psutil.cpu_times()
        memory = psutil.virtual_memory()
        result['host'] = {'cpu_user_seconds': cpu.user, 'cpu_system_seconds': cpu.system,
                          'cpu_idle_seconds': cpu.idle, 'memory_total_bytes': memory.total,
                          'memory_available_bytes': memory.available,
                          'counter_observed_ns': time.perf_counter_ns()}
        for pid in psutil.pids():
            if len(result['processes']) >= process_limit:
                result['truncated'] = True
                break
            result['processes'].append(reader.read(pid))
    except (psutil.Error, OSError) as error:
        result['errors'].append(type(error).__name__)
    result['finished_ns'] = time.perf_counter_ns()
    result['capture_ms'] = (result['finished_ns'] - started) / 1e6
    result['collector_cpu_ms'] = (time.process_time_ns() - own_cpu_started) / 1e6
    result['unavailable_processes'] = sum(p['status'] != 'CAPTURED' for p in result['processes'])
    return result


def compare_host(before, after):
    """Counter deltas only; missing/reused/decreasing values are not zero usage."""
    result = {'scope': SCOPE, 'host_cpu_percent': None, 'process_intervals': [],
              'unmeasured': [], 'partial': True, 'release_gate': 'HOLD', 'promotion_allowed': False,
              'resource_performance_gate': 'NOT_EVALUATED'}
    cpus = after.get('logical_cpus')
    if type(cpus) is not int or cpus <= 0 or before.get('logical_cpus') != cpus:
        result['unmeasured'].append('logical-cpu-count-unavailable-or-changed')
        return result
    first, last = before.get('host', {}), after.get('host', {})
    keys = ('cpu_user_seconds', 'cpu_system_seconds', 'cpu_idle_seconds')
    if (all(_number(item.get(k)) for item in (first, last) for k in keys)
            and last.get('counter_observed_ns', 0) > first.get('counter_observed_ns', 0)):
        deltas = [last[k] - first[k] for k in keys]
        if min(deltas) >= 0 and sum(deltas) > 0:
            # Windows system includes interrupt/DPC time; do not add them again.
            result['host_cpu_percent'] = 100 * (deltas[0] + deltas[1]) / sum(deltas)
        else:
            result['unmeasured'].append('host-counters-decreased-or-no-tick')
    else:
        result['unmeasured'].append('host-counters-unavailable-or-invalid-time')
    identity_of = lambda p: (p['pid'], p.get('created_100ns', p.get('created')))
    old = {identity_of(p): p for p in before.get('processes', [])
           if p.get('status') == 'CAPTURED'}
    seen = set()
    for current in after.get('processes', []):
        identity = identity_of(current)
        if current.get('reason') == 'idle-pseudo-process-excluded':
            continue
        seen.add(identity)
        previous = old.get(identity)
        if current.get('status') != 'CAPTURED' or previous is None:
            result['unmeasured'].append({'pid': current['pid'], 'reason': 'process-unavailable-or-no-same-generation-baseline'})
            continue
        counter_time = lambda p: p.get('cpu_observed_ns', (p['started_ns'] + p['finished_ns']) / 2)
        elapsed = (counter_time(current) - counter_time(previous)) / 1e9
        cpu_keys = ('cpu_user_seconds', 'cpu_system_seconds')
        if not all(_number(p.get(k)) for p in (previous, current) for k in cpu_keys):
            result['unmeasured'].append({'pid': current['pid'], 'reason': 'invalid-process-counter'})
            continue
        delta = sum(current[k] - previous[k] for k in cpu_keys)
        if (elapsed <= 0 or not math.isfinite(elapsed)
                or any(current[k] < previous[k] for k in cpu_keys)):
            result['unmeasured'].append({'pid': current['pid'], 'reason': 'counter-decreased-or-invalid-time'})
            continue
        result['process_intervals'].append({'pid': current['pid'], 'created': current['created'],
            'name': current['name'], 'elapsed_seconds': elapsed, 'cpu_seconds': delta,
            'cpu_percent_machine_capacity': 100 * delta / elapsed / cpus,
            'rss_before_bytes': previous['rss_bytes'], 'rss_after_bytes': current['rss_bytes'],
            'vms_before_bytes': previous['vms_bytes'], 'vms_after_bytes': current['vms_bytes']})
    for identity in old.keys() - seen:
        previous = old[identity]
        result['unmeasured'].append({'pid': previous['pid'], 'created': previous['created'],
                                    'reason': 'process-not-observed-at-end'})
    result['limitations'] = [
        'Process enumeration is sequential, not an atomic host snapshot.',
        'Protected, exited, and new process generations may have no measured interval.',
        'Process CPU uses per-process counter intervals; do not sum percentages as exact host CPU.',
        'Idle pseudo-process PID 0 is excluded from process CPU; host idle time remains measured.',
        'Windows vms_bytes is PagefileUsage/commit charge, not virtual address space size.',
        'Working-set sums include shared pages and are not unique physical memory.',
        'No thread scheduling, CPU stack, or causal attribution is captured.',
    ]
    result['partial'] = bool(before.get('truncated') or after.get('truncated')
                             or before.get('errors') or after.get('errors')
                             or any(p.get('status') != 'CAPTURED' and p.get('pid') != 0
                                    for p in before.get('processes', []))
                             or result['unmeasured'])
    return result
