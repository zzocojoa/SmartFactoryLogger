"""Unnamed Windows job containing only the collector's own gated child tree."""
import ctypes
from ctypes import wintypes
import os


class BasicLimit(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', wintypes.DWORD), ('minimum_working_set', ctypes.c_size_t),
                ('maximum_working_set', ctypes.c_size_t), ('active_process_limit', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]


class ExtendedLimit(ctypes.Structure):
    _fields_ = [('basic', BasicLimit), ('io', ctypes.c_uint64 * 6),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


class Accounting(ctypes.Structure):
    _fields_ = [('user_time', ctypes.c_int64), ('kernel_time', ctypes.c_int64),
                ('period_user_time', ctypes.c_int64), ('period_kernel_time', ctypes.c_int64),
                ('page_faults', wintypes.DWORD), ('total_processes', wintypes.DWORD),
                ('active_processes', wintypes.DWORD), ('terminated_processes', wintypes.DWORD)]


class CollectorJob:
    def __init__(self):
        if os.name != 'nt' or ctypes.sizeof(ctypes.c_void_p) != 8:
            raise OSError('64-bit Windows required')
        if (ctypes.sizeof(BasicLimit), ctypes.sizeof(ExtendedLimit), ctypes.sizeof(Accounting)) != (64, 144, 48):
            raise RuntimeError('Windows job ABI mismatch')
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateJobObjectW': ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            'SetInformationJobObject': ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            'AssignProcessToJobObject': ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            'QueryInformationJobObject': ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
            'TerminateJobObject': ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            getattr(self.api, name).argtypes = arguments
            getattr(self.api, name).restype = result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            limits = ExtendedLimit()
            limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE; no breakaway flags.
            self._check(self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
        except BaseException:
            self.close()
            raise

    def _check(self, success):
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

    def assign_owned_process(self, process):
        # Windows multiprocessing sentinel is the process HANDLE created by
        # Process.start(), not a PID lookup. Caller gates execution until assign.
        self._check(self.api.AssignProcessToJobObject(self.handle, process.sentinel))

    def accounting(self):
        result = Accounting()
        self._check(self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(result), ctypes.sizeof(result), None))
        return {'total_processes': result.total_processes, 'active_processes': result.active_processes,
                'terminated_processes': result.terminated_processes}

    def terminate(self):
        self._check(self.api.TerminateJobObject(self.handle, 1))

    def close(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            self._check(self.api.CloseHandle(handle))
