"""Inspect pinned tracerpt exports; never infer latency causes or field QA PASS.

Raw timestamps require tracerpt -rts; reports require a separate invocation.
Both must be bound to the same locked ETL and successful command receipts.
An exit code of zero means inspection completed, not that the trace is usable.
"""
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET


EVENT_NS = 'http://schemas.microsoft.com/win/2004/08/events/event'
TRACE_NS = 'http://schemas.microsoft.com/win/2004/08/events/trace'
NS = {'e': EVENT_NS, 't': TRACE_NS}
HEADER_GUID = '68fdd900-4a3e-11d1-84f4-0000f80464e3'
THREAD_GUID = '3d6fa8d1-fe05-11d0-9dda-00c04fd7ba7c'
MAX_XML_BYTES = 256 * 1024**2
MAX_EVENTS = 1_000_000


def require(value, reason):
    if not value:
        raise ValueError(reason)


def integer(text):
    require(isinstance(text, str), 'integer-text-required')
    text = text.strip()
    require(re.fullmatch(r'(?:0[xX][0-9a-fA-F]+|[0-9]+)', text), 'unsigned-integer-required')
    value = int(text, 16 if text.lower().startswith('0x') else 10)
    require(value <= 2**64 - 1, 'integer-overflow')
    return value


def guid(text):
    value = (text or '').strip('{}').lower()
    require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value), 'guid-required')
    return value


def scan_xml(stream, limit=MAX_XML_BYTES):
    """Reject DTD/entity declarations in UTF-8/16/32 before parsing any XML."""
    stream.seek(0)
    size = 0
    tail = b''
    while chunk := stream.read(64 * 1024):
        size += len(chunk)
        require(size <= limit, 'xml-byte-budget')
        text = tail + chunk.replace(b'\0', b'').upper()
        require(b'<!DOCTYPE' not in text and b'<!ENTITY' not in text, 'xml-declaration-forbidden')
        tail = text[-16:]
    stream.seek(0)


def data_fields(event):
    fields = {}
    for node in event.findall('e:EventData/e:Data', NS):
        name = node.get('Name')
        require(name and name not in fields and len(name) <= 128, 'duplicate-or-invalid-data-field')
        fields[name] = node.text
    return fields


def inspect_raw(stream, max_events=MAX_EVENTS):
    scan_xml(stream)
    iterator = ET.iterparse(stream, events=('start', 'end'))
    _, root = next(iterator)
    require(root.tag == 'Events', 'events-root-required')
    result = dict(events=0, missing_raw_timestamps=0, timestamp_reversals=0,
                  first_raw=None, last_raw=None, processing_errors=0, headers=[],
                  missing_provider_guids=0, opaque_binary_events=0,
                  scheduler_events={'cswitch': 0, 'ready_thread': 0},
                  scheduler_processing_errors=0, scheduler_opaque_events=0)
    signatures, errors = Counter(), Counter()
    previous = None
    depth = 1
    for action, event in iterator:
        if action == 'start':
            depth += 1
            require(depth <= 32, 'xml-depth-budget')
            continue
        if depth == 2:
            require(event.tag == '{' + EVENT_NS + '}Event', 'unexpected-root-child')
            result['events'] += 1
            require(result['events'] <= max_events, 'event-count-budget')
            system = event.find('e:System', NS)
            require(system is not None, 'event-system-required')
            provider_node = system.find('e:Provider', NS)
            require(provider_node is not None, 'event-provider-required')
            provider_text = provider_node.get('Guid')
            provider = guid(provider_text) if provider_text else None
            if provider is None:
                result['missing_provider_guids'] += 1
            opcode = integer(system.findtext('e:Opcode', namespaces=NS))
            version = integer(system.findtext('e:Version', namespaces=NS))
            class_text = event.findtext('t:ExtendedTracingInfo/t:EventGuid', namespaces=NS)
            event_guid = guid(class_text) if class_text else None
            key = f'{provider}/{event_guid}/{opcode}/{version}'
            signatures[key] += 1
            require(len(signatures) <= 4096, 'event-signature-budget')
            stamp = system.find('e:TimeCreated', NS)
            raw = stamp.get('RawTime') if stamp is not None else None
            if raw is None:
                result['missing_raw_timestamps'] += 1
            else:
                raw = integer(raw)
                if previous is not None and raw < previous:
                    result['timestamp_reversals'] += 1
                previous = raw
                result['first_raw'] = raw if result['first_raw'] is None else min(result['first_raw'], raw)
                result['last_raw'] = raw if result['last_raw'] is None else max(result['last_raw'], raw)
            failure = event.find('e:ProcessingErrorData', NS)
            opaque = event.find('e:BinaryEventData', NS) is not None
            if opaque:
                result['opaque_binary_events'] += 1
            if failure is not None:
                result['processing_errors'] += 1
                code = integer(failure.findtext('e:ErrorCode', namespaces=NS))
                errors[f'{key}/error={code}'] += 1
                require(len(errors) <= 4096, 'processing-error-signature-budget')
            if event_guid == THREAD_GUID and opcode in (36, 50):
                result['scheduler_events']['cswitch' if opcode == 36 else 'ready_thread'] += 1
                if failure is not None:
                    result['scheduler_processing_errors'] += 1
                if opaque:
                    result['scheduler_opaque_events'] += 1
            if event_guid == HEADER_GUID and opcode == 0:
                require(failure is None, 'trace-header-decode-failed')
                fields = data_fields(event)
                header = {name: integer(fields.get(name)) for name in (
                    'PerfFreq', 'ReservedFlags', 'EventsLost', 'BuffersLost',
                    'StartTime', 'EndTime', 'BuffersWritten', 'NumberOfProcessors',
                )}
                result['headers'].append(header)
                require(len(result['headers']) <= 256, 'header-count-budget')
            root.remove(event)
            event.clear()
        depth -= 1
    require(depth == 0 and result['events'] > 0, 'empty-or-unfinished-events')
    result['event_signatures'] = dict(signatures)
    result['processing_error_signatures'] = dict(errors)
    return result


def inspect_report(stream):
    scan_xml(stream, 16 * 1024**2)
    root = ET.parse(stream).getroot()
    require(root.tag == 'Report' and root.get('name') == 'tracerpt', 'tracerpt-report-required')
    items = root.findall("./Section[@name='tracerptHeader']/Table[@name='collection']/Item")
    require(len(items) == 1, 'single-report-collection-required')
    fields = {}
    for node in items[0].findall('Data'):
        name = node.get('name')
        require(name and name not in fields, 'duplicate-report-field')
        fields[name] = node.text
    return {key: integer(fields.get(key)) for key in ('buffers', 'events', 'lostEvents', 'skippedEvents')}


def assess(raw, report):
    issues = []
    headers = raw['headers']
    if len(headers) != 1:
        issues.append('single_trace_header_not_available')
    if any(h['ReservedFlags'] != 1 or h['PerfFreq'] <= 0 for h in headers):
        issues.append('qpc_clock_not_confirmed')
    if any(h['EndTime'] <= h['StartTime'] for h in headers):
        issues.append('finalized_positive_session_interval_not_confirmed')
    if any(h['EventsLost'] or h['BuffersLost'] for h in headers) or report['lostEvents']:
        loss = 'LOSS_DECLARED'
        issues.append('events_or_buffers_lost')
    elif not headers:
        loss = 'UNKNOWN'
    else:
        loss = 'ZERO_DECLARED_NOT_COVERAGE_PROOF'
    if raw['events'] != report['events']:
        issues.append('raw_report_event_count_mismatch')
    if report['skippedEvents']:
        issues.append('report_events_skipped')
    if raw['processing_errors']:
        issues.append('event_decode_errors')
    if raw['missing_provider_guids']:
        issues.append('provider_guids_missing')
    if raw['opaque_binary_events']:
        issues.append('opaque_binary_events_not_decoded')
    if raw['missing_raw_timestamps']:
        issues.append('raw_timestamps_missing')
    if raw['timestamp_reversals']:
        issues.append('timestamp_order_requires_review')
    if not all(raw['scheduler_events'].values()):
        issues.append('scheduler_event_classes_missing')
    return dict(
        schema='sfl-tracerpt-quality-v1', inspection_status='COMPLETED',
        quality='INCOMPLETE_OR_UNUSABLE' if issues else 'STRUCTURE_CONSISTENT_REQUIRES_CORRELATION',
        issues=issues, raw=raw, report=report, declared_loss=loss,
        request_time_coverage='NOT_EVALUATED', thread_generation_binding='NOT_EVALUATED',
        scheduler_payload_validation='NOT_EVALUATED', latency_cause='UNDETERMINED',
        field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False,
    )


def check_command(command, role, etl_path, xml_path):
    require(command['status'] == 'PASS' and type(command['actual_exit_code']) is int and command['actual_exit_code'] == 0
            and command['termination_requested'] is False
            and command['job_after_cleanup'][1] == 0 and not command['errors'], 'decode-command-failed')
    args = command['arguments']
    require(isinstance(args, list) and all(isinstance(x, str) for x in args), 'command-arguments-required')
    values = {}
    index = 0
    while index < len(args):
        option = args[index]
        require(option in ('-l', '-o', '-of', '-y', '-rts', '-summary', '-report')
                and option not in values, 'unexpected-or-duplicate-decode-option')
        index += 1
        if option in ('-y', '-rts'):
            values[option] = True
        else:
            require(index < len(args), 'missing-decode-option-value')
            values[option] = args[index]
            index += 1
    require(values.get('-l') == etl_path and values.get('-of') == 'XML', 'decode-input-binding')
    if role == 'raw':
        require(values.get('-o') == xml_path and values.get('-rts') is True
                and '-report' not in values and '-summary' not in values, 'raw-export-binding')
    else:
        require(values.get('-report') == xml_path and '-rts' not in values, 'report-export-binding')


def inspect_receipt(path, expected_sha256):
    # Existing native read-share-only helper also rejects reparse/hardlink paths.
    from field_installation_binding import locked_read, strict_json, stream_fact
    with ExitStack() as stack:
        receipt_stream = stack.enter_context(locked_read(Path(path)))
        require(os.fstat(receipt_stream.fileno()).st_size <= 64 * 1024, 'receipt-size')
        receipt_fact = stream_fact(receipt_stream)
        require(receipt_fact['bytes'] <= 64 * 1024 and receipt_fact['sha256'] == expected_sha256, 'receipt-pin')
        receipt_stream.seek(0)
        receipt = strict_json(receipt_stream.read())
        require(receipt['schema'] == 'sfl-tracerpt-decode-inputs-v1', 'decode-receipt-schema')
        require(receipt['source_scope'] in ('PUBLIC_FIXTURE', 'LOCAL_CONTROLLER_VALIDATION', 'FIELD_DIAGNOSTIC'), 'decode-source-scope')
        require(set(receipt['files']) == {'etl', 'raw_xml', 'report_xml', 'raw_command', 'report_command'}, 'decode-receipt-members')
        streams = {}
        for role, entry in receipt['files'].items():
            limit = 256 * 1024**2 if role in ('etl', 'raw_xml') else 16 * 1024**2
            require(type(entry['bytes']) is int and 0 <= entry['bytes'] <= limit, 'decode-artifact-size')
            stream = stack.enter_context(locked_read(Path(entry['path'])))
            require(os.fstat(stream.fileno()).st_size == entry['bytes'], 'decode-artifact-length')
            actual = stream_fact(stream)
            require(actual == {key: entry[key] for key in ('bytes', 'sha256')}, 'decode-artifact-pin')
            require(actual['bytes'] <= (256 * 1024**2 if role in ('etl', 'raw_xml') else 16 * 1024**2), 'decode-artifact-size')
            stream.seek(0)
            streams[role] = stream
        for role in ('raw', 'report'):
            command = strict_json(streams[role + '_command'].read())
            check_command(command, role, receipt['files']['etl']['path'], receipt['files'][role + '_xml']['path'])
        result = assess(inspect_raw(streams['raw_xml']), inspect_report(streams['report_xml']))
        result['input_receipt'] = receipt_fact
        result['source_scope'] = receipt['source_scope']
        result['input_files'] = receipt['files']
        return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--receipt-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect_receipt(args.receipt, args.receipt_sha256)
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    with args.output.open('xb') as stream:
        stream.write(encoded)
    print(json.dumps({'inspection_status': result['inspection_status'], 'quality': result['quality'],
                      'result_sha256': hashlib.sha256(encoded).hexdigest(), 'release_gate': 'HOLD'}))


if __name__ == '__main__':
    main()
