"""Bounded System event metadata after sampling, inside the owned worker.

COMPLETE describes this query at this time, not historical log retention or QA.
Native calls are ultimately bounded by the existing worker/Job finalization
deadline. No messages, EventData, computer names or user identifiers are saved.
API contracts: https://learn.microsoft.com/en-us/windows/win32/wes/querying-for-events
"""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import os
import time
from xml.etree import ElementTree


MAX_EVENTS = 1000
MAX_XML_BYTES = 65536
QUERY_SECONDS = 5
NEXT_TIMEOUT_MS = 250
NS = '{http://schemas.microsoft.com/win/2004/08/events/event}'


def utc_now():
    return datetime.now(timezone.utc)


class WindowsEventReader:
    def __init__(self):
        if os.name != 'nt':
            raise OSError('Windows required')
        self.api = ctypes.WinDLL('wevtapi', use_last_error=True)
        declarations = {
            'EvtQuery': ([wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD], wintypes.HANDLE),
            'EvtNext': ([wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
                         wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            'EvtRender': ([wintypes.HANDLE, wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                           ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD),
                           ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            'EvtClose': ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (args, result) in declarations.items():
            getattr(self.api, name).argtypes = args
            getattr(self.api, name).restype = result

    def query(self, xpath):
        handle = self.api.EvtQuery(None, 'System', xpath, 0x1 | 0x100)  # Channel, forward; no error tolerance.
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def next(self, query):
        event, count = wintypes.HANDLE(), wintypes.DWORD()
        if not self.api.EvtNext(query, 1, ctypes.byref(event), NEXT_TIMEOUT_MS, 0, ctypes.byref(count)):
            error = ctypes.get_last_error()
            if error == 259:  # ERROR_NO_MORE_ITEMS is the only successful end.
                return None
            raise ctypes.WinError(error)
        if count.value != 1 or not event.value:
            raise ValueError('event-next-contract')
        return event.value

    def render(self, event):
        used, properties = wintypes.DWORD(), wintypes.DWORD()
        ok = self.api.EvtRender(None, event, 1, 0, None, ctypes.byref(used), ctypes.byref(properties))
        error = ctypes.get_last_error()
        if ok:
            raise ValueError('event-render-size-query-contract')
        if error != 122:  # ERROR_INSUFFICIENT_BUFFER
            raise ctypes.WinError(error)
        if not 2 <= used.value <= MAX_XML_BYTES or used.value % ctypes.sizeof(ctypes.c_wchar):
            raise ValueError('event-xml-size-budget')
        buffer = ctypes.create_unicode_buffer(used.value // ctypes.sizeof(ctypes.c_wchar))
        if not self.api.EvtRender(None, event, 1, ctypes.sizeof(buffer), buffer,
                                 ctypes.byref(used), ctypes.byref(properties)):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.value

    def close(self, handle):
        if not self.api.EvtClose(handle):
            raise ctypes.WinError(ctypes.get_last_error())


def event_metadata(xml):
    # No external entities or embedded DTD are part of the Windows event schema.
    if len(xml.encode('utf-16-le')) > MAX_XML_BYTES or '<!DOCTYPE' in xml or '<!ENTITY' in xml:
        raise ValueError('event-xml-contract')
    root = ElementTree.fromstring(xml)
    system = root.find(NS + 'System')
    if root.tag != NS + 'Event' or system is None:
        raise ValueError('event-system-missing')
    provider = system.find(NS + 'Provider')
    created = system.find(NS + 'TimeCreated')
    if provider is None or not provider.get('Name') or created is None or not created.get('SystemTime'):
        raise ValueError('event-metadata-missing')
    if system.findtext(NS + 'Channel') != 'System':
        raise ValueError('event-channel-mismatch')
    return dict(record_id=int(system.findtext(NS + 'EventRecordID')),
                event_id=int(system.findtext(NS + 'EventID')), provider=provider.get('Name'),
                level=int(system.findtext(NS + 'Level')), time_created_utc=created.get('SystemTime'))


def capture(start, end, stop):
    """Read a fixed UTC interval; preserve partial records and every failure."""
    started = time.perf_counter_ns()
    result = dict(schema='sfl-system-event-query-v1', query_status='INCOMPLETE', channel='System',
                  window_start_utc=start.isoformat(), window_end_utc=end.isoformat(),
                  query_started_utc=utc_now().isoformat(), started_ns=started,
                  max_events=MAX_EVENTS, max_xml_bytes=MAX_XML_BYTES,
                  cooperative_timeout_seconds=QUERY_SECONDS, next_timeout_ms=NEXT_TIMEOUT_MS,
                  events=[], errors=[], end_of_results=False, captured_record_count=0,
                  matched_record_count=None, release_gate='HOLD', promotion_allowed=False)
    reader, query, event = None, None, None
    stage = 'window'

    def error_record(error, where):
        result['errors'].append(dict(stage=where, type=type(error).__name__,
                                     winerror=getattr(error, 'winerror', None)))

    def check_budget():
        if stop.is_set():
            raise InterruptedError('event-query-cancelled')
        if time.perf_counter_ns() - started >= QUERY_SECONDS * 1_000_000_000:
            raise TimeoutError('event-query-time-budget')

    def close(handle):
        if handle is not None:
            try:
                reader.close(handle)
            except Exception as error:
                error_record(error, 'close')

    try:
        if (start.utcoffset() != timezone.utc.utcoffset(start)
                or end.utcoffset() != timezone.utc.utcoffset(end)
                or not 0 <= (end - start).total_seconds() <= 1200):
            raise ValueError('event-query-window-budget')
        first, last = (value.isoformat(timespec='microseconds').replace('+00:00', 'Z') for value in (start, end))
        result['xpath'] = f"*[System[TimeCreated[@SystemTime >= '{first}' and @SystemTime <= '{last}']]]"
        stage = 'budget'
        check_budget()
        stage = 'initialize'
        reader = WindowsEventReader()
        stage = 'query'
        query = reader.query(result['xpath'])
        while True:
            stage = 'budget'
            check_budget()
            stage = 'next'
            event = reader.next(query)
            if event is None:
                result['end_of_results'] = True
                break
            if len(result['events']) >= MAX_EVENTS:
                stage = 'record-limit'
                raise ValueError('event-record-budget')
            stage = 'render'
            xml = reader.render(event)
            stage = 'parse'
            result['events'].append(event_metadata(xml))
            close(event)
            event = None
            if result['errors']:
                break
    except Exception as error:
        error_record(error, stage)
    finally:
        close(event)
        close(query)
    # Cancellation or a slow close must not turn into a completed empty query.
    if not result['errors']:
        try:
            check_budget()
        except Exception as error:
            error_record(error, 'budget')
    result.update(captured_record_count=len(result['events']), finished_ns=time.perf_counter_ns(),
                  query_finished_utc=utc_now().isoformat())
    if result['end_of_results'] and not result['errors']:
        result.update(query_status='COMPLETE', matched_record_count=len(result['events']))
    return result
