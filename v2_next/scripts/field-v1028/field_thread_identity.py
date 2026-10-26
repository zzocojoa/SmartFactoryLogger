"""Hold read-only process/thread handles around a non-atomic external snapshot.

Native IDs alone are not identities. Failed/exited thread reads remain unbound;
no thread is suspended and no process handle has termination/write rights.
"""
import ctypes
from ctypes import wintypes
import os
import time

import field_installation_binding as binding


class ThreadEntry(ctypes.Structure):
    _fields_ = [(name, wintypes.DWORD) for name in ('size', 'usage', 'tid', 'pid')]
    _fields_ += [('base_priority', wintypes.LONG), ('delta_priority', wintypes.LONG), ('flags', wintypes.DWORD)]


class NativeTarget:
    def __init__(self, pid, created_filetime, executable):
        binding.require(os.name == 'nt' and ctypes.sizeof(ctypes.c_void_p) == 8
                        and ctypes.sizeof(ThreadEntry) == 28, 'frame-native-windows-x64')
        binding.require(type(pid) is int and 0 < pid < 2**32
                        and type(created_filetime) is int and 0 < created_filetime < 2**64,
                        'frame-native-identity')
        self.pid, self.created = pid, created_filetime
        self.executable = os.path.normcase(str(binding.plain_path(executable)))
        self.handle = None
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        times = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        declarations = {
            'OpenProcess': ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            'OpenThread': ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
            'WaitForSingleObject': ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            'GetProcessTimes': (times, wintypes.BOOL), 'GetThreadTimes': (times, wintypes.BOOL),
            'GetProcessIdOfThread': ([wintypes.HANDLE], wintypes.DWORD),
            'QueryFullProcessImageNameW': ([wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                           ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            'CreateToolhelp32Snapshot': ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
            'Thread32First': ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
            'Thread32Next': ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
        }
        for name, (args, result) in declarations.items():
            getattr(self.api, name).argtypes = args
            getattr(self.api, name).restype = result

    @staticmethod
    def check(success):
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

    def creation(self, function, handle):
        times = [wintypes.FILETIME() for _ in range(4)]
        self.check(function(handle, *[ctypes.byref(value) for value in times]))
        return times[0].dwLowDateTime + (times[0].dwHighDateTime << 32)

    def alive(self, handle):
        status = self.api.WaitForSingleObject(handle, 0)
        binding.require(status in (0, 258), 'frame-native-wait-failed')
        return status == 258

    def recheck(self):
        binding.require(self.handle is not None and self.alive(self.handle), 'frame-target-exited')
        binding.require(self.creation(self.api.GetProcessTimes, self.handle) == self.created,
                        'frame-target-generation-changed')
        size = wintypes.DWORD(32768)
        name = ctypes.create_unicode_buffer(size.value)
        self.check(self.api.QueryFullProcessImageNameW(self.handle, 0, name, ctypes.byref(size)))
        binding.require(os.path.normcase(name.value) == self.executable, 'frame-target-path-changed')
        return dict(pid=self.pid, created_filetime=self.created, executable=self.executable,
                    observed_ns=time.perf_counter_ns())

    def __enter__(self):
        binding.require(self.handle is None, 'frame-target-already-open')
        self.handle = self.api.OpenProcess(0x1000 | 0x100000, False, self.pid)
        self.check(self.handle)
        try:
            self.recheck()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            self.check(self.api.CloseHandle(handle))

    def threads(self):
        return ThreadHandles(self)


class ThreadHandles:
    def __init__(self, target):
        self.target = target
        self.handles, self.before, self.unavailable = {}, {}, []

    def __enter__(self):
        target, api = self.target, self.target.api
        target.recheck()
        snapshot = api.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            success = api.Thread32First(snapshot, ctypes.byref(entry))
            count = 0
            while success:
                count += 1
                binding.require(count <= 65536 and entry.size >= 16, 'frame-thread-snapshot-budget-or-abi')
                if entry.pid == target.pid:
                    tid = entry.tid
                    binding.require(len(self.before) + len(self.unavailable) < 512, 'frame-target-thread-budget')
                    handle = api.OpenThread(0x0800 | 0x100000, False, tid)
                    if not handle:
                        self.unavailable.append(dict(tid=tid, reason='open-failed', winerror=ctypes.get_last_error()))
                    else:
                        self.handles[tid] = handle
                        try:
                            binding.require(api.GetProcessIdOfThread(handle) == target.pid and target.alive(handle),
                                            'frame-thread-owner-or-liveness')
                            self.before[tid] = target.creation(api.GetThreadTimes, handle)
                        except (OSError, ValueError) as error:
                            self.unavailable.append(dict(tid=tid, reason=type(error).__name__))
                entry.size = ctypes.sizeof(entry)
                success = api.Thread32Next(snapshot, ctypes.byref(entry))
            binding.require(ctypes.get_last_error() == 18, 'frame-thread-enumeration-failed')  # NO_MORE_FILES
            target.recheck()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise
        finally:
            target.check(api.CloseHandle(snapshot))

    def finish(self):
        target, api = self.target, self.target.api
        target.recheck()
        result = {}
        for tid, created in self.before.items():
            handle = self.handles[tid]
            try:
                stable = (target.alive(handle) and api.GetProcessIdOfThread(handle) == target.pid
                          and target.creation(api.GetThreadTimes, handle) == created)
                result[tid] = dict(created_filetime=created, stable=stable)
            except (OSError, ValueError) as error:
                result[tid] = dict(created_filetime=created, stable=False, reason=type(error).__name__)
        return result

    def __exit__(self, *_):
        handles, self.handles = self.handles, {}
        failures = [handle for handle in handles.values() if not self.target.api.CloseHandle(handle)]
        binding.require(not failures, 'frame-thread-handle-close-failed')
