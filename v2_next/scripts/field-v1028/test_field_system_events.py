"""Failure/empty distinction, bounded partial records, native read-only parity."""
from datetime import datetime, timedelta, timezone
import ctypes
import json
import os
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import field_system_events as events


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(seconds=6)
XML = '''<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><System>
<Provider Name="fixture"/><EventID>42</EventID><Level>4</Level>
<TimeCreated SystemTime="2026-01-01T00:00:01.1234567Z"/><EventRecordID>123</EventRecordID>
<Channel>System</Channel><Computer>DO_NOT_SAVE</Computer><Security UserID="DO_NOT_SAVE"/>
</System><EventData><Data>DO_NOT_SAVE</Data></EventData></Event>'''


class Reader:
    def __init__(self, records=(), failure=None, stop=None):
        self.records = iter(records)
        self.failure = failure
        self.stop = stop
        self.closed = []

    def fail(self, stage):
        if self.failure == stage:
            error = OSError('injected')
            error.winerror = 5
            raise error

    def query(self, xpath):
        self.fail('query')
        self.xpath = xpath
        return 100

    def next(self, query):
        self.fail('next')
        if self.stop:
            self.stop.set()
        return next(self.records, None)

    def render(self, event):
        self.fail('render')
        return '<bad>' if self.failure == 'parse' else XML

    def close(self, handle):
        self.closed.append(handle)
        self.fail('close')


class EventTests(unittest.TestCase):
    def run_capture(self, reader, stop=None):
        with patch.object(events, 'WindowsEventReader', return_value=reader):
            result = events.capture(START, END, stop or threading.Event())
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertFalse(result['promotion_allowed'])
        self.assertEqual(result['captured_record_count'], len(result['events']))
        self.assertNotIn('DO_NOT_SAVE', json.dumps(result))
        return result

    def test_successful_empty_is_explicit_and_query_handle_is_closed(self):
        reader = Reader()
        result = self.run_capture(reader)
        self.assertEqual((result['query_status'], result['matched_record_count'], result['events']),
                         ('COMPLETE', 0, []))
        self.assertTrue(result['end_of_results'])
        self.assertEqual(result['errors'], [])
        self.assertEqual(reader.closed, [100])
        self.assertEqual(result['xpath'], "*[System[TimeCreated[@SystemTime >= '2026-01-01T00:00:00.000000Z' and @SystemTime <= '2026-01-01T00:00:06.000000Z']]]")

    def test_nonempty_records_and_all_handles_survive_without_sensitive_fields(self):
        reader = Reader([1, 2])
        result = self.run_capture(reader)
        self.assertEqual((result['query_status'], result['matched_record_count']), ('COMPLETE', 2))
        self.assertEqual(result['events'][0], dict(record_id=123, event_id=42, level=4,
            provider='fixture', time_created_utc='2026-01-01T00:00:01.1234567Z'))
        self.assertEqual(reader.closed, [1, 2, 100])

    def test_query_next_render_parse_and_close_failures_never_claim_empty_success(self):
        for failed, closed in [('query', []), ('next', [100]), ('render', [1, 100]),
                               ('parse', [1, 100]), ('close', [1, 100])]:
            with self.subTest(failed=failed):
                reader = Reader([1], failure=failed)
                result = self.run_capture(reader)
                self.assertEqual(result['query_status'], 'INCOMPLETE')
                self.assertIsNone(result['matched_record_count'])
                self.assertEqual(result['errors'][0]['stage'], failed)
                self.assertEqual(reader.closed, closed)
                if failed != 'parse':
                    self.assertEqual(result['errors'][0]['winerror'], 5)

    def test_empty_query_with_close_failure_is_incomplete(self):
        result = self.run_capture(Reader(failure='close'))
        self.assertTrue(result['end_of_results'])
        self.assertEqual(result['events'], [])
        self.assertEqual(result['query_status'], 'INCOMPLETE')
        self.assertIsNone(result['matched_record_count'])

    def test_partial_result_is_preserved_when_next_fails(self):
        reader = Reader([1])
        calls = 0
        def next_event(query):
            nonlocal calls
            calls += 1
            if calls == 1:
                return 1
            raise OSError('later next failure')
        reader.next = next_event
        result = self.run_capture(reader)
        self.assertEqual(result['captured_record_count'], 1)
        self.assertIsNone(result['matched_record_count'])
        self.assertEqual(reader.closed, [1, 100])

    def test_exact_limit_requires_end_and_excess_handle_is_closed_without_rendering(self):
        with patch.object(events, 'MAX_EVENTS', 2):
            exact = self.run_capture(Reader([1, 2]))
            reader = Reader([1, 2, 3, 4])
            limited = self.run_capture(reader)
        self.assertEqual(exact['query_status'], 'COMPLETE')
        self.assertEqual((limited['query_status'], limited['captured_record_count']), ('INCOMPLETE', 2))
        self.assertEqual(limited['errors'][0]['stage'], 'record-limit')
        self.assertFalse(limited['end_of_results'])
        self.assertEqual(reader.closed, [1, 2, 3, 100])

    def test_cancellation_before_query_and_during_final_next_is_not_complete(self):
        stop = threading.Event(); stop.set()
        reader = Reader()
        result = self.run_capture(reader, stop)
        self.assertEqual(result['errors'][0]['type'], 'InterruptedError')
        self.assertEqual(reader.closed, [])
        stop.clear()
        reader = Reader(stop=stop)
        result = self.run_capture(reader, stop)
        self.assertEqual(result['query_status'], 'INCOMPLETE')
        self.assertTrue(result['end_of_results'])
        self.assertEqual(reader.closed, [100])

    def test_cooperative_deadline_retains_closeout_even_after_end_of_results(self):
        reader = Reader()
        with patch.object(events.time, 'perf_counter_ns', side_effect=[0, 0, 0, 5_000_000_000, 5_000_000_001]):
            result = self.run_capture(reader)
        self.assertEqual(result['query_status'], 'INCOMPLETE')
        self.assertEqual(result['errors'][0]['type'], 'TimeoutError')
        self.assertEqual(reader.closed, [100])

    def test_cancellation_while_closing_cannot_claim_success(self):
        stop = threading.Event()
        reader = Reader()
        original_close = reader.close
        def close(handle):
            original_close(handle)
            stop.set()
        reader.close = close
        result = self.run_capture(reader, stop)
        self.assertEqual(result['query_status'], 'INCOMPLETE')
        self.assertEqual(result['errors'][0]['type'], 'InterruptedError')
        self.assertEqual(reader.closed, [100])

    def test_initialization_failure_is_not_empty_success(self):
        with patch.object(events, 'WindowsEventReader', side_effect=OSError('load failed')):
            result = events.capture(START, END, threading.Event())
        self.assertEqual(result['query_status'], 'INCOMPLETE')
        self.assertEqual(result['errors'][0]['stage'], 'initialize')
        self.assertIsNone(result['matched_record_count'])

    def test_invalid_window_never_opens_log(self):
        for first, last in [(END, START), (START, START+timedelta(seconds=1201)),
                            (START.replace(tzinfo=None), END),
                            (START.astimezone(timezone(timedelta(hours=9))), END)]:
            with self.subTest(first=first), patch.object(events, 'WindowsEventReader') as reader:
                result = events.capture(first, last, threading.Event())
            reader.assert_not_called()
            self.assertEqual(result['errors'][0]['stage'], 'window')
            self.assertEqual(result['query_status'], 'INCOMPLETE')

    def test_malformed_or_oversize_xml_does_not_publish_metadata(self):
        for xml in ['<bad>', XML.replace('<System>', '<Other>').replace('</System>', '</Other>'),
                    XML.replace('System</Channel>', 'Security</Channel>'),
                    XML.replace('Name="fixture"', ''), '<!DOCTYPE Event>'+XML,
                    XML + (' ' * events.MAX_XML_BYTES)]:
            with self.subTest(xml=xml[:80]), self.assertRaises((ValueError, events.ElementTree.ParseError)):
                events.event_metadata(xml)


@unittest.skipUnless(os.name == 'nt', 'Native Windows read-only checks')
class NativeEventTests(unittest.TestCase):
    def test_native_next_only_no_more_items_is_successful_end(self):
        reader = events.WindowsEventReader()
        for code in (259, 5, 1460, 15011):
            def failed_next(*args):
                ctypes.set_last_error(code)
                return 0
            reader.api = SimpleNamespace(EvtNext=failed_next)
            if code == 259:
                self.assertIsNone(reader.next(100))
            else:
                with self.assertRaises(OSError) as failure:
                    reader.next(100)
                self.assertEqual(failure.exception.winerror, code)

    def test_native_missing_results_invalid_query_and_render_error_are_distinct(self):
        first = datetime(1900, 1, 1, tzinfo=timezone.utc)
        empty = events.capture(first, first+timedelta(seconds=1), threading.Event())
        self.assertEqual((empty['query_status'], empty['matched_record_count']), ('COMPLETE', 0))
        reader = events.WindowsEventReader()
        with self.assertRaises(OSError) as failure:
            reader.query('invalid[')
        self.assertIsInstance(failure.exception.winerror, int)
        # Render an invalid handle, exercising the size-call error code path.
        with self.assertRaises(OSError) as failure:
            reader.render(0)
        self.assertNotEqual(failure.exception.winerror, 122)

    def test_native_closed_window_matches_powershell_records(self):
        # Select an existing retained event first; a recent quiet window alone
        # would only test empty parity and never exercise native XML rendering.
        reader = events.WindowsEventReader()
        query, event = None, None
        try:
            query = reader.query('*')
            event = reader.next(query)
            self.assertIsNotNone(event, 'System log has no retained event for nonempty parity')
            anchor = events.event_metadata(reader.render(event))
        finally:
            if event is not None:
                reader.close(event)
            if query is not None:
                reader.close(query)
        when = datetime.fromisoformat(anchor['time_created_utc'])
        start, end = when - timedelta(seconds=1), when + timedelta(seconds=1)
        result = events.capture(start, end, threading.Event())
        self.assertEqual(result['query_status'], 'COMPLETE', result['errors'])
        self.assertIn(anchor, result['events'])
        script = '''$ErrorActionPreference='Stop'; $rows=@(); try {
$rows=@(Get-WinEvent -FilterHashtable @{LogName='System';StartTime=[datetime]::Parse('%s');EndTime=[datetime]::Parse('%s')} -ErrorAction Stop)
} catch { if($_.FullyQualifiedErrorId -notlike 'NoMatchingEventsFound*'){throw} }
$items=@($rows|ForEach-Object {@{record_id=$_.RecordId;event_id=$_.Id;provider=$_.ProviderName;level=$_.Level;time_created_utc=$_.TimeCreated.ToUniversalTime().ToString('o')}})
ConvertTo-Json -InputObject $items -Depth 4 -Compress
''' % (start.isoformat(), end.isoformat())
        system = 'System32' if ctypes.sizeof(ctypes.c_void_p) == 8 else 'Sysnative'
        exe = Path(os.environ['WINDIR'])/system/'WindowsPowerShell/v1.0/powershell.exe'
        environment = dict(os.environ)
        environment.pop('PSModulePath', None)
        raw = subprocess.run([str(exe), '-NoProfile', '-NonInteractive', '-Command', script],
                             capture_output=True, timeout=30, env=environment,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(raw.returncode, 0, raw.stderr.decode(errors='replace'))
        expected = json.loads(raw.stdout)
        def normalize(rows):
            return sorted((r['record_id'], r['event_id'], r['provider'], r['level'],
                           datetime.fromisoformat(r['time_created_utc'])) for r in rows)
        self.assertEqual(normalize(result['events']), normalize(expected))
        print('NATIVE_SYSTEM_EVENT_PARITY_COUNT=' + str(len(expected)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
