"""Best-effort native anchors for explicit health probes; no tracing or handles owned."""
import ctypes
from functools import lru_cache
import os
import threading
import time


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]

    @property
    def value(self) -> int:
        return (self.high << 32) | self.low


@lru_cache(maxsize=1)
def _api():
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise OSError("Windows x64 required")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.POINTER(_FileTime)
    declarations = {
        "GetCurrentProcess": ([], ctypes.c_void_p),
        "GetCurrentThread": ([], ctypes.c_void_p),
        "GetProcessTimes": ([ctypes.c_void_p, pointer, pointer, pointer, pointer], ctypes.c_int),
        "GetThreadTimes": ([ctypes.c_void_p, pointer, pointer, pointer, pointer], ctypes.c_int),
        "QueryPerformanceCounter": ([ctypes.POINTER(ctypes.c_int64)], ctypes.c_int),
        "QueryPerformanceFrequency": ([ctypes.POINTER(ctypes.c_int64)], ctypes.c_int),
    }
    for name, (arguments, result) in declarations.items():
        getattr(api, name).argtypes = arguments
        getattr(api, name).restype = result
    return api


def capture_health_clock() -> dict:
    """Failure cannot break health. Pseudo-handles must not be closed."""
    try:
        api = _api()
        created = []
        for function, handle in ((api.GetProcessTimes, api.GetCurrentProcess()),
                                 (api.GetThreadTimes, api.GetCurrentThread())):
            start, end, kernel, user = (_FileTime() for _ in range(4))
            if not function(handle, *(ctypes.byref(value) for value in (start, end, kernel, user))):
                raise OSError("native creation read failed")
            if start.value <= 0:
                raise ValueError("native creation missing")
            created.append(start.value)
        frequency, ticks = ctypes.c_int64(), ctypes.c_int64()
        if not api.QueryPerformanceFrequency(ctypes.byref(frequency)) or frequency.value <= 0:
            raise OSError("native frequency read failed")
        before = time.perf_counter_ns()
        if not api.QueryPerformanceCounter(ctypes.byref(ticks)):
            raise OSError("native counter read failed")
        after = time.perf_counter_ns()
        if ticks.value < 0 or after < before:
            raise ValueError("native clock order invalid")
        return {"status": "OBSERVED", "pid": os.getpid(), "tid": threading.get_native_id(),
                "process_created_filetime": created[0], "thread_created_filetime": created[1],
                "perf_before_ns": before, "perf_after_ns": after,
                "qpc_ticks": ticks.value, "qpc_frequency": frequency.value}
    except (OSError, ValueError) as error:
        # Fixed type only; no system/provider exception text in response headers.
        return {"status": "UNAVAILABLE", "error_type": type(error).__name__}
