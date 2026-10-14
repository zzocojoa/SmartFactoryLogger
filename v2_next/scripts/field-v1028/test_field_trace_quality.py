"""Quality rejection tests; synthetic XML does not establish real trace coverage."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from field_trace_quality import (
    EVENT_NS, TRACE_NS, HEADER_GUID, THREAD_GUID, assess, check_command,
    inspect_raw, inspect_receipt, inspect_report,
)


def event(class_guid, opcode, raw='9007199254740993', data='', error=''):
    return f'''<Event xmlns="{EVENT_NS}"><System>
    <Provider Guid="{{9e814aad-3204-11d2-9a82-006008a86939}}"/>
    <Version>2</Version><Opcode>{opcode}</Opcode><TimeCreated RawTime="{raw}"/>
    </System><EventData>{data}</EventData>{error}
    <ExtendedTracingInfo xmlns="{TRACE_NS}"><EventGuid>{{{class_guid}}}</EventGuid></ExtendedTracingInfo>
    </Event>'''


def raw_xml(**changes):
    fields = dict(PerfFreq=10000000, ReservedFlags='0x1', EventsLost=0, BuffersLost=0,
                  StartTime=133000000000000000, EndTime=133000000100000000,
                  BuffersWritten=1, NumberOfProcessors=8)
    fields.update(changes)
    header = event(HEADER_GUID, 0, data=''.join(f'<Data Name="{k}">{v}</Data>' for k, v in fields.items()))
    return '<Events>' + header + event(THREAD_GUID, 36) + event(THREAD_GUID, 50) + '</Events>'


def report_xml(events=3, lost=0, skipped=0):
    return f'''<Report name="tracerpt"><Section name="tracerptHeader"><Table name="collection"><Item>
    <Data name="buffers">1</Data><Data name="events">{events}</Data><Data name="lostEvents">{lost}</Data>
    <Data name="skippedEvents">{skipped}</Data></Item></Table></Section></Report>'''


def read_raw(text):
    return inspect_raw(io.BytesIO(text.encode('utf-8')))


def read_report(text):
    return inspect_report(io.BytesIO(text.encode('utf-16')))


class QualityTests(unittest.TestCase):
    def test_consistent_structure_is_not_causal_or_field_pass(self):
        raw = read_raw(raw_xml())
        result = assess(raw, read_report(report_xml()))
        self.assertEqual(raw['first_raw'], 9007199254740993)
        self.assertEqual(raw['headers'][0]['StartTime'], 133000000000000000)
        self.assertEqual(result['quality'], 'STRUCTURE_CONSISTENT_REQUIRES_CORRELATION')
        self.assertEqual(result['declared_loss'], 'ZERO_DECLARED_NOT_COVERAGE_PROOF')
        self.assertEqual(result['request_time_coverage'], 'NOT_EVALUATED')
        self.assertEqual(result['latency_cause'], 'UNDETERMINED')
        self.assertFalse(result['promotion_allowed'])

    def test_exit_zero_does_not_hide_processing_errors(self):
        text = raw_xml().replace('</Events>', event(THREAD_GUID, 50, error='<ProcessingErrorData><ErrorCode>15005</ErrorCode></ProcessingErrorData>') + '</Events>')
        raw = read_raw(text)
        self.assertEqual(raw['processing_errors'], 1)
        self.assertEqual(raw['scheduler_processing_errors'], 1)
        result = assess(raw, read_report(report_xml(events=4)))
        self.assertIn('event_decode_errors', result['issues'])
        self.assertEqual(result['quality'], 'INCOMPLETE_OR_UNUSABLE')

    def test_empty_provider_and_binary_payload_preserved_as_unknown(self):
        text = raw_xml().replace('<Provider Guid="{9e814aad-3204-11d2-9a82-006008a86939}"/>', '<Provider/>')
        text = text.replace('</Events>', event(THREAD_GUID, 36).replace('<EventData></EventData>', '<BinaryEventData>0102</BinaryEventData>') + '</Events>')
        raw = read_raw(text)
        self.assertEqual(raw['events'], 4)
        self.assertEqual(raw['missing_provider_guids'], 3)
        self.assertEqual(raw['opaque_binary_events'], 1)
        self.assertEqual(raw['scheduler_opaque_events'], 1)
        result = assess(raw, read_report(report_xml(events=4)))
        self.assertIn('provider_guids_missing', result['issues'])
        self.assertIn('opaque_binary_events_not_decoded', result['issues'])

    def test_loss_in_any_source_is_retained(self):
        for changes, report in ((dict(EventsLost=1), report_xml()), (dict(BuffersLost=1), report_xml()), ({}, report_xml(lost=1))):
            with self.subTest(changes=changes, report=report):
                self.assertEqual(assess(read_raw(raw_xml(**changes)), read_report(report))['declared_loss'], 'LOSS_DECLARED')
        raw = read_raw('<Events>' + event(THREAD_GUID, 36) + '</Events>')
        self.assertEqual(assess(raw, read_report(report_xml(events=1, lost=1)))['declared_loss'], 'LOSS_DECLARED')

    def test_count_skip_clock_and_closed_interval_rejections(self):
        result = assess(read_raw(raw_xml(ReservedFlags=2, PerfFreq=0, EndTime=0)), read_report(report_xml(events=9, skipped=2)))
        self.assertTrue({'qpc_clock_not_confirmed', 'finalized_positive_session_interval_not_confirmed',
                         'raw_report_event_count_mismatch', 'report_events_skipped'}.issubset(result['issues']))

    def test_missing_and_reversed_raw_times_retained(self):
        text = raw_xml().replace('RawTime="9007199254740993"', 'SystemTime="2026-01-01"', 1)
        text = text.replace('</Events>', event(THREAD_GUID, 36, raw='1') + '</Events>')
        raw = read_raw(text)
        self.assertEqual(raw['missing_raw_timestamps'], 1)
        self.assertEqual(raw['timestamp_reversals'], 1)
        self.assertEqual(raw['events'], 4)

    def test_multiple_headers_not_silently_combined(self):
        text = raw_xml().replace('</Events>', raw_xml().removeprefix('<Events>'))
        result = assess(read_raw(text), read_report(report_xml(events=6)))
        self.assertEqual(len(result['raw']['headers']), 2)
        self.assertIn('single_trace_header_not_available', result['issues'])

    def test_duplicate_fields_invalid_numbers_and_overflow(self):
        for value in ('-1', '1e3', '1.2', str(2**64)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_raw(raw_xml(EventsLost=value))
        with self.assertRaises(ValueError):
            read_raw(raw_xml().replace('</EventData>', '<Data Name="PerfFreq">1</Data></EventData>', 1))
        with self.assertRaises(ValueError):
            read_report(report_xml().replace('</Item>', '<Data name="events">3</Data></Item>'))

    def test_doctype_entities_utf8_utf16_and_split_chunks(self):
        for encoding in ('utf-8', 'utf-16', 'utf-32'):
            text = '<!DOCTYPE Events [<!ENTITY x "expanded">]>' + raw_xml()
            with self.subTest(encoding=encoding), self.assertRaisesRegex(ValueError, 'xml-declaration'):
                inspect_raw(io.BytesIO(text.encode(encoding)))
        with self.assertRaisesRegex(ValueError, 'xml-declaration'):
            inspect_raw(io.BytesIO(b' ' * 65532 + b'<!DOCTYPE Events>' + raw_xml().encode()))

    def test_event_budget_wrong_root_and_truncation(self):
        with self.assertRaisesRegex(ValueError, 'event-count-budget'):
            inspect_raw(io.BytesIO(raw_xml().encode()), max_events=2)
        with self.assertRaises(ValueError):
            read_raw('<NotEvents/>')
        with self.assertRaises(Exception):
            read_raw(raw_xml()[:-6])

    def test_command_must_bind_same_etl_and_raw_mode(self):
        base = dict(status='PASS', actual_exit_code=0, termination_requested=False,
                    job_after_cleanup=[2, 0, 0], errors=[], arguments=['-l', 'same.etl', '-o', 'raw.xml', '-of', 'XML', '-rts', '-y'])
        check_command(base, 'raw', 'same.etl', 'raw.xml')
        for arguments in (base['arguments'][:-2], base['arguments'] + ['-lr'],
                          base['arguments'] + ['-l', 'same.etl'],
                          ['-l', 'other.etl', '-o', 'raw.xml', '-of', 'XML', '-rts']):
            changed = dict(base, arguments=arguments)
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                check_command(changed, 'raw', 'same.etl', 'raw.xml')
        for update in ({'actual_exit_code': 1}, {'actual_exit_code': False}, {'termination_requested': True}, {'job_after_cleanup': [2, 1, 0]}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                check_command(dict(base, **update), 'raw', 'same.etl', 'raw.xml')

    def test_locked_artifact_tampering_and_receipt_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {role: root / (role + '.dat') for role in ('etl', 'raw_xml', 'report_xml', 'raw_command', 'report_command')}
            paths['etl'].write_bytes(b'synthetic binding fixture, not a real ETL')
            paths['raw_xml'].write_text(raw_xml(), encoding='utf-8')
            paths['report_xml'].write_text(report_xml(), encoding='utf-8')
            for role in ('raw', 'report'):
                args = ['-l', str(paths['etl']), '-o', str(paths[role + '_xml']), '-of', 'XML']
                args += ['-rts'] if role == 'raw' else ['-report', str(paths['report_xml'])]
                paths[role + '_command'].write_text(json.dumps(dict(status='PASS', actual_exit_code=0, termination_requested=False, job_after_cleanup=[1, 0, 0], errors=[], arguments=args)), encoding='utf-8')
            receipt = dict(schema='sfl-tracerpt-decode-inputs-v1', source_scope='PUBLIC_FIXTURE', files={role: dict(path=str(path), bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for role, path in paths.items()})
            path = root / 'receipt.json'
            path.write_text(json.dumps(receipt), encoding='utf-8')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(inspect_receipt(path, digest)['source_scope'], 'PUBLIC_FIXTURE')
            with self.assertRaisesRegex(ValueError, 'receipt-pin'):
                inspect_receipt(path, '0' * 64)
            original = paths['raw_xml'].read_bytes()
            paths['raw_xml'].write_bytes(original.replace(b'PerfFreq', b'BadField'))
            with self.assertRaisesRegex(ValueError, 'artifact-pin'):
                inspect_receipt(path, digest)
            paths['raw_xml'].write_bytes(original)
            changed = copy.deepcopy(receipt)
            changed['files']['raw_command']['sha256'] = '0' * 64
            path.write_text(json.dumps(changed), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'artifact-pin'):
                inspect_receipt(path, hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
