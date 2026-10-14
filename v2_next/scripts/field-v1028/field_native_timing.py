"""Read only this process/thread identity and clocks for later ETW correlation.

No tracing session is started. Boundary CPU samples are not a measurement of
server time, ready-thread delay, GIL contention, or an exact request CPU total.
"""
import ctypes
from functools import lru_cache
import os
import threading
import time


class FileTime(ctypes.Structure):
    _fields_ = [('low', ctypes.c_uint32), ('high', ctypes.c_uint32)]

    @property
    def value(self):
        return (self.high << 32) | self.low


class _WindowsClock:
    def __init__(self):
        if os.name != 'nt' or ctypes.sizeof(ctypes.c_void_p) != 8 or ctypes.sizeof(FileTime) != 8:
            raise OSError('Windows x64 clock identity required')
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        pointer = ctypes.POINTER(FileTime)
        declarations = {
            'GetCurrentProcess': ([], ctypes.c_void_p),
            'GetCurrentThread': ([], ctypes.c_void_p),
            'GetProcessTimes': ([ctypes.c_void_p, pointer, pointer, pointer, pointer], ctypes.c_int),
            'GetThreadTimes': ([ctypes.c_void_p, pointer, pointer, pointer, pointer], ctypes.c_int),
            'QueryPerformanceCounter': ([ctypes.POINTER(ctypes.c_int64)], ctypes.c_int),
            'QueryPerformanceFrequency': ([ctypes.POINTER(ctypes.c_int64)], ctypes.c_int),
        }
        for name, (arguments, result) in declarations.items():
            getattr(self.api, name).argtypes = arguments
            getattr(self.api, name).restype = result
        frequency = ctypes.c_int64()
        self.check(self.api.QueryPerformanceFrequency(ctypes.byref(frequency)))
        if frequency.value <= 0:
            raise ValueError('Invalid QPC frequency')
        self.frequency = frequency.value

    @staticmethod
    def check(success):
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

    def creation(self, function, handle):
        created, exited, kernel, user = (FileTime() for _ in range(4))
        self.check(function(handle, *(ctypes.byref(v) for v in (created, exited, kernel, user))))
        if created.value <= 0:
            raise ValueError('Missing creation FILETIME')
        return created.value

    def identity(self):
        # Pseudo-handles refer to the calling process/thread, require no lookup,
        # and must not be closed. Creation times disambiguate reused PID/TID.
        return {'pid': os.getpid(), 'native_thread_id': threading.get_native_id(),
                'process_created_filetime': self.creation(self.api.GetProcessTimes, self.api.GetCurrentProcess()),
                'thread_created_filetime': self.creation(self.api.GetThreadTimes, self.api.GetCurrentThread())}

    def boundary(self):
        ticks = ctypes.c_int64()
        before = time.perf_counter_ns()
        self.check(self.api.QueryPerformanceCounter(ctypes.byref(ticks)))
        cpu = time.thread_time_ns()
        after = time.perf_counter_ns()
        if ticks.value < 0 or cpu < 0 or after < before:
            raise ValueError('Invalid native timing boundary')
        return {'perf_before_ns': before, 'qpc_ticks': ticks.value, 'qpc_frequency': self.frequency,
                'thread_cpu_ns': cpu, 'perf_after_ns': after}


@lru_cache(maxsize=1)
def _clock():
    return _WindowsClock()


_thread_identity = threading.local()


def capture():
    """A failed native read stays unavailable; HTTP evidence must survive it."""
    result = {'schema': 'sfl-self-thread-clock-v1', 'status': 'UNAVAILABLE', 'identity': None,
              'boundary': None, 'error': None}
    try:
        clock = _clock()
        cached = getattr(_thread_identity, 'value', None)
        if cached is None or cached['pid'] != os.getpid():
            cached = clock.identity()
            _thread_identity.value = cached
        result['identity'] = dict(cached)
        result['boundary'] = clock.boundary()
        result['status'] = 'OBSERVED'
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'reason': str(error)[:512],
                           'winerror': getattr(error, 'winerror', None)}
    return result


def interval(begin, end):
    """Validate a join and preserve clock uncertainty, without latency attribution."""
    result = {'status': 'UNAVAILABLE', 'reason': None, 'thread_cpu_delta_ns': None,
              'qpc_offset_lower_ns': None, 'qpc_offset_upper_ns': None}
    try:
        if any(s['schema'] != 'sfl-self-thread-clock-v1' or s['status'] != 'OBSERVED'
               or s['error'] is not None for s in (begin, end)):
            raise ValueError('boundary-unavailable')
        for sample in (begin, end):
            identity = sample['identity']
            for key in ('pid', 'native_thread_id', 'process_created_filetime', 'thread_created_filetime'):
                if type(identity[key]) is not int or not 0 < identity[key] < 2**64:
                    raise ValueError('invalid-process-or-thread-identity')
            if identity['pid'] >= 2**32 or identity['native_thread_id'] >= 2**32:
                raise ValueError('invalid-process-or-thread-id')
        if begin['identity'] != end['identity']:
            raise ValueError('process-or-thread-identity-changed')
        left, right = begin['boundary'], end['boundary']
        frequency = left['qpc_frequency']
        if type(frequency) is not int or frequency <= 0 or right['qpc_frequency'] != frequency:
            raise ValueError('qpc-frequency-changed')
        bounds = []
        for sample in (left, right):
            if any(type(sample[k]) is not int or sample[k] < 0 for k in sample):
                raise ValueError('invalid-boundary-value')
            if sample['perf_after_ns'] < sample['perf_before_ns']:
                raise ValueError('invalid-boundary-order')
            numerator = sample['qpc_ticks'] * 1_000_000_000
            # Conservative integer bounds; no floating-point loss on QPC ticks.
            bounds.append((sample['perf_before_ns'] - (numerator + frequency - 1) // frequency,
                           sample['perf_after_ns'] - numerator // frequency))
        if right['perf_before_ns'] < left['perf_after_ns'] or right['qpc_ticks'] < left['qpc_ticks']:
            raise ValueError('boundary-order-reversed')
        delta = right['thread_cpu_ns'] - left['thread_cpu_ns']
        if delta < 0:
            raise ValueError('thread-cpu-counter-regressed')
        lower, upper = max(b[0] for b in bounds), min(b[1] for b in bounds)
        if lower > upper:
            raise ValueError('clock-offset-intervals-disjoint')
        result.update(status='CORRELATABLE_BOUNDARIES', thread_cpu_delta_ns=delta,
                      qpc_offset_lower_ns=lower, qpc_offset_upper_ns=upper)
    except (KeyError, TypeError, ValueError) as error:
        result['reason'] = str(error)
    return result
